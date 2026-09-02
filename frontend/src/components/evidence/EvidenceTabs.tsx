import { NavLink } from 'react-router-dom'

const TABS = [
  { to: '/evidence', label: 'Command Center', end: true },
  { to: '/evidence/forward', label: 'Forward', end: false },
  { to: '/evidence/statistics', label: 'Statistics', end: false },
  { to: '/evidence/governance', label: 'Governance', end: false },
]

/** Segmented navigation shared by every evidence route. */
export function EvidenceTabs() {
  return (
    <nav
      aria-label="Evidence sections"
      className="flex flex-wrap gap-1 rounded-lg border border-border bg-surface p-1"
    >
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              isActive
                ? 'bg-surface-elevated text-primary'
                : 'text-secondary hover:text-primary'
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  )
}
