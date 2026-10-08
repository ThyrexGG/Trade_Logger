import { NavLink, useLocation } from 'react-router-dom'
import { ZONES, findZoneByPath } from '../../lib/navigation'
import { DotsIcon } from '../../lib/icons'

/**
 * Phone navigation: the four daily groups as thumb-sized tabs, each opening
 * that group's main page, plus "More" for the full page list (the drawer).
 * A tab stays lit for every page in its group, not just the first.
 * Hidden at lg and up, where the sidebar takes over.
 */
export function BottomNav({ onOpenMore }: { onOpenMore: () => void }) {
  const { pathname } = useLocation()
  const activeZone = findZoneByPath(pathname)?.id
  const daily = ZONES.filter((z) => z.id !== 'settings').slice(0, 4)

  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-0 bottom-0 z-30 grid border-t border-border-subtle bg-background/95 backdrop-blur lg:hidden"
      style={{ gridTemplateColumns: `repeat(${daily.length + 1}, minmax(0, 1fr))`, paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {daily.map((zone) => {
        const Icon = zone.icon
        const on = activeZone === zone.id
        return (
          <NavLink
            key={zone.id}
            to={zone.path}
            aria-current={on ? 'page' : undefined}
            className={`flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-semibold ${on ? 'text-primary' : 'text-muted'}`}
          >
            <span className={`grid h-7 w-12 place-items-center rounded-full transition-colors ${on ? 'bg-accent-soft' : ''}`}>
              <Icon className={`h-[19px] w-[19px] ${on ? 'text-accent' : ''}`} />
            </span>
            {zone.shortLabel}
          </NavLink>
        )
      })}
      <button
        type="button"
        onClick={onOpenMore}
        className={`flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-semibold ${activeZone === 'settings' ? 'text-primary' : 'text-muted'}`}
      >
        <span className="grid h-7 w-12 place-items-center rounded-full">
          <DotsIcon className="h-[19px] w-[19px]" />
        </span>
        More
      </button>
    </nav>
  )
}
