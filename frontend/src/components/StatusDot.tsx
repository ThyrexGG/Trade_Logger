type Tone = 'positive' | 'negative' | 'warning' | 'muted'

const TONE_CLASS: Record<Tone, string> = {
  positive: 'bg-positive',
  negative: 'bg-negative',
  warning: 'bg-warning',
  muted: 'bg-muted',
}

interface StatusDotProps {
  tone: Tone
  label: string
  pulse?: boolean
}

/** Small labelled status indicator dot used on the connectivity screen. */
export function StatusDot({ tone, label, pulse = false }: StatusDotProps) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`h-2.5 w-2.5 rounded-full ${TONE_CLASS[tone]} ${
          pulse ? 'animate-pulse' : ''
        }`}
      />
      <span className="text-sm text-primary">{label}</span>
    </span>
  )
}
