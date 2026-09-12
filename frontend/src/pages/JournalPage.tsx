import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useJournal } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import { JournalSummary, JournalView } from '../components/operations/JournalView'
import { JournalFeed } from '../components/journal/JournalFeed'
import { FreeEntries } from '../components/journal/FreeEntries'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

type ViewMode = 'feed' | 'table'
const VIEW_KEY = 'tl.journal.view'

function loadView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_KEY) === 'table' ? 'table' : 'feed'
  } catch {
    return 'feed'
  }
}

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
  // A deep-link from the calendar ("?trade=...") wants the highlighted-row
  // scroll-to behaviour the table view has — honour that regardless of the
  // remembered preference; a plain visit to the page uses it as normal.
  const [view, setView] = useState<ViewMode>(() => (focusTradeId ? 'table' : loadView()))

  function changeView(v: ViewMode) {
    setView(v)
    try {
      localStorage.setItem(VIEW_KEY, v)
    } catch {
      /* private browsing / storage blocked — the choice just won't stick */
    }
  }

  return (
    <PageContainer
      title="Trade Journal"
      description="Closed-trade record with editable setup tags, notes and chart snapshots. Execution facts are immutable."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <div className="flex overflow-hidden rounded border border-border text-xs">
            <button
              type="button"
              onClick={() => changeView('feed')}
              className={`px-2.5 py-1 ${view === 'feed' ? 'bg-accent/10 text-accent' : 'text-secondary hover:bg-surface-hover'}`}
            >
              Feed
            </button>
            <button
              type="button"
              onClick={() => changeView('table')}
              className={`border-l border-border px-2.5 py-1 ${view === 'table' ? 'bg-accent/10 text-accent' : 'text-secondary hover:bg-surface-hover'}`}
            >
              Table
            </button>
          </div>
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
          <div className="tl-fade-in space-y-4">
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good journal — refresh failed: {error}
              </p>
            ) : null}
            <JournalSummary data={data} />
            {view === 'feed' ? (
              <JournalFeed data={data} onEntryUpdated={applyEntry} />
            ) : (
              <JournalView data={data} onEntryUpdated={applyEntry} focusTradeId={focusTradeId} />
            )}
            <FreeEntries />
          </div>
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
