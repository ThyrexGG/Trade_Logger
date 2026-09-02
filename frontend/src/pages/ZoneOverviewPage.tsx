import { Link } from 'react-router-dom'
import { ZONES } from '../lib/navigation'
import { ChevronRightIcon } from '../lib/icons'
import { PageContainer } from '../components/shell/PageContainer'

interface ZoneOverviewPageProps {
  zoneId: string
}

/**
 * Landing page for a product zone: lists its areas as navigation entry points.
 * Structural only — no metrics, no data.
 */
export function ZoneOverviewPage({ zoneId }: ZoneOverviewPageProps) {
  const zone = ZONES.find((z) => z.id === zoneId)
  if (!zone) {
    return (
      <PageContainer title="Unknown zone" width="standard">
        <p className="text-sm text-secondary">No such zone.</p>
      </PageContainer>
    )
  }

  return (
    <PageContainer title={zone.label} description={zone.tagline}>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {zone.items.map((item) => {
          const Icon = item.icon
          return (
            <li key={item.id}>
              <Link
                to={item.path}
                className="flex h-full items-start gap-3 rounded-lg border border-border bg-surface p-4 transition-colors hover:border-border-subtle hover:bg-surface-elevated"
              >
                <span className="mt-0.5 shrink-0 rounded-md border border-border-subtle bg-surface-elevated p-2 text-accent">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-primary">
                      {item.label}
                    </span>
                    {item.status === 'shell' ? (
                      <span className="rounded bg-surface px-1 text-[9px] font-semibold uppercase tracking-wide text-muted">
                        shell
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 block text-xs text-muted">
                    {item.description}
                  </span>
                </span>
                <ChevronRightIcon className="mt-1 h-4 w-4 shrink-0 text-muted" />
              </Link>
            </li>
          )
        })}
      </ul>
    </PageContainer>
  )
}
