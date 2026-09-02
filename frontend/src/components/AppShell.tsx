import type { ReactNode } from 'react'

interface AppShellProps {
  children: ReactNode
}

/**
 * Minimal application shell for the React foundation. Later stages fill this
 * with navigation zones; for now it is a header + centered content column.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-full flex-col bg-background text-primary">
      <header className="border-b border-border-subtle bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-accent" />
            <span className="font-mono text-sm font-semibold tracking-wide">
              TradeLogger React
            </span>
          </div>
          <span className="rounded border border-negative/40 px-2 py-0.5 font-mono text-[11px] text-negative">
            LIVE TRANSMISSION BLOCKED
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">{children}</main>

      <footer className="border-t border-border-subtle bg-surface">
        <div className="mx-auto w-full max-w-5xl px-6 py-3 text-xs text-muted">
          Foundation shell · React 19 + Vite + Tailwind · FastAPI adapter →
          authoritative Python engines
        </div>
      </footer>
    </div>
  )
}
