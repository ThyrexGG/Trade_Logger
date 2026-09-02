import { Link } from 'react-router-dom'
import { useAlerts } from '../lib/useAlerts'
import { PageContainer } from '../components/shell/PageContainer'
import { AlertsPanel, AlertsSummary } from '../components/alerts/AlertsPanel'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Price Alerts (`/workspace/alerts`). Migrated from the Streamlit "PRICE ALERTS"
 * tab. Create / list / delete price-target alerts on the authoritative
 * `price_alerts` table. Monitoring only — evaluation and notification stay in
 * the existing `auto_sync` daemon; there is no order / execution control here.
 */
export function PriceAlertsPage() {
  const { state, data, error, refreshing, refetch } = useAlerts()

  return (
    <PageContainer
      title="Price Alerts"
      description="Price-target alerts checked against live prices by the background sync daemon. Notification only — no order is ever placed."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <Link to="/workspace/market" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Market
          </Link>
          <button type="button" onClick={refetch} className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Refresh
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <OpsSafetyBanner />

        {state === 'loading' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={6} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={error ?? 'The alerts service could not be reached.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good alert list — refresh failed: {error}
              </p>
            ) : null}
            <AlertsSummary data={data} />
            <AlertsPanel data={data} onChanged={refetch} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Alerts refresh every 60s (paused while the tab is hidden) to pick up
          daemon-side <code>TRIGGERED</code> transitions. Not exposed by this API:
          alert editing (delete + recreate instead), per-account alerts, and the
          custom notification-rules engine (still Streamlit-only).
        </p>
      </div>
    </PageContainer>
  )
}
