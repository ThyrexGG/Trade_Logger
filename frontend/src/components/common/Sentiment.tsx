import type { ReactNode } from 'react'
import {
  classifySentiment,
  numberSentiment,
  toneChip,
  toneText,
  type Sentiment,
  type SentimentTone,
} from '../../lib/sentiment'

function resolve(
  value: string | number | null | undefined,
  hint?: SentimentTone,
  deadband?: number,
): Sentiment {
  return typeof value === 'number'
    ? numberSentiment(value, deadband)
    : classifySentiment(value, hint)
}

/**
 * A directional value as a coloured chip with an arrow — the same look
 * everywhere for bull/bear, hawkish/dovish, beat/miss, tracking/diverging, …
 * Pass the raw backend string as `value`; `label` overrides the shown text.
 */
export function SentimentBadge({
  value,
  label,
  hint,
  deadband,
  size = 'sm',
}: {
  value: string | number | null | undefined
  label?: ReactNode
  hint?: SentimentTone
  deadband?: number
  size?: 'sm' | 'md'
}) {
  const s = resolve(value, hint, deadband)
  const text =
    label ??
    (typeof value === 'string' && value ? value.replace(/_/g, ' ') : s.word)
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border font-mono leading-none ${
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-[11px]'
      } ${toneChip(s.tone)}`}
    >
      <span aria-hidden="true">{s.arrow}</span>
      {text}
    </span>
  )
}

/** Inline coloured text + arrow, no chip — for use inside a sentence or a cell. */
export function SentimentText({
  value,
  label,
  hint,
  deadband,
  arrow = true,
  className = '',
}: {
  value: string | number | null | undefined
  label?: ReactNode
  hint?: SentimentTone
  deadband?: number
  arrow?: boolean
  className?: string
}) {
  const s = resolve(value, hint, deadband)
  const text =
    label ??
    (typeof value === 'string' && value ? value.replace(/_/g, ' ') : typeof value === 'number' ? value : s.word)
  return (
    <span className={`${toneText(s.tone)} ${className}`}>
      {arrow ? <span aria-hidden="true">{s.arrow} </span> : null}
      {text}
    </span>
  )
}

/** A tiny fixed "what the colours mean" strip. */
export function ColorLegend({
  items,
  className = '',
}: {
  items?: { tone: SentimentTone; label: string }[]
  className?: string
}) {
  const list = items ?? [
    { tone: 'up' as const, label: 'positive / bullish' },
    { tone: 'down' as const, label: 'negative / bearish' },
    { tone: 'caution' as const, label: 'mixed / watch' },
    { tone: 'flat' as const, label: 'neutral / n-a' },
  ]
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted ${className}`}>
      {list.map((i) => (
        <span key={i.label} className="flex items-center gap-1">
          <span className={`inline-block h-2 w-2 rounded-full ${
            i.tone === 'up' ? 'bg-positive' : i.tone === 'down' ? 'bg-negative' : i.tone === 'caution' ? 'bg-warning' : 'bg-muted'
          }`} />
          {i.label}
        </span>
      ))}
    </div>
  )
}
