import { Link } from 'react-router-dom'
import { ZONES } from '../../lib/navigation'
import { useHealth } from '../../lib/health'
import { apiStatusView } from '../../lib/status'
import { CloseIcon } from '../../lib/icons'
import { StatusDot } from './StatusDot'
import { ZoneSection } from './ZoneSection'

interface SidebarProps {
  /** Mobile drawer open state (ignored on desktop where the sidebar is fixed). */
  open: boolean
  onClose: () => void
}

/** Persistent navigation sidebar. Fixed on desktop, off-canvas drawer below lg. */
export function Sidebar({ open, onClose }: SidebarProps) {
  const { state, data } = useHealth()
  const api = apiStatusView(state)

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={`fixed inset-0 z-30 bg-black/60 lg:hidden ${
          open ? 'block' : 'hidden'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        aria-label="Primary navigation"
        className={[
          'fixed inset-y-0 left-0 z-40 flex w-[var(--tl-sidebar-width)] flex-col border-r border-border-subtle bg-surface',
          'transition-transform duration-200 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        <div className="flex h-[var(--tl-topbar-height)] shrink-0 items-center justify-between border-b border-border-subtle px-3">
          <Link
            to="/workspace"
            onClick={onClose}
            className="flex items-center gap-2"
          >
            <span className="h-2.5 w-2.5 rounded-full bg-accent" />
            <span className="font-mono text-sm font-semibold tracking-wide text-primary">
              TradeLogger
            </span>
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted hover:bg-surface-hover hover:text-primary lg:hidden"
            aria-label="Close navigation"
          >
            <CloseIcon />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-3">
          <div className="flex flex-col gap-4">
            {ZONES.map((zone) => (
              <ZoneSection key={zone.id} zone={zone} onNavigate={onClose} />
            ))}
          </div>
        </nav>

        <div className="shrink-0 space-y-1.5 border-t border-border-subtle px-3 py-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-muted">
              API
            </span>
            <StatusDot tone={api.tone} label={api.label} pulse={api.pulse} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-muted">
              Safety
            </span>
            <span className="font-mono text-[11px] font-semibold text-negative">
              {data?.live_broker_transmission ?? 'BLOCKED'}
            </span>
          </div>
        </div>
      </aside>
    </>
  )
}
