import { NavLink } from 'react-router-dom'
import { ZONES } from '../../lib/navigation'

/**
 * Thumb-reachable zone switcher for small screens. The sidebar drawer (hamburger)
 * still holds the full page tree; this is the fast path between the 4 zones.
 * Hidden at lg and up where the fixed sidebar takes over.
 */
export function BottomNav() {
  return (
    <nav
      aria-label="Zones"
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 backdrop-blur-xl lg:hidden"
      style={{
        paddingBottom: 'env(safe-area-inset-bottom)',
        background: 'var(--tl-glass-bg)',
        borderTop: '1px solid var(--tl-glass-border)',
      }}
    >
      {ZONES.map((zone) => {
        const Icon = zone.icon
        return (
          <NavLink
            key={zone.id}
            to={zone.path}
            className={({ isActive }) =>
              [
                'flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium',
                isActive ? 'text-accent' : 'text-muted',
              ].join(' ')
            }
          >
            <Icon className="h-5 w-5" />
            {zone.shortLabel}
          </NavLink>
        )
      })}
    </nav>
  )
}
