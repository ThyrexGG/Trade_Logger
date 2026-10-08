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
 * A beginner's note under the page title: one line saying what the page is
 * for, with "How it works" to expand the steps. It used to be a large box at
 * the top of every page, pushing the actual content down; now it costs one
 * line until you ask for more. "Hide" removes it for that page (remembered
 * per device) and "What is this page?" brings it back.
 */
export function PageGuide({
  id,
  title,
  children,
  steps,
}: {
  id: string
  title: string
  children?: ReactNode
  steps?: ReactNode[]
}) {
  const [hidden, setHidden] = useState(() => loadHidden(id))
  const [open, setOpen] = useState(false)
  const hasMore = Boolean(children) || Boolean(steps && steps.length)

  function hide(next: boolean) {
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
      <button type="button" onClick={() => hide(false)} className="mb-4 text-xs font-semibold text-muted underline-offset-2 hover:text-accent hover:underline">
        What is this page?
      </button>
    )
  }

  return (
    <aside className="tl-guide mb-5" aria-label="About this page">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="min-w-0 flex-1 text-sm font-semibold text-primary">{title}</p>
        <div className="flex shrink-0 items-center gap-1">
          {hasMore ? (
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="tl-btn tl-btn--ghost tl-btn--sm">
              {open ? 'Less' : 'How it works'}
            </button>
          ) : null}
          <button type="button" onClick={() => hide(true)} className="tl-btn tl-btn--ghost tl-btn--sm">
            Hide
          </button>
        </div>
      </div>
      {open ? (
        <div className="tl-fade-in mt-2 max-w-3xl space-y-2 text-sm leading-relaxed text-secondary">
          {children ? <div>{children}</div> : null}
          {steps && steps.length ? (
            <ol className="space-y-1.5">
              {steps.map((s, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent-soft font-mono text-[11px] font-bold text-accent">{i + 1}</span>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
          ) : null}
        </div>
      ) : null}
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
        <span className="font-semibold text-primary">{summary}</span>
        {hint ? <span className="text-xs text-muted">{hint}</span> : null}
      </summary>
      <div className="mt-4 space-y-4">{children}</div>
    </details>
  )
}
