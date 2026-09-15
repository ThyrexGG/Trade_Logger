import { useEffect, useRef, useState } from 'react'
import {
  ColorType,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
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
  }
}

/**
 * The same candles the scanner analyzed, with its findings drawn on top:
 * sweep + shift markers per candidate, BSL/SSL liquidity levels, and
 * unmitigated FVG boundaries. Purely visual context for the table above/below
 * it — nothing here is computed independently, and nothing is clickable into
 * an order path.
 */
export function KillzoneChart({
  symbol,
  ltf,
  candidates,
  liquidity,
  fvgs,
  height = 340,
}: {
  symbol: string
  ltf: string
  candidates: KillzoneCandidate[]
  liquidity: { bsl: LiquidityPool[]; ssl: LiquidityPool[] } | null
  fvgs: FairValueGap[]
  height?: number
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const linesRef = useRef<IPriceLine[]>([])

  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<string | null>(null)
  const [liveness, setLiveness] = useState<string | null>(null)

  // create / destroy the chart with the container
  useEffect(() => {
    if (!boxRef.current) return
    const t = chartTheme()
    const chart = createChart(boxRef.current, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: t.text, fontSize: 11 },
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
    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      linesRef.current = []
    }
  }, [])

  // fetch the same candles the scan itself just looked at
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getCandles(symbol, ltf, 200)
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
  }, [symbol, ltf])

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

  // sweep + shift markers, one pair per candidate
  useEffect(() => {
    const s = seriesRef.current
    if (!s) return
    const t = chartTheme()
    const markers: SeriesMarker<Time>[] = []
    for (const c of candidates) {
      const below = c.direction === 'bullish'
      markers.push({
        time: c.sweep_time as Time,
        position: below ? 'belowBar' : 'aboveBar',
        color: t.text,
        shape: below ? 'arrowUp' : 'arrowDown',
        text: 'Sweep',
      })
      markers.push({
        time: c.shift_time as Time,
        position: below ? 'belowBar' : 'aboveBar',
        color: below ? t.up : t.down,
        shape: below ? 'arrowUp' : 'arrowDown',
        text: 'MSS',
      })
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number))
    s.setMarkers(markers)
  }, [candidates])

  // liquidity levels + FVG boundaries as horizontal price lines
  useEffect(() => {
    const s = seriesRef.current
    if (!s) return
    linesRef.current.forEach((l) => s.removePriceLine(l))
    linesRef.current = []

    for (const p of liquidity?.bsl ?? []) {
      linesRef.current.push(
        s.createPriceLine({
          price: p.price, color: 'rgba(239,68,68,0.55)', lineWidth: 1, lineStyle: LineStyle.Dashed,
          axisLabelVisible: true, title: 'BSL',
        }),
      )
    }
    for (const p of liquidity?.ssl ?? []) {
      linesRef.current.push(
        s.createPriceLine({
          price: p.price, color: 'rgba(34,197,94,0.55)', lineWidth: 1, lineStyle: LineStyle.Dashed,
          axisLabelVisible: true, title: 'SSL',
        }),
      )
    }
    for (const f of fvgs) {
      const color = f.type === 'Bullish' ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'
      linesRef.current.push(
        s.createPriceLine({ price: f.top, color, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: 'FVG' }),
      )
      linesRef.current.push(
        s.createPriceLine({ price: f.bottom, color, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false }),
      )
    }
  }, [liquidity, fvgs])

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm font-semibold text-primary">{symbol}</span>
          <span className="text-[10px] text-muted">{ltf} · sweeps, shifts &amp; liquidity marked</span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted">
          {liveness ? <span>{liveness}</span> : null}
          {source ? <span>{source}</span> : null}
        </div>
      </div>

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
            No candle data for {symbol} at {ltf}.
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border-subtle px-3 py-1.5 text-[10px] text-muted">
        <span>grey arrow = sweep</span>
        <span><span className="text-positive">▲</span>/<span className="text-negative">▼</span> = structure shift</span>
        <span className="text-negative">- - BSL</span>
        <span className="text-positive">- - SSL</span>
        <span>dotted = unmitigated FVG</span>
      </div>
    </div>
  )
}
