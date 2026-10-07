import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { formatSignedAmount } from '../../lib/format'
import { intensity, prettyDate, type HeatCell, type HeatGrid } from './homeMath'

const WEEKDAY_LABELS = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun']
const CHART_H = 190
const PAD = { top: 12, right: 64, bottom: 22, left: 4 }

function cellColor(cell: HeatCell, scale: number): string | undefined {
  if (!cell.data) return undefined
  const pnl = cell.data.net_profit
  if (pnl === 0) return 'var(--tl-text-muted)'
  const pct = Math.round(intensity(pnl, scale) * 100)
  const tone = pnl > 0 ? 'var(--tl-positive)' : 'var(--tl-negative)'
  return `color-mix(in oklab, ${tone} ${pct}%, var(--tl-surface-elevated))`
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

function compactUsd(v: number): string {
  const a = Math.abs(v)
  const s = a >= 10_000 ? `${(a / 1000).toFixed(0)}k` : a >= 1000 ? `${(a / 1000).toFixed(1)}k` : a.toFixed(0)
  return `${v < 0 ? '-' : v > 0 ? '+' : ''}${s}`
}

/**
 * The home screen's centrepiece: a compact weeks-by-weekday P&L heatmap next
 * to the running total since the first trade in view. Hovering a square or
 * the chart lights up the same day in both, and the readout above the chart
 * names it; clicking a square opens that day's trades.
 */
export function PnlHeatmap({
  grid,
  hovered,
  selected,
  onHover,
  onSelect,
}: {
  grid: HeatGrid
  hovered: string | null
  selected: string | null
  onHover: (iso: string | null) => void
  onSelect: (iso: string) => void
}) {
  const [chartRef, chartW] = useWidth<HTMLDivElement>()

  const past = grid.cells.filter((c) => !c.future)
  const firstIdx = past.findIndex((c) => c.data)
  // The chart starts at the first trade in view — no months of flat zero line before it.
  const series = firstIdx >= 0 ? past.slice(firstIdx) : []
  const values = series.map((c) => c.cumulative)
  const rawLo = Math.min(0, ...values)
  const rawHi = Math.max(0, ...values)
  const pad = (rawHi - rawLo || 1) * 0.08
  const lo = rawLo - (rawLo < 0 ? pad : 0)
  const hi = rawHi + pad
  const innerW = Math.max(0, chartW - PAD.left - PAD.right)
  const innerH = CHART_H - PAD.top - PAD.bottom
  const xAt = (i: number) => PAD.left + (series.length > 1 ? (i / (series.length - 1)) * innerW : innerW / 2)
  const yOf = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo || 1)) * innerH
  const indexOf = new Map(series.map((c, i) => [c.iso, i]))

  const line = chartW && series.length ? series.map((c, i) => `${i ? 'L' : 'M'}${xAt(i).toFixed(1)},${yOf(c.cumulative).toFixed(1)}`).join('') : ''
  const area = line ? `${line}L${xAt(series.length - 1).toFixed(1)},${yOf(0).toFixed(1)}L${xAt(0).toFixed(1)},${yOf(0).toFixed(1)}Z` : ''
  // Zero always gets a label; the high/low only when they won't collide with it.
  const ticks = [0, rawHi, rawLo].filter((v, i, a) => a.indexOf(v) === i && (v === 0 || Math.abs(yOf(v) - yOf(0)) >= 16))

  const focus = (hovered && grid.cells.find((c) => c.iso === hovered && !c.future)) || series[series.length - 1] || null
  const focusIdx = focus ? indexOf.get(focus.iso) : undefined

  function chartPointer(e: React.PointerEvent<HTMLDivElement>) {
    if (!innerW || !series.length) return
    const x = e.clientX - e.currentTarget.getBoundingClientRect().left - PAD.left
    const i = Math.round(Math.max(0, Math.min(1, x / innerW)) * (series.length - 1))
    onHover(series[i]?.iso ?? null)
  }

  return (
    <div className="tl-cal" style={{ '--weeks': grid.weeks } as CSSProperties}>
      {/* Heatmap */}
      <div className="tl-heat">
        <div className="tl-heat-months" aria-hidden="true">
          {grid.monthMarks.map((m) => (
            <span key={`${m.col}-${m.label}`} style={{ '--col': m.col } as CSSProperties}>
              {m.label}
            </span>
          ))}
        </div>
        <div className="tl-heat-body">
          <div className="tl-heat-days" aria-hidden="true">
            {WEEKDAY_LABELS.map((d, i) => (
              <span key={i}>{d}</span>
            ))}
          </div>
          <div className="tl-heat-cells" role="group" aria-label="Daily P&L heatmap" onPointerLeave={() => onHover(null)}>
            {grid.cells.map((c) => {
              const style = { '--d': `${c.col * 30 + c.row * 12}ms`, background: cellColor(c, grid.scale) } as CSSProperties
              const cls = [
                'tl-heat-cell',
                c.future ? 'is-future' : '',
                c.data ? 'has-data' : '',
                c.row >= 5 ? 'is-weekend' : '',
                c.iso === grid.todayIso ? 'is-today' : '',
                c.iso === hovered ? 'is-hovered' : '',
                c.iso === selected ? 'is-selected' : '',
              ].join(' ')
              return c.data ? (
                <button
                  key={c.iso}
                  type="button"
                  className={cls}
                  style={style}
                  aria-label={`${prettyDate(c.iso)}: ${formatSignedAmount(c.data.net_profit)} across ${c.data.trades} trade${c.data.trades === 1 ? '' : 's'}`}
                  aria-pressed={c.iso === selected}
                  onPointerEnter={() => onHover(c.iso)}
                  onFocus={() => onHover(c.iso)}
                  onBlur={() => onHover(null)}
                  onClick={() => onSelect(c.iso)}
                />
              ) : (
                <div key={c.iso} className={cls} style={style} onPointerEnter={() => onHover(c.future ? null : c.iso)} />
              )
            })}
          </div>
        </div>
        <div className="tl-heat-legend" aria-hidden="true">
          <span>Loss</span>
          {[1, 0.6, 0.3].map((t) => (
            <i key={`n${t}`} style={{ background: `color-mix(in oklab, var(--tl-negative) ${28 + t * 72}%, var(--tl-surface-elevated))` }} />
          ))}
          <i style={{ background: 'var(--tl-surface-elevated)' }} />
          {[0.3, 0.6, 1].map((t) => (
            <i key={`p${t}`} style={{ background: `color-mix(in oklab, var(--tl-positive) ${28 + t * 72}%, var(--tl-surface-elevated))` }} />
          ))}
          <span>Profit</span>
        </div>
      </div>

      {/* Running total */}
      <div className="tl-cal-chart">
        <div className="tl-cal-readout" aria-live="polite">
          {focus ? (
            <>
              <span className="text-xs text-muted">{focus === series[series.length - 1] && !hovered ? 'Today' : prettyDate(focus.iso)}</span>
              {focus.data ? (
                <span className={`font-mono text-sm font-semibold ${focus.data.net_profit >= 0 ? 'text-positive' : 'text-negative'}`}>
                  {formatSignedAmount(focus.data.net_profit)}
                  <span className="ml-1.5 font-sans text-xs font-normal text-muted">
                    {focus.data.trades} trade{focus.data.trades === 1 ? '' : 's'} · {focus.data.wins} won
                  </span>
                </span>
              ) : (
                <span className="text-xs text-muted">no closed trades</span>
              )}
              <span className="ml-auto text-xs text-muted">
                running total{' '}
                <span className={`font-mono text-sm font-semibold ${focus.cumulative >= 0 ? 'text-primary' : 'text-negative'}`}>{formatSignedAmount(focus.cumulative)}</span>
              </span>
            </>
          ) : (
            <span className="text-xs text-muted">The running total draws itself here once a trade closes.</span>
          )}
        </div>

        <div
          ref={chartRef}
          className="tl-cal-plot"
          onPointerMove={chartPointer}
          onPointerLeave={() => onHover(null)}
          role="img"
          aria-label="Running total of closed-trade P&L since the first trade in view"
        >
          {line ? (
            <svg width={chartW} height={CHART_H} className="block">
              <defs>
                <linearGradient id="tl-cal-fill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="var(--tl-glow-a)" stopOpacity="0.22" />
                  <stop offset="100%" stopColor="var(--tl-glow-a)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {ticks.map((v) => (
                <g key={v}>
                  <line
                    x1={PAD.left}
                    x2={PAD.left + innerW}
                    y1={yOf(v)}
                    y2={yOf(v)}
                    stroke={v === 0 ? 'var(--tl-border)' : 'var(--tl-border-subtle)'}
                    strokeDasharray={v === 0 ? '3 4' : undefined}
                  />
                  <text x={PAD.left + innerW + 8} y={yOf(v) + 3.5} fontSize={10} fill="var(--tl-text-muted)" fontFamily="var(--tl-font-mono)">
                    {v === 0 ? '0' : compactUsd(v)}
                  </text>
                </g>
              ))}
              <text x={PAD.left} y={CHART_H - 4} fontSize={10} fill="var(--tl-text-muted)">
                {prettyDate(series[0].iso, { day: 'numeric', month: 'short' })}
              </text>
              <text x={PAD.left + innerW} y={CHART_H - 4} fontSize={10} fill="var(--tl-text-muted)" textAnchor="end">
                Today
              </text>
              <path d={area} fill="url(#tl-cal-fill)" className="tl-ribbon-area" />
              <path d={line} fill="none" stroke="var(--tl-accent)" strokeWidth={2} strokeLinejoin="round" pathLength={1} className="tl-ribbon-line" />
              {focusIdx !== undefined && hovered ? (
                <g>
                  <line x1={xAt(focusIdx)} x2={xAt(focusIdx)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--tl-accent)" strokeOpacity={0.35} />
                  <circle cx={xAt(focusIdx)} cy={yOf(series[focusIdx].cumulative)} r={4.5} fill="var(--tl-background)" stroke="var(--tl-accent)" strokeWidth={2} />
                </g>
              ) : null}
              <circle cx={xAt(series.length - 1)} cy={yOf(series[series.length - 1].cumulative)} r={3.5} fill="var(--tl-accent)" className="tl-ribbon-end" />
            </svg>
          ) : null}
        </div>
      </div>
    </div>
  )
}
