import { useEffect, useState, type ReactNode } from 'react'
import { ageSeconds, timeAgo } from '../../lib/format'

export type IntelTone = 'positive' | 'negative' | 'warning' | 'neutral'

/** Classifies an authoritative intelligence state string into a display tone. */
export function toneForIntel(value: string): IntelTone {
  const v = (value || '').toUpperCase()
  if (
    v.includes('BEAR') ||
    v.includes('CONFLICT') ||
    v.includes('RISK_OFF') ||
    v.includes('RISK OFF') ||
    v.includes('WITHHELD') ||
    v.includes('DIVERG')
  ) {
    return 'negative'
  }
  if (
    v.includes('BULL') ||
    v.includes('RISK_ON') ||
    v.includes('RISK ON') ||
    v.includes('ALIGNED') ||
    v.includes('EXPANSION')
  ) {
    return 'positive'
  }
  if (v.includes('MIXED') || v.includes('TRANSITION') || v.includes('WATCH')) {
    return 'warning'
  }
  return 'neutral'
}

const TONE_TAG: Record<IntelTone, string> = {
  positive: 'text-positive border-positive/30 bg-positive/10',
  negative: 'text-negative border-negative/30 bg-negative/10',
  warning: 'text-warning border-warning/30 bg-warning/10',
  neutral: 'text-secondary border-border-subtle bg-surface-elevated',
}

export function IntelTag({
  value,
  label,
  tone,
  className = '',
}: {
  value: string
  label?: string
  tone?: IntelTone
  className?: string
}) {
  const t = tone ?? toneForIntel(value)
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] leading-none ${TONE_TAG[t]} ${className}`}
    >
      {label ? <span className="text-muted">{label}</span> : null}
      <span>{value}</span>
    </span>
  )
}

export function qualityTone(score: number): IntelTone {
  if (score >= 85) return 'positive'
  if (score >= 70) return 'warning'
  return 'negative'
}

const TONE_TEXT: Record<IntelTone, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  neutral: 'text-secondary',
}

/** Data-quality score + authoritative rating text. Never colour-only. */
export function DataQualityBadge({
  score,
  rating,
  compact = false,
}: {
  score: number
  rating?: string
  compact?: boolean
}) {
  const tone = qualityTone(score)
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className={`font-mono text-sm tabular-nums ${TONE_TEXT[tone]}`}>
        {score}
        <span className="text-muted">/100</span>
      </span>
      {rating && !compact ? (
        <span className="text-[11px] uppercase tracking-wide text-muted">
          {rating}
        </span>
      ) : null}
    </span>
  )
}

const STALE_AFTER_S = 120

/** Relative age from an authoritative ISO timestamp. Never synthesized. */
export function FreshnessBadge({
  timestamp,
  cached = false,
  label = 'as of',
}: {
  timestamp: string | undefined
  cached?: boolean
  label?: string
}) {
  const [, tick] = useState(0)
  useEffect(() => {
    const t = window.setInterval(() => tick((n) => n + 1), 5000)
    return () => window.clearInterval(t)
  }, [])

  const age = ageSeconds(timestamp)
  const rel = timeAgo(timestamp)
  if (!rel) return null
  const stale = age !== null && age > STALE_AFTER_S

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] ${
        stale ? 'text-stale' : 'text-muted'
      }`}
      title={timestamp ? new Date(timestamp).toLocaleString() : undefined}
    >
      <span>
        {stale ? 'Stale · ' : `${label} `}
        {rel}
      </span>
      {cached ? (
        <span className="rounded bg-surface-elevated px-1 text-muted">cached</span>
      ) : null}
    </span>
  )
}

/**
 * Horizontal score bar on a fixed authoritative scale (default -100..+100),
 * zero-centred. The numeric value is always shown as text.
 */
export function ScoreBar({
  score,
  min = -100,
  max = 100,
  size = 'md',
}: {
  score: number
  min?: number
  max?: number
  size?: 'sm' | 'md'
}) {
  const clamped = Math.max(min, Math.min(max, score))
  const zeroPct = ((0 - min) / (max - min)) * 100
  const valuePct = ((clamped - min) / (max - min)) * 100
  const left = Math.min(zeroPct, valuePct)
  const width = Math.abs(valuePct - zeroPct)
  const positive = clamped >= 0
  const height = size === 'sm' ? 'h-1.5' : 'h-2'

  return (
    <div className="flex items-center gap-2">
      <div
        className={`relative w-full ${height} rounded bg-surface-elevated`}
        role="img"
        aria-label={`Score ${score.toFixed(1)} on a ${min} to ${max} scale`}
      >
        <span
          className="absolute top-0 bottom-0 w-px bg-border"
          style={{ left: `${zeroPct}%` }}
        />
        <span
          className={`absolute top-0 bottom-0 rounded ${
            positive ? 'bg-positive/70' : 'bg-negative/70'
          }`}
          style={{ left: `${left}%`, width: `${Math.max(width, 0.5)}%` }}
        />
      </div>
      <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums text-primary">
        {score > 0 ? '+' : ''}
        {score.toFixed(1)}
      </span>
    </div>
  )
}

export function SectionCard({
  title,
  action,
  children,
  className = '',
}: {
  title: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      aria-label={title}
      className={`rounded-lg border border-border bg-surface ${className}`}
    >
      <header className="flex items-center justify-between gap-2 border-b border-border-subtle px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-secondary">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-4">{children}</div>
    </section>
  )
}

export function SectionError({
  message,
  onRetry,
}: {
  message: string | null
  onRetry: () => void
}) {
  return (
    <div className="text-sm">
      <p className="text-negative">Section unavailable</p>
      {message ? <p className="mt-1 text-xs text-muted">{message}</p> : null}
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
      >
        Retry
      </button>
    </div>
  )
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 w-full rounded bg-surface-elevated" />
      ))}
    </div>
  )
}
