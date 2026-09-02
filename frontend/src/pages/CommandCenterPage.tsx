import { useCommandCenter } from '../lib/useCommandCenter'
import { PageContainer } from '../components/shell/PageContainer'
import { CommandCenterView } from '../components/command-center/CommandCenterView'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Daily Command Center (`/workspace/command-center`). One aggregated read-only
 * request that re-shapes slices of the already-authoritative analytics,
 * positions, alerts, intelligence and forward-evidence sources into a
 * "what matters today" overview. Nothing here is executed or mutated.
 */
export function CommandCenterPage() {
  const { state, data, error, refreshing, refetch } = useCommandCenter()

  return (
    <PageContainer
      title="Daily Command Center"
      description="What matters today — today's P&L, open risk, alerts, market context and research state in one read-only view."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
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
            <SkeletonRows rows={10} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={error ?? 'The command centre could not be reached.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good overview — refresh failed: {error}
              </p>
            ) : null}
            <CommandCenterView data={data} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Aggregated from <code>analytics</code>, <code>positions</code>,
          <code> price_alerts</code>, market intelligence and forward evidence —
          one request, no per-section fan-out. Refreshes every 60s (paused while
          the tab is hidden). Not included: the XAUUSD news / economic-calendar
          engine (stays in Streamlit pending the macro-intelligence stage) and
          research-note / snapshot writing.
        </p>
      </div>
    </PageContainer>
  )
}
