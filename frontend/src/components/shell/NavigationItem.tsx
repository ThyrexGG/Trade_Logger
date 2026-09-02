import { NavLink } from 'react-router-dom'
import type { NavItem } from '../../lib/navigation'

interface NavigationItemProps {
  item: NavItem
  onNavigate?: () => void
}

/** Single sidebar navigation row. Active route is marked by colour + a rail. */
export function NavigationItem({ item, onNavigate }: NavigationItemProps) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.path}
      onClick={onNavigate}
      className={({ isActive }) =>
        [
          'group flex items-center gap-2.5 rounded-md border-l-2 py-1.5 pl-2.5 pr-2 text-sm transition-colors',
          isActive
            ? 'border-accent bg-surface-hover text-primary'
            : 'border-transparent text-secondary hover:bg-surface-elevated hover:text-primary',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={
              isActive ? 'text-accent' : 'text-muted group-hover:text-secondary'
            }
          />
          <span className="flex-1 truncate">{item.label}</span>
          {item.status === 'shell' ? (
            <span
              className="rounded bg-surface px-1 text-[9px] font-semibold uppercase tracking-wide text-muted"
              title="Shell page — migration in progress"
            >
              shell
            </span>
          ) : null}
        </>
      )}
    </NavLink>
  )
}
