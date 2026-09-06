import { useEffect, useMemo, useRef } from 'react'
import {
  ColorType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import { usePriceChart, CHART_TIMEFRAMES, type ChartTimeframe } from '../../lib/usePriceChart'

/** Reads a CSS custom property off :root, with a fallback. */
function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

function chartTheme() {
  return {
    bg: cssVar('--tl-surface', '#0e1116'),
    text: cssVar('--tl-text-muted', '#8b95a5'),
    grid: cssVar('--tl-border-subtle', '#1c222c'),
    up: cssVar('--tl-positive', '#22c55e'),
    down: cssVar('--tl-negative', '#ef4444'),
  }
}

const LIVENESS_LABEL: Record<string, { text: string; cls: string }> = {
  live: { text: 'live', cls: 'text-positive' },
  delayed: { text: 'delayed feed', cls: 'text-warning' },
  synthetic: { text: 'synthetic — no real feed', cls: 'text-negative' },
  unknown: { text: 'source unknown', cls: 'text-muted' },
}

export function PriceChart({
  symbol,
  tf,
  onTf,
  height = 300,
}: {
  symbol: string | null
  tf: ChartTimeframe
  onTf: (tf: ChartTimeframe) => void
  height?: number
}) {
  const { data, loading, error } = usePriceChart(symbol, tf)
  const boxRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

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
    }
  }, [])

  const candleData = useMemo<CandlestickData[]>(() => {
    if (!data?.candles?.length) return []
    return data.candles
      .filter((c) => Number.isFinite(c.open))
      .map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
  }, [data])

  useEffect(() => {
    const s = seriesRef.current
    if (!s) return
    s.setData(candleData)
    if (candleData.length) chartRef.current?.timeScale().fitContent()
  }, [candleData])

  const last = data?.candles?.[data.candles.length - 1]
  const first = data?.candles?.[0]
  const chg = last && first ? last.close - first.close : null
  const chgPct = chg != null && first?.close ? (chg / first.close) * 100 : null
  const live = data ? LIVENESS_LABEL[data.liveness] ?? LIVENESS_LABEL.unknown : null

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm font-semibold text-primary">{symbol ?? '—'}</span>
          {last ? (
            <span className="font-mono text-sm tabular-nums text-secondary">{last.close}</span>
          ) : null}
          {chg != null ? (
            <span className={`font-mono text-[11px] tabular-nums ${chg >= 0 ? 'text-positive' : 'text-negative'}`}>
              {chg >= 0 ? '▲' : '▼'} {chg >= 0 ? '+' : ''}
              {chgPct?.toFixed(2)}%
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {live ? <span className={`text-[10px] ${live.cls}`}>● {live.text}</span> : null}
          {data?.source ? <span className="text-[10px] text-muted">{data.source}</span> : null}
          <div className="flex overflow-hidden rounded border border-border-subtle">
            {CHART_TIMEFRAMES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onTf(t)}
                className={`px-2 py-0.5 text-[11px] font-mono ${
                  t === tf ? 'bg-accent/15 text-accent' : 'text-muted hover:text-secondary'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="relative" style={{ height }}>
        <div ref={boxRef} className="absolute inset-0" />
        {loading && !data ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">
            Loading {symbol} chart…
          </div>
        ) : null}
        {!loading && data && candleData.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-muted">
            No candle data for {symbol} at {tf}. {data.liveness === 'synthetic' ? 'No real feed reachable for this instrument.' : ''}
          </div>
        ) : null}
        {error && !data ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-negative">{error}</div>
        ) : null}
      </div>

      <p className="px-3 py-1.5 text-[10px] text-muted">
        Display only — no order path. Crypto is a real Binance feed; FX / metals fall back to a
        polled (delayed) source.
      </p>
    </div>
  )
}
