import { NavLink } from 'react-router-dom'
import type { Zone } from '../../lib/navigation'
import { NavigationItem } from './NavigationItem'

interface ZoneSectionProps {
  zone: Zone
  onNavigate?: () => void
}

/** A product-zone group in the sidebar: heading link + its navigation items. */
export function ZoneSection({ zone, onNavigate }: ZoneSectionProps) {
  const ZoneIcon = zone.icon
  return (
    <div className="px-2">
      <NavLink
        to={zone.path}
        end
        onClick={onNavigate}
        className={({ isActive }) =>
          [
            'flex items-center gap-2 rounded px-1.5 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors',
            isActive ? 'text-accent' : 'text-muted hover:text-secondary',
          ].join(' ')
        }
      >
        <ZoneIcon className="h-3.5 w-3.5" />
        {zone.shortLabel}
      </NavLink>
      <div className="mt-1 flex flex-col gap-0.5">
        {zone.items.map((item) => (
          <NavigationItem key={item.id} item={item} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  )
}
