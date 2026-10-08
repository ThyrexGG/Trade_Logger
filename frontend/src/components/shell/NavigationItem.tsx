import { NavLink } from 'react-router-dom'
import type { NavItem } from '../../lib/navigation'

interface NavigationItemProps {
  item: NavItem
  onNavigate?: () => void
}

/** One sidebar row. The current page gets a solid surface and an accent icon — the only accent colour in the sidebar. */
export function NavigationItem({ item, onNavigate }: NavigationItemProps) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.path}
      onClick={onNavigate}
      title={item.description}
      className={({ isActive }) =>
        [
          'group flex h-9 items-center gap-2.5 rounded-[var(--tl-radius)] px-2.5 text-[13.5px] font-semibold transition-colors',
          isActive
            ? 'bg-surface-elevated text-primary shadow-[0_0_0_1px_var(--tl-border-subtle)]'
            : 'text-secondary hover:bg-surface-elevated/60 hover:text-primary',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          <Icon className={`h-[17px] w-[17px] shrink-0 ${isActive ? 'text-accent' : 'text-muted group-hover:text-secondary'}`} />
          <span className="flex-1 truncate">{item.label}</span>
          {isActive ? <span className="h-1.5 w-1.5 rounded-full bg-accent-fill" aria-hidden="true" /> : null}
        </>
      )}
    </NavLink>
  )
}
