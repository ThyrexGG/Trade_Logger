import { Link } from 'react-router-dom'
import { ZONES } from '../../lib/navigation'
import { CloseIcon } from '../../lib/icons'
import { BrandLockup } from './BrandMark'
import { ZoneSection } from './ZoneSection'

interface SidebarProps {
  /** Mobile drawer open state (ignored on desktop where the sidebar is fixed). */
  open: boolean
  onClose: () => void
}

/**
 * Primary navigation. Fixed on desktop; an off-canvas drawer below lg (opened
 * from the bottom bar's "More"). Settings sits apart at the bottom — it's
 * visited rarely, so it shouldn't compete with the daily groups above.
 */
export function Sidebar({ open, onClose }: SidebarProps) {
  const daily = ZONES.filter((z) => z.id !== 'settings')
  const settings = ZONES.find((z) => z.id === 'settings')

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/55 lg:hidden ${open ? 'block' : 'hidden'}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        aria-label="Primary navigation"
        className={[
          'fixed inset-y-0 left-0 z-40 flex w-[var(--tl-sidebar-width)] flex-col border-r border-border-subtle bg-background',
          'transition-transform duration-200 lg:translate-x-0',
          open ? 'translate-x-0 shadow-[var(--tl-shadow-pop)]' : '-translate-x-full',
        ].join(' ')}
      >
        <div className="flex h-[var(--tl-topbar-height)] shrink-0 items-center justify-between px-5">
          <Link to="/workspace/home" onClick={onClose} aria-label="TradeLogger home">
            <BrandLockup />
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="tl-btn tl-btn--ghost tl-btn--sm lg:hidden"
            aria-label="Close navigation"
          >
            <CloseIcon />
          </button>
        </div>

        <nav className="flex flex-1 flex-col overflow-y-auto pb-4 pt-3" aria-label="Pages">
          <div className="flex flex-col gap-5">
            {daily.map((zone) => (
              <ZoneSection key={zone.id} zone={zone} onNavigate={onClose} />
            ))}
          </div>
          {settings ? (
            <div className="mt-auto border-t border-border-subtle pt-4">
              <ZoneSection zone={settings} onNavigate={onClose} />
            </div>
          ) : null}
        </nav>
      </aside>
    </>
  )
}
