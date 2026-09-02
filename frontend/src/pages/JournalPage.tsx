import { Link } from 'react-router-dom'
import { useJournal } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import { JournalSummary, JournalView } from '../components/operations/JournalView'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Trade journal (`/operations/journal`). Read-only over the authoritative
 * `closed_trades` table. Client-side filtering; no journal-write endpoint
 * exists so nothing can be created or edited here.
 */
export function JournalPage() {
  const { state, data, error, refreshing, refetch } = useJournal()

  return (
    <PageContainer
      title="Trade Journal"
      description="Closed-trade record with subjective setup tags, notes and ratings. Read-only."
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
            <JournalView data={data} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Journal records keep their authoritative account / source. Not exposed
          by the current API: journal creation / editing, per-entry screenshots,
          free-form annotations beyond the note field, and tag management.
        </p>
      </div>
    </PageContainer>
  )
}
