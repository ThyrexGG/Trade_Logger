import { Link, useSearchParams } from 'react-router-dom'
import { useJournal } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import { JournalSummary, JournalView } from '../components/operations/JournalView'
import { FreeEntries } from '../components/journal/FreeEntries'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Trade journal (`/operations/journal`). Read view over the authoritative
 * `closed_trades` table with client-side filtering. The subjective annotation
 * fields (setup tag / notes / chart snapshot) are editable in place via
 * `PATCH /api/operations/journal/{trade_id}`; execution facts stay immutable.
 */
export function JournalPage() {
  const { state, data, error, refreshing, refetch, applyEntry } = useJournal()
  const [params] = useSearchParams()
  const focusTradeId = params.get('trade')

  return (
    <PageContainer
      title="Trade Journal"
      description="Closed-trade record with editable setup tags, notes and chart snapshots. Execution facts are immutable."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <Link to="/workspace/positions" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Positions
          </Link>
          <Link to="/operations/audit" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Audit
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
            <SectionError message={error ?? 'The journal service could not be reached.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good journal — refresh failed: {error}
              </p>
            ) : null}
            <JournalSummary data={data} />
            <JournalView data={data} onEntryUpdated={applyEntry} focusTradeId={focusTradeId} />
            <FreeEntries />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          One entry per closed trade (from the authoritative <code>closed_trades</code> table).
          Editable: setup tag, notes, chart-snapshot URL, and uploaded screenshots
          (stored in the database, up to 4 MB each — drag-drop or paste). Execution
          facts are immutable and nothing here can submit or transmit an order.
        </p>
      </div>
    </PageContainer>
  )
}
