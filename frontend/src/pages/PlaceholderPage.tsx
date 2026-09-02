import { ALL_NAV_ITEMS, ZONES } from '../lib/navigation'
import { useHealth } from '../lib/health'
import { apiStatusView } from '../lib/status'
import { PageContainer } from '../components/shell/PageContainer'
import { StatusDot } from '../components/shell/StatusDot'

interface PlaceholderPageProps {
  itemId: string
}

/**
 * Professional placeholder for a feature not yet migrated to React. Communicates
 * the feature, its zone, migration status and real backend availability.
 * Never renders fabricated data.
 */
export function PlaceholderPage({ itemId }: PlaceholderPageProps) {
  const item = ALL_NAV_ITEMS.find((i) => i.id === itemId)
  const zone = ZONES.find((z) => z.items.some((i) => i.id === itemId))
  const { state } = useHealth()
  const api = apiStatusView(state)

  if (!item || !zone) {
    return (
      <PageContainer title="Unknown page" width="standard">
        <p className="text-sm text-secondary">
          This route is not part of the navigation model.
        </p>
      </PageContainer>
    )
  }

  const Icon = item.icon

  return (
    <PageContainer
      title={item.label}
      description={zone.label}
      width="standard"
    >
      <div className="rounded-lg border border-border bg-surface p-6">
        <div className="flex items-center gap-3">
          <span className="rounded-md border border-border-subtle bg-surface-elevated p-2 text-accent">
            <Icon className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-medium text-primary">Coming next</p>
            <p className="text-xs text-muted">{item.description}</p>
          </div>
        </div>

        <p className="mt-5 text-sm leading-relaxed text-secondary">
          This workspace is being migrated to the React terminal from the
          authoritative TradeLogger backend. Until then, use the Streamlit
          reference application for this feature.
        </p>

        <dl className="mt-5 grid gap-x-6 gap-y-2 border-t border-border-subtle pt-4 text-sm sm:grid-cols-[8rem_1fr]">
          <dt className="text-muted">Zone</dt>
          <dd className="text-primary">{zone.label}</dd>

          <dt className="text-muted">Migration status</dt>
          <dd className="text-warning">Shell — not yet migrated</dd>

          <dt className="text-muted">Backend service</dt>
          <dd>
            <StatusDot tone={api.tone} label={api.label} pulse={api.pulse} />
          </dd>
        </dl>

        <p className="mt-4 text-xs text-muted">
          No data is being fabricated on this page.
        </p>
      </div>
    </PageContainer>
  )
}
