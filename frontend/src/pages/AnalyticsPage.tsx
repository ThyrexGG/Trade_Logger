import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAnalytics } from '../lib/useAnalytics'
import type { AnalyticsQuery } from '../types/analytics'
import { PageContainer } from '../components/shell/PageContainer'
import { AnalyticsControls } from '../components/analytics/AnalyticsControls'
import { AnalyticsView } from '../components/analytics/AnalyticsView'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Analytics (`/workspace/analytics`). Migrated from the Streamlit
 * "ANALYTICS & OVERVIEW" tab. Account / symbol / date-filtered trading
 * performance over the closed-trade journal. Read-only — every metric comes
 * from the backend `analytics.calculate_performance_metrics`.
 */
export function AnalyticsPage() {
  const [query, setQuery] = useState<AnalyticsQuery>({ initial_balance: 10000 })
  const { state, data, error, refreshing, refetch } = useAnalytics(query)

  const available = useMemo(
    () => data?.available ?? { accounts: [], symbols: [], date_min: null, date_max: null },
    [data],
  )

  return (
    <PageContainer
      title="Analytics"
      description="Account, symbol and date-filtered trading performance over the closed-trade journal. Read-only — nothing here is executed."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Updating…</span> : null}
          <Link to="/operations/journal" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Journal
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
            <SkeletonRows rows={8} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={error ?? 'The analytics service could not be reached.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <>
            {error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                {/HTTP\s*4/.test(error) || error.includes('422')
                  ? `Filter rejected — showing the last valid result. ${error}`
                  : `Showing last good analytics — refresh failed: ${error}`}
              </p>
            ) : null}
            <AnalyticsControls available={available} query={query} onChange={setQuery} />
            <AnalyticsView data={data} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Source: <code>closed_trades</code> via <code>analytics.calculate_performance_metrics</code>.
          Not migrated here: the month calendar grid (daily P&L is shown as a bar
          series instead), the radar chart (shown as index bars), and the
          "Sync MT5 / Sync Capital" data-ingestion buttons (those stay in
          Streamlit). Research-analytics (R-multiples, execution stress,
          confluence) is a separate Research Lab workflow.
        </p>
      </div>
    </PageContainer>
  )
}
