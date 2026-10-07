import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { formatSignedAmount } from '../../lib/format'
import { intensity, prettyDate, type HeatCell, type HeatGrid } from './homeMath'

const WEEKDAY_LABELS = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun']
const RIBBON_H = 116
const RIBBON_PAD = 10

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

/**
 * The home screen's centrepiece: a weeks-by-weekday P&L heatmap with a
 * cumulative-P&L ribbon drawn directly underneath it. The ribbon's x-axis is
 * the heatmap's columns, so the curve sits under the weeks that made it, and
 * hovering either one lights up the same day in both.
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
  const cellsRef = useRef<HTMLDivElement>(null)
  const cellEls = useRef(new Map<string, HTMLElement>())
  const [tip, setTip] = useState<{ x: number; y: number; below: boolean } | null>(null)
  const [ribbonRef, ribbonW] = useWidth<HTMLDivElement>()

  const hoveredCell = useMemo(() => grid.cells.find((c) => c.iso === hovered) ?? null, [grid, hovered])

  // Position the tooltip over whichever cell is hovered — from the grid *or* the ribbon.
  useEffect(() => {
    const host = cellsRef.current
    const el = hovered ? cellEls.current.get(hovered) : null
    if (!host || !el) {
      setTip(null)
      return
    }
    const h = host.getBoundingClientRect()
    const r = el.getBoundingClientRect()
    const y = r.top - h.top
    const x = Math.min(h.width - 96, Math.max(96, r.left - h.left + r.width / 2))
    setTip({ x, y: y < 70 ? r.bottom - h.top : y, below: y < 70 })
  }, [hovered])

  const past = grid.cells.filter((c) => !c.future)
  const values = past.map((c) => c.cumulative)
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  const span = hi - lo || 1
  const xOf = (c: HeatCell) => ((c.col + (c.row + 0.5) / 7) / grid.weeks) * ribbonW
  const yOf = (v: number) => RIBBON_PAD + (1 - (v - lo) / span) * (RIBBON_H - RIBBON_PAD * 2)
  const anyTrades = past.some((c) => c.data)

  const line = ribbonW && past.length ? past.map((c, i) => `${i ? 'L' : 'M'}${xOf(c).toFixed(1)},${yOf(c.cumulative).toFixed(1)}`).join('') : ''
  const area = line ? `${line}L${xOf(past[past.length - 1]).toFixed(1)},${yOf(lo)}L${xOf(past[0]).toFixed(1)},${yOf(lo)}Z` : ''

  function ribbonPointer(e: React.PointerEvent<HTMLDivElement>) {
    if (!ribbonW) return
    const x = e.clientX - e.currentTarget.getBoundingClientRect().left
    const t = Math.max(0, Math.min(0.9999, x / ribbonW)) * grid.weeks
    const idx = Math.min(past.length - 1, Math.floor(t) * 7 + Math.floor((t % 1) * 7))
    onHover(past[Math.max(0, idx)]?.iso ?? null)
  }

  return (
    <div className="tl-heat" style={{ '--weeks': grid.weeks } as CSSProperties}>
      <div className="tl-heat-months" aria-hidden="true">
        <span />
        <div className="tl-heat-months-track">
          {grid.monthMarks.map((m) => (
            <span key={`${m.col}-${m.label}`} style={{ left: `${(m.col / grid.weeks) * 100}%` }}>
              {m.label}
            </span>
          ))}
        </div>
      </div>

      <div className="tl-heat-body">
        <div className="tl-heat-days" aria-hidden="true">
          {WEEKDAY_LABELS.map((d, i) => (
            <span key={i}>{d}</span>
          ))}
        </div>

        <div ref={cellsRef} className="tl-heat-cells" role="group" aria-label="Daily P&L heatmap" onPointerLeave={() => onHover(null)}>
          {grid.cells.map((c) => {
            const style = {
              '--d': `${c.col * 26 + c.row * 10}ms`,
              background: cellColor(c, grid.scale),
            } as CSSProperties
            const cls = [
              'tl-heat-cell',
              c.future ? 'is-future' : '',
              c.data ? 'has-data' : '',
              c.row >= 5 ? 'is-weekend' : '',
              c.iso === grid.todayIso ? 'is-today' : '',
              c.iso === hovered ? 'is-hovered' : '',
              c.iso === selected ? 'is-selected' : '',
            ].join(' ')
            const register = (el: HTMLElement | null) => {
              if (el) cellEls.current.set(c.iso, el)
              else cellEls.current.delete(c.iso)
            }
            return c.data ? (
              <button
                key={c.iso}
                ref={register}
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
              <div key={c.iso} ref={register} className={cls} style={style} onPointerEnter={() => onHover(c.future ? null : c.iso)} />
            )
          })}

          {tip && hoveredCell ? (
            <div className={`tl-heat-tip ${tip.below ? 'is-below' : ''}`} style={{ left: tip.x, top: tip.y }} role="status">
              <div className="text-[11px] text-muted">{prettyDate(hoveredCell.iso, { weekday: 'long', day: 'numeric', month: 'long' })}</div>
              {hoveredCell.data ? (
                <>
                  <div className={`font-mono text-base font-semibold ${hoveredCell.data.net_profit >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {formatSignedAmount(hoveredCell.data.net_profit)}
                  </div>
                  <div className="text-[11px] text-secondary">
                    {hoveredCell.data.trades} trade{hoveredCell.data.trades === 1 ? '' : 's'} · {hoveredCell.data.wins} won · click for details
                  </div>
                </>
              ) : (
                <div className="text-xs text-secondary">No closed trades</div>
              )}
              <div className="mt-1 border-t border-border-subtle pt-1 font-mono text-[11px] text-muted">
                running total {formatSignedAmount(hoveredCell.cumulative)}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="tl-heat-ribbon-row">
        <span className="tl-heat-ribbon-label" aria-hidden="true">P&amp;L</span>
        <div
          ref={ribbonRef}
          className="tl-heat-ribbon"
          onPointerMove={ribbonPointer}
          onPointerLeave={() => onHover(null)}
          aria-label="Running total of closed-trade P&L across the same weeks"
          role="img"
        >
          {line && anyTrades ? (
            <svg width={ribbonW} height={RIBBON_H} className="block overflow-visible">
              <defs>
                <linearGradient id="tl-ribbon-fill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="var(--tl-glow-a)" stopOpacity="0.32" />
                  <stop offset="100%" stopColor="var(--tl-glow-a)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <line x1={0} x2={ribbonW} y1={yOf(0)} y2={yOf(0)} stroke="var(--tl-border)" strokeDasharray="3 4" />
              <path d={area} fill="url(#tl-ribbon-fill)" className="tl-ribbon-area" />
              <path d={line} fill="none" stroke="var(--tl-accent)" strokeWidth={2} strokeLinejoin="round" pathLength={1} className="tl-ribbon-line" />
              {hoveredCell && !hoveredCell.future ? (
                <g>
                  <line x1={xOf(hoveredCell)} x2={xOf(hoveredCell)} y1={0} y2={RIBBON_H} stroke="var(--tl-accent)" strokeOpacity={0.35} />
                  <circle cx={xOf(hoveredCell)} cy={yOf(hoveredCell.cumulative)} r={4.5} fill="var(--tl-background)" stroke="var(--tl-accent)" strokeWidth={2} />
                </g>
              ) : null}
              <circle
                cx={xOf(past[past.length - 1])}
                cy={yOf(past[past.length - 1].cumulative)}
                r={3.5}
                fill="var(--tl-accent)"
                className="tl-ribbon-end"
              />
            </svg>
          ) : (
            <div className="flex h-full items-center text-xs text-muted">The running total draws itself here once trades close.</div>
          )}
        </div>
      </div>
    </div>
  )
}
