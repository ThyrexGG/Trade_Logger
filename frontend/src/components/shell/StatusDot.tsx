export type StatusTone =
  | 'positive'
  | 'negative'
  | 'warning'
  | 'info'
  | 'neutral'
  | 'blocked'

const TONE: Record<StatusTone, { dot: string; text: string }> = {
  positive: { dot: 'bg-positive', text: 'text-positive' },
  negative: { dot: 'bg-negative', text: 'text-negative' },
  warning: { dot: 'bg-warning', text: 'text-warning' },
  info: { dot: 'bg-info', text: 'text-info' },
  neutral: { dot: 'bg-neutral', text: 'text-secondary' },
  blocked: { dot: 'bg-blocked', text: 'text-negative' },
}

interface StatusDotProps {
  tone: StatusTone
  label?: string
  /** Screen-reader text when no visible label is rendered. */
  srLabel?: string
  pulse?: boolean
  className?: string
}

/**
 * Labelled status indicator. State is never conveyed by colour alone — a text
 * label (or an aria-label) always accompanies the dot.
 */
export function StatusDot({
  tone,
  label,
  srLabel,
  pulse = false,
  className = '',
}: StatusDotProps) {
  const t = TONE[tone]
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${className}`}
      role="status"
      aria-label={label ? undefined : (srLabel ?? tone)}
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${t.dot} ${
          pulse ? 'animate-pulse' : ''
        }`}
        aria-hidden="true"
      />
      {label ? (
        <span className={`text-xs font-medium ${t.text}`}>{label}</span>
      ) : null}
    </span>
  )
}
