import { useState, type ReactNode } from 'react'

function storageKey(id: string) {
  return `tl.guide.hidden.${id}`
}

function loadHidden(id: string): boolean {
  try {
    return localStorage.getItem(storageKey(id)) === '1'
  } catch {
    return false
  }
}

/**
 * A short beginner's note at the top of a page: what the page is for, and how
 * to read it. Can be hidden once you know your way around (remembered per
 * page, per device); a small "What is this page?" link brings it back.
 */
export function PageGuide({
  id,
  title,
  children,
  steps,
}: {
  /** stable per page, e.g. "market-intelligence" */
  id: string
  /** one line: what the page is for */
  title: string
  /** a sentence or two of context */
  children?: ReactNode
  /** optional "how to use it" bullets */
  steps?: ReactNode[]
}) {
  const [hidden, setHidden] = useState(() => loadHidden(id))

  function toggle(next: boolean) {
    setHidden(next)
    try {
      if (next) localStorage.setItem(storageKey(id), '1')
      else localStorage.removeItem(storageKey(id))
    } catch {
      /* per-device convenience only */
    }
  }

  if (hidden) {
    return (
      <button type="button" onClick={() => toggle(false)} className="mb-3 text-xs text-muted underline-offset-2 hover:text-accent hover:underline">
        What is this page?
      </button>
    )
  }

  return (
    <aside className="tl-guide mb-4" aria-label="About this page">
      <div className="flex items-start gap-3">
        <span className="tl-guide-mark" aria-hidden="true">
          ?
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-primary">{title}</p>
          {children ? <div className="mt-1 max-w-3xl text-sm leading-relaxed text-secondary">{children}</div> : null}
          {steps && steps.length ? (
            <ul className="mt-2 max-w-3xl space-y-1 text-sm text-secondary">
              {steps.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-accent" aria-hidden="true">
                    •
                  </span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <button type="button" onClick={() => toggle(true)} className="shrink-0 rounded px-2 py-0.5 text-xs text-muted hover:bg-surface-hover hover:text-primary">
          Got it
        </button>
      </div>
    </aside>
  )
}

/**
 * Tucks advanced detail away behind one click. Closed by default so a
 * beginner sees the simple view first; the native <details> element keeps it
 * keyboard- and screen-reader-friendly with no extra script.
 */
export function MoreDetails({
  summary = 'Show the detailed numbers',
  hint,
  children,
  defaultOpen = false,
}: {
  summary?: string
  hint?: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details className="tl-more" open={defaultOpen}>
      <summary>
        <span className="tl-more-chevron" aria-hidden="true">
          ›
        </span>
        <span className="font-medium text-primary">{summary}</span>
        {hint ? <span className="text-xs text-muted">{hint}</span> : null}
      </summary>
      <div className="mt-4 space-y-4">{children}</div>
    </details>
  )
}
