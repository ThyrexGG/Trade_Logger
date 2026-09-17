import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useJournal } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import { downloadCsv, tradesToCsv } from '../lib/csvExport'
import { JournalSummary, JournalView } from '../components/operations/JournalView'
import { JournalFeed } from '../components/journal/JournalFeed'
import { FreeEntries } from '../components/journal/FreeEntries'
import type { JournalResponse } from '../types/operations'
import {
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

type ViewMode = 'feed' | 'table'
const VIEW_KEY = 'tl.journal.view'
const ACCOUNT_KEY = 'tl.journal.account'

function loadView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_KEY) === 'table' ? 'table' : 'feed'
  } catch {
    return 'feed'
  }
}

function loadAccount(): string {
  try {
    return localStorage.getItem(ACCOUNT_KEY) ?? 'ALL'
  } catch {
    return 'ALL'
  }
}

/** Filters a journal snapshot down to one account, recomputing the summary
 * totals to match — the raw fetch always carries every account so the
 * dropdown itself has something to list. */
function filterByAccount(data: JournalResponse, account: string): JournalResponse {
  if (account === 'ALL') return data
  const entries = data.entries.filter((e) => e.account_id === account)
  const wins = entries.filter((e) => e.net_profit > 0).length
  const losses = entries.filter((e) => e.net_profit < 0).length
  const total_net_profit = Math.round(entries.reduce((sum, e) => sum + e.net_profit, 0) * 100) / 100
  return { ...data, entries, total_trades: entries.length, wins, losses, total_net_profit }
}

/**
 * Trade journal (`/workspace/journal`). Read view over the authoritative
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
  const [account, setAccount] = useState<string>(loadAccount)

  function changeView(v: ViewMode) {
    setView(v)
    try {
      localStorage.setItem(VIEW_KEY, v)
    } catch {
      /* private browsing / storage blocked — the choice just won't stick */
    }
  }

  function changeAccount(a: string) {
    setAccount(a)
    try {
      localStorage.setItem(ACCOUNT_KEY, a)
    } catch {
      /* private browsing / storage blocked — the choice just won't stick */
    }
  }

  function exportCsv() {
    if (!viewData || viewData.entries.length === 0) return
    const stamp = new Date().toISOString().slice(0, 10)
    const scope = account === 'ALL' ? 'all-accounts' : account
    downloadCsv(`tradelogger-journal-${scope}-${stamp}.csv`, tradesToCsv(viewData.entries))
  }

  const filtered = useMemo(() => (data ? filterByAccount(data, account) : null), [data, account])
  // A deep-linked trade might belong to an account this filter is hiding —
  // fall back to unfiltered so the link still resolves instead of 404-ing.
  const viewData = focusTradeId && filtered && !filtered.entries.some((e) => e.trade_id === focusTradeId) ? data : filtered

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
          <button
            type="button"
            onClick={exportCsv}
            disabled={!viewData || viewData.entries.length === 0}
            className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            Export CSV
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {state === 'loading' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={8} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={error ?? 'The journal service could not be reached.'} onRetry={refetch} />
          </div>
        ) : data && viewData ? (
          <div className="tl-fade-in space-y-4">
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good journal — refresh failed: {error}
              </p>
            ) : null}
            {data.accounts.length > 1 ? (
              <label className="block w-fit text-[11px] text-muted">
                Account
                <select
                  value={account}
                  onChange={(e) => changeAccount(e.target.value)}
                  className="mt-1 block w-full min-w-[10rem] rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
                >
                  <option value="ALL">All accounts ({data.total_trades})</option>
                  {data.accounts.map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </label>
            ) : null}
            <JournalSummary data={viewData} />
            {view === 'feed' ? (
              <JournalFeed data={viewData} onEntryUpdated={applyEntry} />
            ) : (
              <JournalView data={viewData} onEntryUpdated={applyEntry} focusTradeId={focusTradeId} />
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
