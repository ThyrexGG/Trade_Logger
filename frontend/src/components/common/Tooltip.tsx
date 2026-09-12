import { useCallback, useEffect, useId, useRef, useState, type ReactElement } from 'react'
import { createPortal } from 'react-dom'

const PANEL_MAX_W = 220
const SHOW_DELAY_MS = 250

/**
 * A small, consistent hover/focus tooltip for anything — an icon-only button,
 * a nav item, a stat label. Portal-rendered with `position: fixed` so it's
 * never clipped by an ancestor `overflow: hidden` or stuck behind a sibling,
 * and auto-flips above/below depending on available space.
 *
 * Prefer this over a bare `title="…"` attribute: the native browser tooltip
 * is slow to appear, unstyled, and invisible to touch — this one is instant
 * on focus (keyboard users), themed, and still keyboard/screen-reader wired
 * via `aria-describedby`.
 *
 * Wraps its child in an inline-flex span (no visual footprint beyond that)
 * and reads hover/focus from it, so it works with a button, a link, or any
 * single element — including one that's `disabled` (a native `disabled`
 * button fires no mouse events, so disabled controls still need their own
 * `title`/reason text if a tooltip must show there).
 */
export function Tooltip({
  label,
  children,
  disabled = false,
}: {
  label: string
  children: ReactElement
  /** Skip rendering the tooltip entirely (e.g. it's redundant with visible text). */
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; placement: 'top' | 'bottom' }>()
  const id = useId()
  const wrapRef = useRef<HTMLSpanElement>(null)
  const showTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const place = useCallback(() => {
    const el = wrapRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const spaceBelow = window.innerHeight - r.bottom
    const placement: 'top' | 'bottom' = spaceBelow < 100 && r.top > 100 ? 'top' : 'bottom'
    let left = r.left + r.width / 2 - PANEL_MAX_W / 2
    left = Math.max(8, Math.min(left, window.innerWidth - PANEL_MAX_W - 8))
    setPos({ top: placement === 'bottom' ? r.bottom + 6 : r.top - 6, left, placement })
  }, [])

  const show = useCallback(
    (immediate: boolean) => {
      clearTimeout(hideTimer.current)
      clearTimeout(showTimer.current)
      if (immediate) {
        place()
        setOpen(true)
      } else {
        showTimer.current = setTimeout(() => {
          place()
          setOpen(true)
        }, SHOW_DELAY_MS)
      }
    },
    [place],
  )

  const hide = useCallback(() => {
    clearTimeout(showTimer.current)
    clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setOpen(false), 60)
  }, [])

  useEffect(() => {
    if (!open) return
    const onScroll = () => setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  useEffect(
    () => () => {
      clearTimeout(showTimer.current)
      clearTimeout(hideTimer.current)
    },
    [],
  )

  if (disabled || !label) return children

  return (
    <span
      ref={wrapRef}
      className="inline-flex"
      aria-describedby={open ? id : undefined}
      onMouseEnter={() => show(false)}
      onMouseLeave={hide}
      onFocus={() => show(true)}
      onBlur={hide}
    >
      {children}
      {open && pos
        ? createPortal(
            <span
              id={id}
              role="tooltip"
              style={{
                position: 'fixed',
                top: pos.top,
                left: pos.left,
                maxWidth: PANEL_MAX_W,
                transform: pos.placement === 'top' ? 'translateY(-100%)' : undefined,
              }}
              className="z-[100] whitespace-normal rounded-md border border-border bg-surface-elevated px-2 py-1 text-[11px] font-normal leading-snug text-secondary shadow-lg"
            >
              {label}
            </span>,
            document.body,
          )
        : null}
    </span>
  )
}
