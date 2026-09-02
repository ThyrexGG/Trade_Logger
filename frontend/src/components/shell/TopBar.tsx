import { useHealth } from '../../lib/health'
import { apiStatusView, systemStatusView } from '../../lib/status'
import { MenuIcon, SearchIcon } from '../../lib/icons'
import { isMac } from '../../lib/platform'
import { Breadcrumbs } from './Breadcrumbs'
import { StatusDot } from './StatusDot'

interface TopBarProps {
  onOpenSidebar: () => void
  onOpenCommandPalette: () => void
}

/** Persistent header: breadcrumb (left), live status + command palette (right). */
export function TopBar({ onOpenSidebar, onOpenCommandPalette }: TopBarProps) {
  const { state, data } = useHealth()
  const api = apiStatusView(state)
  const system = systemStatusView(state)
  const safety = data?.live_broker_transmission ?? 'BLOCKED'

  return (
    <header className="sticky top-0 z-20 flex h-[var(--tl-topbar-height)] items-center gap-3 border-b border-border-subtle bg-surface/95 px-3 backdrop-blur sm:px-4">
      <button
        type="button"
        onClick={onOpenSidebar}
        className="rounded p-1.5 text-muted hover:bg-surface-hover hover:text-primary lg:hidden"
        aria-label="Open navigation"
      >
        <MenuIcon />
      </button>

      <div className="min-w-0 flex-1 truncate">
        <Breadcrumbs />
      </div>

      <div className="hidden items-center gap-4 md:flex">
        <span className="flex items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wider text-muted">
            API
          </span>
          <StatusDot tone={api.tone} label={api.label} pulse={api.pulse} />
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wider text-muted">
            System
          </span>
          <StatusDot
            tone={system.tone}
            label={system.label}
            pulse={system.pulse}
          />
        </span>
      </div>

      <span
        className="flex items-center gap-1.5 rounded border border-negative/40 bg-negative/10 px-2 py-1"
        title="Live broker transmission is permanently blocked (fail-closed)"
      >
        <span aria-hidden="true">🔒</span>
        <span className="font-mono text-[11px] font-semibold text-negative">
          LIVE {safety}
        </span>
      </span>

      <button
        type="button"
        onClick={onOpenCommandPalette}
        className="flex items-center gap-2 rounded border border-border bg-surface-elevated px-2.5 py-1.5 text-xs text-secondary hover:border-border-subtle hover:text-primary"
        aria-label="Open command palette"
      >
        <SearchIcon className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Search</span>
        <kbd className="rounded bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted">
          {isMac() ? '⌘' : 'Ctrl'} K
        </kbd>
      </button>
    </header>
  )
}
