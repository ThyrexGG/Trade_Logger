import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface LegalPageLayoutProps {
  title: string
  updated: string
  children: ReactNode
}

/**
 * Standalone reading page for Terms / Privacy — rendered outside the
 * authenticated app shell (reachable even when logged out, see the
 * `/legal/*` check in main.tsx), so it carries its own background and
 * navigation instead of relying on AppShell.
 */
export function LegalPageLayout({ title, updated, children }: LegalPageLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--color-background)] px-4 py-10 text-primary">
      <div className="mx-auto max-w-2xl">
        <Link to="/" className="text-xs text-muted underline hover:text-primary">
          ← Back to TradeLogger
        </Link>
        <h1 className="mt-4 text-2xl font-semibold text-primary">{title}</h1>
        <p className="mt-1 text-xs text-muted">Last updated {updated}</p>
        <div className="legal-prose mt-6 space-y-4 text-sm leading-relaxed text-secondary">
          {children}
        </div>
      </div>
    </div>
  )
}
