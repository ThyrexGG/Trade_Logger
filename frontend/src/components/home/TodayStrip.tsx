import { Link } from 'react-router-dom'
import { useOpenPositions } from '../../lib/useOpenPositions'
import { useAlerts } from '../../lib/useAlerts'
import { formatPrice, formatSignedAmount } from '../../lib/format'
import { ALL_NAV_ITEMS } from '../../lib/navigation'

const MAX_ROWS = 4

function navPath(id: string): string | null {
  return ALL_NAV_ITEMS.find((n) => n.id === id)?.path ?? null
}

function isLong(direction: string): boolean {
  const d = direction.toUpperCase()
  return d.startsWith('B') || d === 'LONG'
}

/**
 * "Right now" on Home — what used to be the Command Center's live half: the
 * selected account's open positions with floating P&L, and the price alerts
 * still waiting to fire. Positions follow the account switcher; alerts are
 * price levels, not tied to an account, so all of them show.
 */
export function TodayStrip({ account }: { account: string | null }) {
  const positions = useOpenPositions()
  const alerts = useAlerts()

  const open = (positions.data?.positions ?? []).filter((p) => !account || p.account_id === account)
  const floating = open.reduce((s, p) => s + p.floating_pnl, 0)
  const active = (alerts.data?.alerts ?? []).filter((a) => a.status.toUpperCase() === 'ACTIVE')
  const positionsPath = navPath('workspace.positions')
  const alertsPath = navPath('workspace.alerts')

  return (
    <section className="mt-5 grid gap-3 md:grid-cols-2" aria-label="Right now">
      <div className="tl-home-card is-quiet">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Open positions</h2>
          {open.length ? (
            <span className={`font-mono text-sm font-semibold ${floating >= 0 ? 'text-positive' : 'text-negative'}`}>
              {formatSignedAmount(floating)} <span className="font-sans text-xs font-normal text-muted">floating</span>
            </span>
          ) : null}
        </div>
        {positions.state === 'loading' && !positions.data ? (
          <div className="mt-3 h-8 animate-pulse rounded-md bg-surface-elevated" />
        ) : positions.state === 'error' && !positions.data ? (
          <p className="mt-2 text-xs text-muted">Couldn't load positions right now.</p>
        ) : open.length === 0 ? (
          <p className="mt-2 text-sm text-secondary">Nothing open on this account.</p>
        ) : (
          <ul className="mt-2 divide-y divide-border-subtle">
            {open.slice(0, MAX_ROWS).map((p) => (
              <li key={p.position_id} className="flex items-center gap-3 py-1.5 text-sm">
                <span className={`w-10 shrink-0 text-[11px] font-semibold uppercase ${isLong(p.direction) ? 'text-positive' : 'text-negative'}`}>{p.direction}</span>
                <span className="min-w-0 flex-1 truncate font-medium text-primary">{p.symbol}</span>
                <span className="hidden font-mono text-xs text-muted sm:inline">{p.volume} lots</span>
                <span className={`w-24 text-right font-mono ${p.floating_pnl >= 0 ? 'text-positive' : 'text-negative'}`}>{formatSignedAmount(p.floating_pnl)}</span>
              </li>
            ))}
          </ul>
        )}
        {positionsPath && open.length > 0 ? (
          <Link to={positionsPath} className="mt-2 inline-block text-xs text-accent hover:underline">
            {open.length > MAX_ROWS ? `All ${open.length} positions` : 'Open Positions'} →
          </Link>
        ) : null}
      </div>

      <div className="tl-home-card is-quiet">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Price alerts</h2>
          {alerts.data ? <span className="text-xs text-muted">{active.length} waiting</span> : null}
        </div>
        {alerts.state === 'loading' && !alerts.data ? (
          <div className="mt-3 h-8 animate-pulse rounded-md bg-surface-elevated" />
        ) : alerts.state === 'error' && !alerts.data ? (
          <p className="mt-2 text-xs text-muted">Couldn't load alerts right now.</p>
        ) : active.length === 0 ? (
          <p className="mt-2 text-sm text-secondary">No alerts set.</p>
        ) : (
          <ul className="mt-2 divide-y divide-border-subtle">
            {active.slice(0, MAX_ROWS).map((a) => (
              <li key={a.id} className="flex items-center gap-3 py-1.5 text-sm">
                <span className="min-w-0 flex-1 truncate font-medium text-primary">{a.symbol}</span>
                <span className="text-xs text-muted">{a.condition === 'ABOVE' ? 'above' : 'below'}</span>
                <span className="w-24 text-right font-mono text-primary">{formatPrice(a.target_price)}</span>
              </li>
            ))}
          </ul>
        )}
        {alertsPath ? (
          <Link to={alertsPath} className="mt-2 inline-block text-xs text-accent hover:underline">
            {active.length ? 'Manage alerts' : 'Set an alert'} →
          </Link>
        ) : null}
      </div>
    </section>
  )
}
