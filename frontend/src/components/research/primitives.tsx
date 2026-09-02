import type { ReactNode } from 'react'
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
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border font-mono leading-none ${
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-[11px]'
      } ${TAG[t]}`}
    >
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
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: ResearchTone
}) {
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
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

/** Research-only safety strip. */
export function ResearchSafetyBanner({ broker = 'BLOCKED' }: { broker?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-blocked/30 bg-blocked/10 px-3 py-2 text-[11px]">
      <span className="font-mono font-semibold uppercase tracking-wider text-blocked">
        Historical Research
      </span>
      <span className="text-secondary">Live automation disabled</span>
      <span className="text-secondary">·</span>
      <span className="text-secondary">Broker transmission {broker}</span>
      <span className="text-secondary">·</span>
      <span className="text-secondary">No live execution</span>
    </div>
  )
}

/**
 * Minimal equity-curve sparkline. Plots real (time, equity) points only — no
 * smoothing, no synthetic interpolation. Down-samples for rendering while
 * keeping the first and last real points.
 */
export function Sparkline({
  points,
  height = 120,
  render = 320,
}: {
  points: { time: string; equity: number }[]
  height?: number
  render?: number
}) {
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

  const d = sampled
    .map((p, i) => {
      const x = (i / (sampled.length - 1)) * w
      const y = h - ((p.equity - min) / range) * h
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const baselineY = h - ((first - min) / range) * h

  return (
    <div>
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
        <path
          d={d}
          fill="none"
          stroke="currentColor"
          className={up ? 'text-positive' : 'text-negative'}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
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
