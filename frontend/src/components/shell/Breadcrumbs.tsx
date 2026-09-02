import { Link, useLocation } from 'react-router-dom'
import { getBreadcrumbs } from '../../lib/navigation'
import { ChevronRightIcon } from '../../lib/icons'

/** Lightweight route-derived breadcrumb trail, e.g. Research / Intelligence. */
export function Breadcrumbs() {
  const { pathname } = useLocation()
  const crumbs = getBreadcrumbs(pathname)

  if (crumbs.length === 0) {
    return <span className="text-sm text-muted">TradeLogger</span>
  }

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-1.5 text-sm">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1
          return (
            <li key={crumb.path} className="flex items-center gap-1.5">
              {i > 0 ? (
                <ChevronRightIcon className="h-3.5 w-3.5 text-muted" />
              ) : null}
              {isLast ? (
                <span className="font-medium text-primary" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link
                  to={crumb.path}
                  className="text-secondary hover:text-primary"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
