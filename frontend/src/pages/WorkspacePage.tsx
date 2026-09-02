import { Link } from 'react-router-dom'
import { ZONES } from '../lib/navigation'
import { useHealth } from '../lib/health'
import { apiStatusView } from '../lib/status'
import { ChevronRightIcon } from '../lib/icons'
import { PageContainer } from '../components/shell/PageContainer'
import { StatusDot } from '../components/shell/StatusDot'

const workspaceZone = ZONES.find((z) => z.id === 'workspace')!

/**
 * `/workspace` landing — the shell entry into the trading zone. Navigation
 * entry points plus real /api/health info. No prices, PnL, trades or signals.
 */
export function WorkspacePage() {
  const { state, data, lastChecked } = useHealth()
  const api = apiStatusView(state)

  return (
    <PageContainer
      title="Trading Workspace"
      description="Primary market monitoring workspace. Feature areas below are being migrated from the authoritative backend."
    >
      <section
        aria-label="Backend status"
        className="mb-6 grid gap-3 rounded-lg border border-border bg-surface p-4 sm:grid-cols-3"
      >
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            API connection
          </p>
          <div className="mt-1">
            <StatusDot tone={api.tone} label={api.label} pulse={api.pulse} />
          </div>
          <p className="mt-1 text-[11px] text-muted">
            {lastChecked
              ? `Checked ${lastChecked.toLocaleTimeString()}`
              : 'Checking…'}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Backend engine
          </p>
          <p className="mt-1 text-sm text-primary">
            {data ? data.app_name : '—'}
          </p>
          <p className="mt-1 text-[11px] text-muted">
            {data ? `v${data.version}` : 'Unavailable'}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Safety gate
          </p>
          <p className="mt-1 font-mono text-sm text-negative">
            {data?.live_broker_transmission ?? 'BLOCKED'}
          </p>
          <p className="mt-1 text-[11px] text-muted">
            Automation {data ? String(data.automation_enabled) : 'off'}
          </p>
        </div>
      </section>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
        Feature areas
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {workspaceZone.items.map((item) => {
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
                  <span className="text-sm font-medium text-primary">
                    {item.label}
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
