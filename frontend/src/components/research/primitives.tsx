import { useRef, useState, type PointerEvent, type ReactNode } from 'react'
import { classifySentiment, toneArrow } from '../../lib/sentiment'
export { SectionCard, SectionError, SkeletonRows } from '../intelligence/primitives'
export { HashChip } from '../evidence/primitives'

export type ResearchTone = 'positive' | 'negative' | 'warning' | 'info' | 'neutral'

const TAG: Record<ResearchTone, string> = {
  positive: 'text-positive border-positive/30 bg-positive/10',
  negative: 'text-negative border-negative/30 bg-negative/10',
  warning: 'text-warning border-warning/30 bg-warning/10',
  info: 'text-info border-info/30 bg-info/10',
  neutral: 'text-secondary border-border-subtle bg-surface-elevated',
}

const TEXT: Record<ResearchTone, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  info: 'text-info',
  neutral: 'text-secondary',
}

/** Presentation-only tone for a backend research-status string. */
export function researchTone(value: string | null | undefined): ResearchTone {
  const v = (value || '').toUpperCase()
  if (v.includes('FAIL') || v.includes('ERROR') || v.includes('INVALID')) return 'negative'
  if (v.includes('RUNNING') || v.includes('STALE') || v.includes('PENDING')) return 'warning'
  if (v.includes('COMPLETE') || v.includes('ROBUST') || v.includes('READY') || v.includes('PASS')) {
    return 'positive'
  }
  // fall back to the shared classifier so NOT_ESTABLISHED / PROMISING / DECAYED /
  // USABLE_EDGE_FOUND etc. get a sensible colour instead of always "neutral".
  const s = classifySentiment(value).tone
  if (s === 'up') return 'positive'
  if (s === 'down') return 'negative'
  if (s === 'caution') return 'warning'
  return 'neutral'
}

export function ResearchStatusTag({
  value,
  tone,
  size = 'md',
}: {
  value: string
  tone?: ResearchTone
  size?: 'sm' | 'md'
}) {
  const t = tone ?? researchTone(value)
  const arrow = toneArrow(t, value)
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border font-mono leading-none ${
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-[11px]'
      } ${TAG[t]}`}
    >
      {arrow ? <span aria-hidden="true">{arrow}</span> : null}
      {value}
    </span>
  )
}

/** Compact research metric card. A missing value renders "—", never "0". */
export function MetricCard({
  label,
  value,
  sub,
  tone,
}: {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode
  tone?: ResearchTone
}) {
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-3 py-2">
      <p className="flex items-center text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-0.5 font-mono text-lg tabular-nums ${tone ? TEXT[tone] : 'text-primary'}`}>
        {value}
      </p>
      {sub ? <p className="text-[10px] text-muted">{sub}</p> : null}
    </div>
  )
}

/** Truthful "the backend does not expose this" state. */
export function ResearchUnavailable({ children }: { children: ReactNode }) {
  return (
    <p className="rounded border border-dashed border-border-subtle px-3 py-4 text-center text-xs text-muted">
      {children}
    </p>
  )
}

export interface SparklinePoint {
  time: string
  equity: number
  /** Optional extra context for the hover tooltip (analytics passes both; a plain equity curve can omit them). */
  netProfit?: number
  symbol?: string
}

function formatSparklineTime(iso: string): { date: string; time: string | null } {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return { date: iso.slice(0, 10), time: null }
  const hasTime = iso.length > 10
  return {
    date: d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
    time: hasTime ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : null,
  }
}

/**
 * Equity-curve sparkline. Plots real (time, equity) points only — no
 * smoothing, no synthetic interpolation. Down-samples for rendering while
 * keeping the first and last real points. Hoverable: tracks the pointer to
 * the nearest real point and shows a glass-panel tooltip with its date,
 * balance, and (when the caller has it) the trade that produced it.
 */
export function Sparkline({
  points,
  height = 120,
  render = 320,
}: {
  points: SparklinePoint[]
  height?: number
  render?: number
}) {
  const [hover, setHover] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  if (points.length < 2) {
    return <ResearchUnavailable>Not enough equity points to plot.</ResearchUnavailable>
  }

  const step = points.length > render ? Math.ceil(points.length / render) : 1
  const sampled: typeof points = []
  for (let i = 0; i < points.length; i += step) sampled.push(points[i])
  if (sampled[sampled.length - 1] !== points[points.length - 1]) {
    sampled.push(points[points.length - 1])
  }

  const values = sampled.map((p) => p.equity)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const w = 1000
  const h = height
  const first = sampled[0].equity
  const last = sampled[sampled.length - 1].equity
  const up = last >= first
  const lastIdx = sampled.length - 1

  const yOf = (equity: number) => h - ((equity - min) / range) * h

  const d = sampled
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${((i / lastIdx) * w).toFixed(1)},${yOf(p.equity).toFixed(1)}`)
    .join(' ')

  const baselineY = yOf(first)

  const updateHover = (e: PointerEvent<HTMLDivElement>) => {
    const el = containerRef.current
    if (!el || lastIdx === 0) return
    const rect = el.getBoundingClientRect()
    if (rect.width === 0) return
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    setHover(Math.round(ratio * lastIdx))
  }

  // Pointer capture: once a touch starts tracking the curve, keep delivering
  // pointermove to this element even if the finger drifts a pixel outside
  // its exact bounds mid-drag — without this a real touch drag (unlike a
  // mouse, which stays precisely where you put it) loses tracking the
  // moment the contact point wobbles off the element.
  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    containerRef.current?.setPointerCapture(e.pointerId)
    updateHover(e)
  }

  const point = hover !== null ? sampled[hover] : null
  const leftPct = hover !== null ? (hover / lastIdx) * 100 : 0
  const topPct = point ? (yOf(point.equity) / h) * 100 : 0
  const side = leftPct > 70 ? 'right' : leftPct < 30 ? 'left' : 'center'
  const fmt = point ? formatSparklineTime(point.time) : null

  return (
    <div>
      <div
        ref={containerRef}
        // pan-y (not `touch-none`): a touch-drag across the chart tracks the
        // curve horizontally, but a vertical swipe that merely starts on the
        // chart while scrolling the page must still scroll the page —
        // `touch-none` was swallowing that gesture entirely on a phone.
        className="relative touch-pan-y select-none"
        onPointerMove={updateHover}
        onPointerDown={onDown}
        onPointerLeave={() => setHover(null)}
      >
        <svg
          viewBox={`0 0 ${w} ${h}`}
          preserveAspectRatio="none"
          className="h-32 w-full"
          role="img"
          aria-label={`Equity curve from ${first.toFixed(2)} to ${last.toFixed(
            2,
          )} over ${points.length} points`}
        >
          <line
            x1="0"
            x2={w}
            y1={baselineY}
            y2={baselineY}
            stroke="currentColor"
            className="text-border"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
          {hover !== null ? (
            <line
              x1={(hover / lastIdx) * w}
              x2={(hover / lastIdx) * w}
              y1="0"
              y2={h}
              stroke="currentColor"
              className="text-border-subtle"
              strokeWidth="1"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
          ) : null}
          <path
            d={d}
            fill="none"
            stroke="currentColor"
            className={up ? 'text-positive' : 'text-negative'}
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        </svg>

        {point ? (
          <>
            <div
              aria-hidden="true"
              className={`pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--tl-surface)] shadow ${
                up ? 'bg-positive' : 'bg-negative'
              }`}
              style={{ left: `${leftPct}%`, top: `${topPct}%` }}
            />
            {/* Glassmorphism: a translucent, blurred panel so the curve stays
               visible underneath — reads correctly in both themes because
               --tl-glass-* is redefined per theme in tokens.css, not hardcoded here. */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute top-1 z-10 min-w-[8rem] rounded-lg px-2.5 py-1.5 text-[11px] shadow-lg backdrop-blur-md transition-opacity duration-100"
              style={{
                left: side === 'center' ? `${leftPct}%` : side === 'left' ? '0%' : undefined,
                right: side === 'right' ? '0%' : undefined,
                transform: side === 'center' ? 'translateX(-50%)' : undefined,
                background: 'var(--tl-glass-bg)',
                border: '1px solid var(--tl-glass-border)',
                boxShadow: `0 8px 24px var(--tl-glass-shadow)`,
              }}
            >
              <div className="font-mono text-muted">
                {fmt?.date}
                {fmt?.time ? <span className="ml-1 opacity-70">{fmt.time}</span> : null}
              </div>
              <div className={`font-mono text-sm font-semibold ${up ? 'text-positive' : 'text-negative'}`}>
                ${point.equity.toFixed(2)}
              </div>
              {point.netProfit !== undefined ? (
                <div className="font-mono text-[10px] text-secondary">
                  {point.symbol ? `${point.symbol} · ` : ''}
                  {point.netProfit >= 0 ? '+' : ''}
                  {point.netProfit.toFixed(2)}
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] tabular-nums text-muted">
        <span>{sampled[0].time.slice(0, 10)}</span>
        <span>
          {first.toFixed(0)} → {last.toFixed(0)}
        </span>
        <span>{sampled[sampled.length - 1].time.slice(0, 10)}</span>
      </div>
    </div>
  )
}
