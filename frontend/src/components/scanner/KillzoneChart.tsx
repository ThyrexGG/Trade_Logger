import { useEffect, useRef, useState } from 'react'
import {
  ColorType,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'
import { getCandles } from '../../api/market'
import type { Candle } from '../../types/market'
import type { FairValueGap, KillzoneCandidate, LiquidityPool } from '../../types/scanner'

/** Reads a CSS custom property off :root, with a fallback (mirrors PriceChart). */
function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

function chartTheme() {
  return {
    text: cssVar('--tl-text-muted', '#8b95a5'),
    grid: cssVar('--tl-border-subtle', '#1c222c'),
    up: cssVar('--tl-positive', '#22c55e'),
    down: cssVar('--tl-negative', '#ef4444'),
    accent: cssVar('--tl-accent', '#f5b642'),
  }
}

/** View-only timeframe options for the chart itself — independent of the
 *  scan's own "entry timeframe". Changing this re-fetches a different candle
 *  series for display; it never re-runs the scan or changes what counts as
 *  a candidate. */
const VIEW_TF_OPTIONS = ['1m', '5m', '15m', '1h']
const HISTORY_OPTIONS = [150, 300, 500, 800]

/** Rough bar duration in seconds per timeframe — used to pad the auto-scroll
 *  window around a focused candidate, so an approximation is fine. */
const BAR_SECONDS: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600 }

interface Ohlc {
  time: number
  open: number
  high: number
  low: number
  close: number
}

/** The last candle at or before `ts`, so an event detected on one timeframe
 *  (the scan's) can still be placed correctly on a *different* timeframe's
 *  candles when the chart's own view is switched — lightweight-charts marks
 *  a marker only at an exact bar time, and a 1m sweep's timestamp won't
 *  exist as a bar boundary on a 15m series otherwise. */
function nearestBarTime(candles: Candle[], ts: number): number {
  let result = candles[0]?.time ?? ts
  for (const c of candles) {
    if (c.time <= ts) result = c.time
    else break
  }
  return result
}

/** A flat line of points spanning the loaded candles at a single price —
 *  invisible on screen, its only job is to nudge this pane's price-scale
 *  autoscale to include a level the candlestick series itself never touches.
 *  Liquidity targets are, by definition, often *outside* the current price
 *  action (that's the whole point of "draw on liquidity") — without this,
 *  the dashed/solid lines marking them can end up scrolled off the top or
 *  bottom of the visible range with no way to tell they're there. */
function flatLine(candles: Candle[], value: number): { time: Time; value: number }[] {
  if (candles.length === 0) return []
  const step = Math.max(1, Math.floor(candles.length / 12))
  const pts: { time: Time; value: number }[] = []
  for (let i = 0; i < candles.length; i += step) pts.push({ time: candles[i].time as Time, value })
  const last = candles[candles.length - 1]
  if (pts[pts.length - 1]?.time !== last.time) pts.push({ time: last.time as Time, value })
  return pts
}

/**
 * The scanner's findings drawn on the actual candles: sweep + shift markers
 * per candidate (price value in the label), BSL/SSL liquidity levels, and
 * unmitigated FVG boundaries plus a marker on the confirming candle. The
 * chart's own timeframe/history are independently adjustable (top-right) so
 * you can zoom out for context without re-running the scan; events are
 * re-snapped onto whichever candles are currently loaded. Hovering a row in
 * the candidates table (via `focusedIndex`) highlights that candidate's
 * pair, previews its entry/stop/target as price lines, and scrolls it into
 * view. Purely visual context — nothing here is computed independently of
 * the scan response, and nothing is clickable into an order path.
 */
export function KillzoneChart({
  symbol,
  ltf,
  candidates,
  liquidity,
  fvgs,
  focusedIndex = null,
  height = 400,
}: {
  symbol: string
  ltf: string
  candidates: KillzoneCandidate[]
  liquidity: { bsl: LiquidityPool[]; ssl: LiquidityPool[] } | null
  fvgs: FairValueGap[]
  focusedIndex?: number | null
  height?: number
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const linesRef = useRef<IPriceLine[]>([])
  const focusLinesRef = useRef<IPriceLine[]>([])
  const hintSeriesRef = useRef<ISeriesApi<'Line'>[]>([])

  // The chart's own view — defaults to match the scan, but is independently
  // adjustable. Re-syncs to the scan's timeframe whenever a genuinely new
  // scan configuration comes in.
  const [viewTf, setViewTf] = useState(ltf)
  const [count, setCount] = useState(300)
  useEffect(() => setViewTf(ltf), [ltf])

  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<string | null>(null)
  const [liveness, setLiveness] = useState<string | null>(null)
  const [hover, setHover] = useState<Ohlc | null>(null)

  // create / destroy the chart with the container
  useEffect(() => {
    if (!boxRef.current) return
    const t = chartTheme()
    const chart = createChart(boxRef.current, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: t.text, fontSize: 12 },
      grid: { vertLines: { color: t.grid }, horzLines: { color: t.grid } },
      rightPriceScale: { borderColor: t.grid },
      timeScale: { borderColor: t.grid, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 },
      autoSize: true,
    })
    const series = chart.addCandlestickSeries({
      upColor: t.up,
      downColor: t.down,
      borderUpColor: t.up,
      borderDownColor: t.down,
      wickUpColor: t.up,
      wickDownColor: t.down,
    })
    chartRef.current = chart
    seriesRef.current = series

    const onMove = (param: MouseEventParams<Time>) => {
      const bar = param.seriesData.get(series) as { open: number; high: number; low: number; close: number } | undefined
      if (!bar || param.time == null) {
        setHover(null)
        return
      }
      setHover({ time: param.time as unknown as number, open: bar.open, high: bar.high, low: bar.low, close: bar.close })
    }
    chart.subscribeCrosshairMove(onMove)

    return () => {
      chart.unsubscribeCrosshairMove(onMove)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      linesRef.current = []
      focusLinesRef.current = []
      hintSeriesRef.current = []
    }
  }, [])

  // fetch candles for the chart's own view (independent of the scan's ltf)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getCandles(symbol, viewTf, count)
      .then((r) => {
        if (cancelled) return
        setCandles(r.candles)
        setSource(r.source)
        setLiveness(r.liveness)
      })
      .catch((e) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Failed to load chart')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [symbol, viewTf, count])

  // candle data
  useEffect(() => {
    const s = seriesRef.current
    if (!s) return
    s.setData(
      candles
        .filter((c) => Number.isFinite(c.open))
        .map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close })),
    )
    if (candles.length) chartRef.current?.timeScale().fitContent()
  }, [candles])

  // All markers on the series in one place — lightweight-charts' setMarkers()
  // replaces the whole marker set on every call, so sweep/shift and FVG
  // markers have to be built together rather than in separate effects. Every
  // event's original timestamp is snapped onto the nearest loaded bar, so
  // switching the chart's view timeframe never leaves a marker stranded
  // between candles.
  //
  // Sweep + shift: one pair per candidate, price riding along in the label so
  // a glance tells you the level, not just the shape. The focused candidate
  // (hovered in the table) draws at full direction color; every other one
  // dims to muted grey so it doesn't compete for attention.
  //
  // FVG: a small circle marker sits on the *specific candle* that confirmed
  // the gap — detect_fvgs() (market_data.py) finds a 3-candle imbalance and
  // records `creation_time` as the third candle's, the one whose close
  // confirmed the gap exists, not the displacement candle itself.
  useEffect(() => {
    const s = seriesRef.current
    if (!s || candles.length === 0) return
    const t = chartTheme()
    const markers: SeriesMarker<Time>[] = []
    candidates.forEach((c, i) => {
      const below = c.direction === 'bullish'
      const focused = focusedIndex === i
      const dimmed = focusedIndex != null && !focused
      const dirColor = below ? t.up : t.down
      markers.push({
        time: nearestBarTime(candles, c.sweep_time) as Time,
        position: below ? 'belowBar' : 'aboveBar',
        color: dimmed ? 'rgba(139,149,165,0.35)' : t.text,
        shape: below ? 'arrowUp' : 'arrowDown',
        text: `Sweep ${c.sweep_level}`,
        size: focused ? 1.8 : 1.2,
      })
      markers.push({
        time: nearestBarTime(candles, c.shift_time) as Time,
        position: below ? 'belowBar' : 'aboveBar',
        color: dimmed ? 'rgba(139,149,165,0.35)' : dirColor,
        shape: below ? 'arrowUp' : 'arrowDown',
        text: `MSS ${c.shift_level}`,
        size: focused ? 1.8 : 1.2,
      })
    })
    fvgs.forEach((f) => {
      const bullish = f.type === 'Bullish'
      markers.push({
        time: nearestBarTime(candles, f.creation_time) as Time,
        position: 'inBar',
        color: bullish ? t.up : t.down,
        shape: 'circle',
        text: `FVG confirmed ${f.bottom}–${f.top}`,
        size: 0.8,
      })
    })
    markers.sort((a, b) => (a.time as number) - (b.time as number))
    s.setMarkers(markers)
  }, [candidates, fvgs, focusedIndex, candles])

  // liquidity levels + FVG boundaries as horizontal price lines, each labelled
  // with its actual price so the axis (and hover tooltip) reads like a real
  // trading terminal rather than a bare dashed line.
  useEffect(() => {
    const s = seriesRef.current
    if (!s) return
    linesRef.current.forEach((l) => s.removePriceLine(l))
    linesRef.current = []

    for (const p of liquidity?.bsl ?? []) {
      linesRef.current.push(
        s.createPriceLine({
          price: p.price, color: 'rgba(239,68,68,0.55)', lineWidth: 1, lineStyle: LineStyle.Dashed,
          axisLabelVisible: true, title: `BSL ${p.price}`,
        }),
      )
    }
    for (const p of liquidity?.ssl ?? []) {
      linesRef.current.push(
        s.createPriceLine({
          price: p.price, color: 'rgba(34,197,94,0.55)', lineWidth: 1, lineStyle: LineStyle.Dashed,
          axisLabelVisible: true, title: `SSL ${p.price}`,
        }),
      )
    }
    for (const f of fvgs) {
      const color = f.type === 'Bullish' ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'
      linesRef.current.push(
        s.createPriceLine({ price: f.top, color, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: `FVG ${f.top}` }),
      )
      linesRef.current.push(
        s.createPriceLine({ price: f.bottom, color, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: `FVG ${f.bottom}` }),
      )
    }
  }, [liquidity, fvgs])

  // Force the visible price range to actually include the nearest liquidity
  // target on each side (and the focused candidate's target) whenever it
  // would otherwise fall outside the candles' own range — see flatLine()'s
  // comment. Without this, "draw on liquidity" is invisible whenever price
  // hasn't approached it yet, which defeats the point of drawing it at all.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || candles.length === 0) return
    hintSeriesRef.current.forEach((hs) => chart.removeSeries(hs))
    hintSeriesRef.current = []

    const candleMin = Math.min(...candles.map((c) => c.low))
    const candleMax = Math.max(...candles.map((c) => c.high))
    const target = focusedIndex != null ? candidates[focusedIndex]?.potential_target ?? undefined : undefined
    const nearestBsl = liquidity?.bsl?.[0]?.price
    const nearestSsl = liquidity?.ssl?.[0]?.price

    const above = [nearestBsl, target].filter((v): v is number => v != null && v > candleMax)
    const below = [nearestSsl, target].filter((v): v is number => v != null && v < candleMin)
    const extremes: number[] = []
    if (above.length) extremes.push(Math.max(...above))
    if (below.length) extremes.push(Math.min(...below))

    extremes.forEach((value) => {
      const hint = chart.addLineSeries({
        color: 'transparent', lineVisible: false, lastValueVisible: false,
        priceLineVisible: false, crosshairMarkerVisible: false,
      })
      hint.setData(flatLine(candles, value))
      hintSeriesRef.current.push(hint)
    })
  }, [candles, liquidity, focusedIndex, candidates])

  // the focused candidate previews as an actual entry/stop/target trio (shift
  // level = entry reference, sweep level = stop reference — the same mapping
  // "Plan this" seeds into the checklist) and the view scrolls to it.
  useEffect(() => {
    const s = seriesRef.current
    const chart = chartRef.current
    if (!s) return
    focusLinesRef.current.forEach((l) => s.removePriceLine(l))
    focusLinesRef.current = []

    if (focusedIndex == null || !candidates[focusedIndex]) return
    const c = candidates[focusedIndex]
    const t = chartTheme()
    focusLinesRef.current.push(
      s.createPriceLine({
        price: c.shift_level, color: t.accent, lineWidth: 2, lineStyle: LineStyle.Solid,
        axisLabelVisible: true, title: `Entry ${c.shift_level}`,
      }),
    )
    focusLinesRef.current.push(
      s.createPriceLine({
        price: c.sweep_level, color: t.down, lineWidth: 2, lineStyle: LineStyle.Solid,
        axisLabelVisible: true, title: `Stop ${c.sweep_level}`,
      }),
    )
    if (c.potential_target != null) {
      focusLinesRef.current.push(
        s.createPriceLine({
          price: c.potential_target, color: t.up, lineWidth: 2, lineStyle: LineStyle.Solid,
          axisLabelVisible: true, title: `Target ${c.potential_target}${c.risk_reward != null ? ` (R:R ${c.risk_reward})` : ''}`,
        }),
      )
    }

    if (chart && candles.length) {
      const pad = (BAR_SECONDS[viewTf] ?? 900) * 12
      const from = Math.min(c.sweep_time, c.shift_time) - pad
      const to = Math.max(c.sweep_time, c.shift_time) + pad
      try {
        chart.timeScale().setVisibleRange({ from: from as Time, to: to as Time })
      } catch {
        /* range outside loaded data — leave the current view as-is */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedIndex, candidates, viewTf, candles.length])

  const last = candles[candles.length - 1]

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="font-mono text-sm font-semibold text-primary">{symbol}</span>
          {last ? <span className="font-mono text-sm tabular-nums text-secondary">{last.close}</span> : null}
          {hover ? (
            <span className="font-mono text-[11px] tabular-nums text-muted">
              O {hover.open} H {hover.high} L {hover.low} C {hover.close}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted">
          {liveness ? <span>{liveness}</span> : null}
          {source ? <span>{source}</span> : null}
          <label className="flex items-center gap-1">
            View
            <select
              value={viewTf}
              onChange={(e) => setViewTf(e.target.value)}
              className="rounded border border-border bg-background px-1.5 py-0.5 text-[11px] text-primary focus:border-accent focus:outline-none"
            >
              {VIEW_TF_OPTIONS.map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1">
            History
            <select
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="rounded border border-border bg-background px-1.5 py-0.5 text-[11px] text-primary focus:border-accent focus:outline-none"
            >
              {HISTORY_OPTIONS.map((n) => (
                <option key={n} value={n}>{n} candles</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <p className="border-b border-border-subtle bg-surface-elevated/40 px-3 py-1.5 text-[11px] leading-snug text-secondary">
        Read left to right: a <span className="font-semibold text-secondary">grey arrow</span> is where price briefly
        broke a level then snapped back (a sweep); the <span className="font-semibold text-positive">colored arrow</span>{' '}
        right after is where structure actually confirmed a reversal (MSS). The{' '}
        <span className="font-semibold">dashed lines</span> are liquidity levels price tends to get drawn toward — even
        when they're far from current price, the chart stretches to show them. Hover a row below to spotlight one
        candidate and preview its entry (gold), stop (red) and target (green).
      </p>

      <div className="relative" style={{ height }}>
        <div ref={boxRef} className="absolute inset-0" />
        {loading && candles.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">Loading chart…</div>
        ) : null}
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-negative">{error}</div>
        ) : null}
        {!loading && !error && candles.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">
            No candle data for {symbol} at {viewTf}.
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 border-t border-border-subtle px-3 py-2 text-[10.5px] text-muted sm:grid-cols-3">
        <span><span className="font-mono text-secondary">↑↓</span> grey = sweep</span>
        <span><span className="text-positive">▲</span>/<span className="text-negative">▼</span> colored = structure shift</span>
        <span><span className="text-negative">- -</span> red dashed = BSL (above)</span>
        <span><span className="text-positive">- -</span> green dashed = SSL (below)</span>
        <span>⋯ dotted = unmitigated FVG</span>
        <span>● dot = candle that confirmed the FVG</span>
      </div>
    </div>
  )
}
