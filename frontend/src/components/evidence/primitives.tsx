import type { ReactNode } from 'react'
export {
  SectionCard,
  SectionError,
  SkeletonRows,
  FreshnessBadge,
} from '../intelligence/primitives'

export type EvidenceTone = 'positive' | 'negative' | 'warning' | 'info' | 'neutral'

/**
 * Classifies an authoritative evidence/governance state string into a display
 * tone. This is presentation only — it never overrides or recomputes the
 * backend's own classification, it just picks a colour for the exact string
 * the engine emitted.
 */
export function evidenceTone(value: string | undefined | null): EvidenceTone {
  const v = (value || '').toUpperCase()
  if (
    v.includes('DECAY') ||
    v.includes('DEGRADATION') ||
    v.includes('DETERIOR') ||
    v.includes('STRUCTURAL') ||
    v.includes('BLOCKED') ||
    v.includes('FAIL') ||
    v.includes('INVALID') ||
    v.includes('NEGATIVE')
  ) {
    return 'negative'
  }
  if (
    v.includes('INSTABILITY') ||
    v.includes('WARNING') ||
    v.includes('DIVERGENCE') ||
    v.includes('COMPRESSION') ||
    v.includes('REVIEW REQUIRED') ||
    v.includes('STALE') ||
    v.includes('CAUTION')
  ) {
    return 'warning'
  }
  if (
    v.includes('INSUFFICIENT') ||
    v.includes('NO FORWARD') ||
    v.includes('NO_FORWARD') ||
    v.includes('WAITING') ||
    v.includes('EARLY') ||
    v.includes('PRELIMINARY') ||
    v.includes('N = 0')
  ) {
    return 'neutral'
  }
  if (
    v.includes('PASS') ||
    v.includes('ESTABLISHED') ||
    v.includes('CONSISTENT') ||
    v.includes('NO EVIDENCE OF ALPHA DECAY') ||
    v.includes('ROBUST') ||
    v.includes('LOCKED') ||
    v.includes('VERIFIED') ||
    v.includes('DECISION ELIGIBLE') ||
    v.includes('DECISION-ELIGIBLE')
  ) {
    return 'positive'
  }
  if (
    v.includes('INFORMATIVE') ||
    v.includes('EMERGING') ||
    v.includes('MODERATE') ||
    v.includes('OBSERVATION')
  ) {
    return 'info'
  }
  return 'neutral'
}

const TAG_CLASS: Record<EvidenceTone, string> = {
  positive: 'text-positive border-positive/30 bg-positive/10',
  negative: 'text-negative border-negative/30 bg-negative/10',
  warning: 'text-warning border-warning/30 bg-warning/10',
  info: 'text-info border-info/30 bg-info/10',
  neutral: 'text-secondary border-border-subtle bg-surface-elevated',
}

const TEXT_CLASS: Record<EvidenceTone, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  info: 'text-info',
  neutral: 'text-secondary',
}

/** Status pill carrying the authoritative state string. Never colour-only. */
export function EvidenceStatusTag({
  value,
  label,
  tone,
  size = 'md',
}: {
  value: string
  label?: string
  tone?: EvidenceTone
  size?: 'sm' | 'md'
}) {
  const t = tone ?? evidenceTone(value)
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border font-mono leading-none ${
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-[11px]'
      } ${TAG_CLASS[t]}`}
    >
      {label ? <span className="text-muted">{label}</span> : null}
      <span>{value}</span>
    </span>
  )
}

/** Labelled metric cell. `value` is passed through as text — no formatting policy here. */
export function EvidenceMetric({
  label,
  value,
  sub,
  tone,
  mono = true,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: EvidenceTone
  mono?: boolean
}) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p
        className={`mt-0.5 truncate text-sm ${mono ? 'font-mono tabular-nums' : ''} ${
          tone ? TEXT_CLASS[tone] : 'text-primary'
        }`}
      >
        {value}
      </p>
      {sub ? <p className="text-[10px] text-muted">{sub}</p> : null}
    </div>
  )
}

/**
 * A confidence interval drawn on a fixed authoritative scale. The numeric
 * bounds are always shown as text; the bar is a secondary cue. Renders an
 * explicit "not exposed" state when the engine did not emit the interval.
 */
export function IntervalBar({
  interval,
  point,
  min,
  max,
  unit = '',
  precision = 1,
}: {
  interval: [number, number] | null
  point?: number | null
  min: number
  max: number
  unit?: string
  precision?: number
}) {
  if (!interval) {
    return <p className="text-xs text-muted">Interval not exposed at this sample size.</p>
  }
  const span = max - min || 1
  const lo = Math.max(min, Math.min(interval[0], interval[1]))
  const hi = Math.min(max, Math.max(interval[0], interval[1]))
  const leftPct = ((lo - min) / span) * 100
  const widthPct = Math.max(((hi - lo) / span) * 100, 0.5)
  const pointPct =
    point !== undefined && point !== null
      ? ((Math.max(min, Math.min(max, point)) - min) / span) * 100
      : null

  const fmt = (n: number) =>
    `${n > 0 ? '+' : ''}${n.toFixed(precision)}${unit}`

  return (
    <div>
      <div
        className="relative h-2 w-full rounded bg-surface-elevated"
        role="img"
        aria-label={`Confidence interval from ${fmt(interval[0])} to ${fmt(
          interval[1],
        )}${
          pointPct !== null ? `, observed ${fmt(point as number)}` : ''
        }, on a ${min}${unit} to ${max}${unit} scale`}
      >
        <span
          className="absolute inset-y-0 rounded bg-info/40"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
        />
        {pointPct !== null ? (
          <span
            className="absolute inset-y-0 w-0.5 bg-primary"
            style={{ left: `${pointPct}%` }}
          />
        ) : null}
      </div>
      <p className="mt-1 font-mono text-[11px] tabular-nums text-secondary">
        [{fmt(interval[0])}, {fmt(interval[1])}]
      </p>
    </div>
  )
}

/** Signed delta from an authoritative backend comparison field. */
export function Delta({
  value,
  unit = '',
  precision = 2,
  goodWhenPositive = true,
}: {
  value: number | null | undefined
  unit?: string
  precision?: number
  goodWhenPositive?: boolean
}) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return <span className="text-muted">—</span>
  }
  const neutral = value === 0
  const good = goodWhenPositive ? value > 0 : value < 0
  const cls = neutral
    ? 'text-secondary'
    : good
      ? 'text-positive'
      : 'text-negative'
  return (
    <span className={`font-mono tabular-nums ${cls}`}>
      {value > 0 ? '+' : ''}
      {value.toFixed(precision)}
      {unit}
    </span>
  )
}

/** Truthful "nothing to show" state — distinct from a zero value. */
export function EvidenceEmpty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded border border-dashed border-border-subtle px-3 py-4 text-center text-xs text-muted">
      {children}
    </p>
  )
}

/** Short fingerprint / hash display with full value in the title. */
export function HashChip({ value, chars = 12 }: { value: string; chars?: number }) {
  if (!value) return <span className="text-muted">—</span>
  return (
    <code
      className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[11px] text-secondary"
      title={value}
    >
      {value.slice(0, chars)}…
    </code>
  )
}
