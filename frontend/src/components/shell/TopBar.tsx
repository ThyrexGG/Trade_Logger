import { Link } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import { isLocalFallbackBuild } from '../../lib/appMode'
import { useSyncOnOpen } from '../../lib/syncOnOpen'
import { SearchIcon } from '../../lib/icons'
import { isMac } from '../../lib/platform'
import { Tooltip } from '../common/Tooltip'
import { AccountMenu } from './AccountMenu'
import { BrandMark } from './BrandMark'
import { Breadcrumbs } from './Breadcrumbs'

interface TopBarProps {
  onOpenCommandPalette: () => void
}

/**
 * Header: where you are (breadcrumb), anything that needs your attention right
 * now (syncing / reconnecting / local mode — only when true), search, and the
 * account menu. Healthy-state status lights were removed from the header: they
 * said "Connected / Operational" all day and told a trader nothing; health now
 * shows as a small dot on the avatar and in its menu.
 */
export function TopBar({ onOpenCommandPalette }: TopBarProps) {
  const { degraded } = useAuth()
  const { syncing } = useSyncOnOpen()

  return (
    <header className="sticky top-0 z-20 flex h-[var(--tl-topbar-height)] items-center gap-3 border-b border-border-subtle bg-background/90 px-4 backdrop-blur sm:px-6">
      <Link to="/workspace/home" className="lg:hidden" aria-label="TradeLogger home">
        <BrandMark size={26} />
      </Link>

      <div className="min-w-0 flex-1 truncate">
        <Breadcrumbs />
      </div>

      {isLocalFallbackBuild() ? (
        <Tooltip label="Showing this PC's own local copy of your data while the cloud is down — it switches back automatically once the cloud is reachable again.">
          <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-2.5 py-1 text-[11px] font-bold text-warning">
            <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-warning" aria-hidden="true" />
            Offline copy
          </span>
        </Tooltip>
      ) : null}

      {syncing ? (
        <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-surface-elevated px-2.5 py-1 text-[11px] font-semibold text-secondary" role="status">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-fill" aria-hidden="true" />
          <span className="hidden sm:inline">Syncing your trades…</span>
          <span className="sm:hidden">Syncing</span>
        </span>
      ) : degraded ? (
        <Tooltip label="The server is waking up — you're seeing your last session while it reconnects in the background.">
          <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[11px] font-semibold text-warning" role="status">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-warning" aria-hidden="true" />
            Reconnecting
          </span>
        </Tooltip>
      ) : null}

      <button
        type="button"
        onClick={onOpenCommandPalette}
        className="flex h-9 shrink-0 items-center gap-2 rounded-[var(--tl-radius)] border border-border-subtle bg-surface px-2.5 text-xs font-semibold text-secondary hover:border-border hover:text-primary sm:min-w-[200px]"
        aria-label="Search pages and actions"
      >
        <SearchIcon className="h-4 w-4" />
        <span className="hidden flex-1 text-left sm:inline">Search…</span>
        <kbd className="hidden rounded border border-border-subtle bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-muted sm:inline">
          {isMac() ? '⌘' : 'Ctrl'} K
        </kbd>
      </button>

      <AccountMenu />
    </header>
  )
}
