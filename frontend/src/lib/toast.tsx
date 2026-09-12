import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

export type ToastKind = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

interface ToastContextValue {
  /** Push a toast of a given kind. Prefer the kind-specific helpers below. */
  push: (kind: ToastKind, message: string) => void
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const DURATION_MS: Record<ToastKind, number> = { success: 3500, error: 6000, info: 4000 }
/** Cap the stack so a burst of actions doesn't wall off the screen. */
const MAX_VISIBLE = 4

let nextId = 1

/**
 * One shared, animated toast stack for the whole app — replaces the
 * scattered per-panel "flash" / inline success-or-error banner pattern.
 * Mounted once near the root (see `AppShell`); call `useToast()` from
 * anywhere to push one. Auto-dismisses (success/info sooner, errors linger
 * longer), dismissable early by hand, capped at 4 at once. CSS-only
 * animation (`.tl-toast` in index.css) — no bundle weight, no server cost,
 * and it already inherits the app's global `prefers-reduced-motion` clamp.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId++
      setToasts((prev) => [...prev, { id, kind, message }].slice(-MAX_VISIBLE))
      const timer = setTimeout(() => dismiss(id), DURATION_MS[kind])
      timers.current.set(id, timer)
    },
    [dismiss],
  )

  useEffect(() => {
    const map = timers.current
    return () => map.forEach((t) => clearTimeout(t))
  }, [])

  const value: ToastContextValue = {
    push,
    success: useCallback((m: string) => push('success', m), [push]),
    error: useCallback((m: string) => push('error', m), [push]),
    info: useCallback((m: string) => push('info', m), [push]),
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

/** Push toasts from anywhere: `const toast = useToast(); toast.success('Saved')`. */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast() must be called inside <ToastProvider> (mounted in AppShell)')
  }
  return ctx
}

const TONE: Record<ToastKind, string> = {
  success: 'border-positive/30 bg-positive/10 text-positive',
  error: 'border-negative/30 bg-negative/10 text-negative',
  info: 'border-border bg-surface-elevated text-secondary',
}
const ICON: Record<ToastKind, string> = { success: '✓', error: '✕', info: 'ℹ' }

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[]
  onDismiss: (id: number) => void
}) {
  if (toasts.length === 0) return null
  return createPortal(
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed inset-x-3 top-[calc(var(--tl-topbar-height)+0.5rem)] z-[200] flex flex-col items-stretch gap-2 sm:inset-x-auto sm:right-4 sm:items-end"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.kind === 'error' ? 'alert' : 'status'}
          className={`tl-toast pointer-events-auto flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-xs shadow-lg backdrop-blur sm:max-w-sm ${TONE[t.kind]}`}
        >
          <span className="mt-0.5 shrink-0 font-semibold" aria-hidden="true">
            {ICON[t.kind]}
          </span>
          <span className="min-w-0 flex-1 leading-snug">{t.message}</span>
          <button
            type="button"
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss"
            className="shrink-0 text-current opacity-60 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ))}
    </div>,
    document.body,
  )
}
