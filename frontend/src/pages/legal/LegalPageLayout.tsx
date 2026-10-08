import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BrandLockup } from '../../components/shell/BrandMark'

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
        <div className="flex items-center justify-between gap-4 border-b border-border-subtle pb-4">
          <Link to="/" aria-label="TradeLogger home">
            <BrandLockup compact />
          </Link>
          <Link to="/" className="text-xs text-muted hover:text-primary">
            ← Back to the app
          </Link>
        </div>
        <h1 className="mt-6 text-2xl font-semibold text-primary">{title}</h1>
        <p className="mt-1 text-xs text-muted">Last updated {updated}</p>
        <div className="legal-prose mt-6 space-y-4 text-sm leading-relaxed text-secondary">
          {children}
        </div>
      </div>
    </div>
  )
}
