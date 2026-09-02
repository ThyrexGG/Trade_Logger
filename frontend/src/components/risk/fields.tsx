import { useId, type ReactNode } from 'react'

interface LabeledFieldProps {
  label: string
  hint?: string
  error?: string
  optional?: boolean
  children: (props: { id: string; describedBy: string | undefined }) => ReactNode
}

/** Label + control + inline error, wired with matching id / aria-describedby. */
export function LabeledField({
  label,
  hint,
  error,
  optional,
  children,
}: LabeledFieldProps) {
  const id = useId()
  const errId = `${id}-err`
  const hintId = `${id}-hint`
  const describedBy =
    [error ? errId : null, hint ? hintId : null].filter(Boolean).join(' ') ||
    undefined

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] uppercase tracking-wider text-muted">
        {label}
        {optional ? <span className="ml-1 normal-case text-muted">(optional)</span> : null}
      </label>
      {children({ id, describedBy })}
      {hint ? (
        <p id={hintId} className="text-[11px] text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errId} className="text-[11px] text-negative">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export const inputClass =
  'w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-sm text-primary tabular-nums placeholder:text-muted focus:outline-none focus:border-accent aria-[invalid=true]:border-negative'

interface SegmentedControlProps<T extends string> {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

/** Accessible radio-group segmented control (used for trade side). */
export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded border border-border bg-background p-0.5"
    >
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={`rounded px-3 py-1 text-xs font-semibold transition-colors ${
              active
                ? 'bg-surface-hover text-primary'
                : 'text-muted hover:text-secondary'
            }`}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
