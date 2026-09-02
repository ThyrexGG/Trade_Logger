import type { ReactNode } from 'react'
export { SectionCard, SectionError, SkeletonRows } from '../intelligence/primitives'
export { HashChip } from '../evidence/primitives'

export type OpsTone = 'positive' | 'negative' | 'warning' | 'info' | 'neutral'

const TAG: Record<OpsTone, string> = {
  positive: 'text-positive border-positive/30 bg-positive/10',
  negative: 'text-negative border-negative/30 bg-negative/10',
  warning: 'text-warning border-warning/30 bg-warning/10',
  info: 'text-info border-info/30 bg-info/10',
  neutral: 'text-secondary border-border-subtle bg-surface-elevated',
}
const TEXT: Record<OpsTone, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  info: 'text-info',
  neutral: 'text-secondary',
}

/** Presentation-only tone for an authoritative operational-status string. */
export function opsTone(value: string | null | undefined): OpsTone {
  const v = (value || '').toUpperCase()
  if (
    v.includes('REJECT') || v.includes('FAIL') || v.includes('ERROR') ||
    v.includes('BLOCK') || v.includes('HALT') || v.includes('UNKNOWN') ||
    v.includes('DISCONNECT') || v.includes('LOSS')
  ) {
    return 'negative'
  }
  if (
    v.includes('DEGRADED') || v.includes('STALE') || v.includes('STOPPED') ||
    v.includes('PENDING') || v.includes('WARN') || v.includes('SHADOW')
  ) {
    return 'warning'
  }
  if (
    v.includes('HEALTHY') || v.includes('FILLED') || v.includes('RECONCILED') ||
    v.includes('CONNECTED') || v.includes('OK') || v.includes('WIN') ||
    v.includes('PASS')
  ) {
    return 'positive'
  }
  if (v.includes('PAPER') || v.includes('LIVE') || v.includes('INFO')) return 'info'
  return 'neutral'
}

export function OpsStatusTag({
  value,
  tone,
  size = 'md',
}: {
  value: string
  tone?: OpsTone
  size?: 'sm' | 'md'
}) {
  const t = tone ?? opsTone(value)
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

export function OpsMetric({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: OpsTone
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

/** Distinguishes "empty dataset" from "not exposed" — both truthful, different. */
export function OpsUnavailable({ children }: { children: ReactNode }) {
  return (
    <p className="rounded border border-dashed border-border-subtle px-3 py-5 text-center text-xs text-muted">
      {children}
    </p>
  )
}

/** Operational read-only safety strip. */
export function OpsSafetyBanner({
  broker = 'BLOCKED',
  automationDisabled = true,
}: {
  broker?: string
  automationDisabled?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-blocked/30 bg-blocked/10 px-3 py-2 text-[11px]">
      <span className="font-mono font-semibold uppercase tracking-wider text-blocked">
        Operational · Read-Only
      </span>
      <span className="text-secondary">
        Live automation {automationDisabled ? 'DISABLED' : 'ENABLED'}
      </span>
      <span className="text-secondary">·</span>
      <span className="text-secondary">Broker transmission {broker}</span>
    </div>
  )
}

/** Boolean check rendered as text + colour (never colour alone). */
export function CheckRow({
  label,
  ok,
  okText = 'OK',
  badText = 'ATTENTION',
  neutralText = 'not reported',
}: {
  label: string
  ok: boolean | null | undefined
  okText?: string
  badText?: string
  neutralText?: string
}) {
  const tone: OpsTone = ok === null || ok === undefined ? 'neutral' : ok ? 'positive' : 'negative'
  const text = ok === null || ok === undefined ? neutralText : ok ? okText : badText
  return (
    <div className="flex items-baseline justify-between border-b border-border-subtle/60 py-1.5 last:border-0">
      <span className="text-xs text-secondary">{label}</span>
      <span className={`font-mono text-xs ${TEXT[tone]}`}>{text}</span>
    </div>
  )
}
