import { Link } from 'react-router-dom'
import { useOpenPositions } from '../lib/useOpenPositions'
import { PageContainer } from '../components/shell/PageContainer'
import { PositionsSummary, PositionsView } from '../components/operations/PositionsView'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Full read-only positions terminal (`/workspace/positions`). Reuses the
 * existing optimized `GET /api/positions` (Stage 3.5A). The Risk Gateway keeps
 * its own compact exposure panel — this is the full view. No close / modify /
 * reverse / execute control.
 */
export function PositionsPage() {
  const { state, data, error, refetch } = useOpenPositions()

  return (
    <PageContainer
      title="Positions"
      description="Open paper / shadow positions with excursion metrics. Read-only operational state — nothing here is executed."
      actions={
        <div className="flex flex-wrap gap-2">
          <Link to="/workspace/risk" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Risk Gateway
          </Link>
          <Link to="/operations/journal" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Journal
          </Link>
          <button
            type="button"
            onClick={refetch}
            className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
          >
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
            <SectionError
              message={error ?? 'The positions endpoint could not be reached.'}
              onRetry={refetch}
            />
          </div>
        ) : data ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good positions — refresh failed: {error}
              </p>
            ) : null}
            <PositionsSummary data={data} />
            <PositionsView data={data} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Positions are live operational state — not historical backtest research
          and not forward-evidence records. Refreshes every 30s, paused while the
          tab is hidden. "Last updated" uses the backend response timestamp.
        </p>
      </div>
    </PageContainer>
  )
}
