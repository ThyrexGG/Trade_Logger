import { useState } from 'react'

/** 0–5 star rating. Click a star to set; click the same star again to clear. */
export function StarRating({
  value,
  onChange,
  disabled = false,
  size = 'sm',
}: {
  value: number | null
  onChange: (n: number) => void
  disabled?: boolean
  size?: 'sm' | 'md'
}) {
  const [hover, setHover] = useState<number | null>(null)
  const shown = hover ?? value ?? 0
  const cls = size === 'md' ? 'text-lg' : 'text-sm'
  return (
    <span className={`inline-flex items-center ${cls}`} role="radiogroup" aria-label="rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={disabled}
          onMouseEnter={() => !disabled && setHover(n)}
          onMouseLeave={() => setHover(null)}
          onClick={() => onChange(value === n ? 0 : n)}
          className={`px-0.5 leading-none transition-colors disabled:opacity-50 ${
            n <= shown ? 'text-warning' : 'text-border'
          } ${!disabled ? 'hover:text-warning' : ''}`}
          aria-label={`${n} star${n === 1 ? '' : 's'}`}
          aria-pressed={value === n}
        >
          ★
        </button>
      ))}
      {value ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(0)}
          className="ml-1 text-[10px] text-muted hover:text-negative disabled:opacity-50"
        >
          clear
        </button>
      ) : null}
    </span>
  )
}
