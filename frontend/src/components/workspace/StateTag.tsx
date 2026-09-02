type Tone = 'positive' | 'negative' | 'warning' | 'neutral'

/** Classifies an authoritative state/bias string into a display tone. */
export function toneForState(value: string): Tone {
  const v = value.toUpperCase()
  if (v.includes('BEAR')) return 'negative'
  if (v.includes('BULL') || v.includes('ENTRY') || v.includes('READY')) {
    return 'positive'
  }
  if (v.includes('WATCH') || v.includes('SETUP') || v.includes('ARM')) {
    return 'warning'
  }
  return 'neutral'
}

const TONE_CLASS: Record<Tone, string> = {
  positive: 'text-positive border-positive/30 bg-positive/10',
  negative: 'text-negative border-negative/30 bg-negative/10',
  warning: 'text-warning border-warning/30 bg-warning/10',
  neutral: 'text-secondary border-border-subtle bg-surface-elevated',
}

interface StateTagProps {
  value: string
  /** Optional prefix rendered in muted text, e.g. "4H". */
  label?: string
  className?: string
}

/**
 * Compact tag for an authoritative state string (bias, setup state). The text
 * itself carries the meaning — tone/colour is a secondary cue only.
 */
export function StateTag({ value, label, className = '' }: StateTagProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] leading-none ${TONE_CLASS[toneForState(value)]} ${className}`}
    >
      {label ? <span className="text-muted">{label}</span> : null}
      <span>{value}</span>
    </span>
  )
}
