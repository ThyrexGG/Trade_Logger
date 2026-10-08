import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useJournal } from '../lib/useOperations'
import { useSyncControl } from '../lib/useSyncControl'
import { useOpenPositions } from '../lib/useOpenPositions'
import { OpenTradesStrip } from '../components/journal/OpenTradesStrip'
import { OpenPositionsTable } from '../components/journal/OpenPositionsTable'
import { PageContainer } from '../components/shell/PageContainer'
import { downloadCsv, tradesToCsv } from '../lib/csvExport'
import { JournalSummary, JournalView } from '../components/operations/JournalView'
import { JournalFeed } from '../components/journal/JournalFeed'
import { JournalDayPicker, localDayIso } from '../components/journal/JournalDayPicker'
import { describeAccount } from '../lib/accountLabel'
import { FreeEntries } from '../components/journal/FreeEntries'
import type { JournalResponse } from '../types/operations'
import {
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

type ViewMode = 'feed' | 'table'
type DateFilter = 'today' | 'week' | 'month' | 'all'
const VIEW_KEY = 'tl.journal.view'
const ACCOUNT_KEY = 'tl.journal.account'
const DATE_KEY = 'tl.journal.dateFilter'

const DATE_FILTER_LABEL: Record<DateFilter, string> = {
  today: 'Today',
  week: 'This week',
  month: 'This month',
  all: 'All time',
}

function loadView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_KEY) === 'table' ? 'table' : 'feed'
  } catch {
    return 'feed'
  }
}

/** `null` means "never explicitly chosen" — distinct from an explicit past
 * choice of "ALL" — so a first-ever visit can default to Capital.com instead
 * of dumping every account together, same as the Analytics page. */
function loadStoredAccount(): string | null {
  try {
    return localStorage.getItem(ACCOUNT_KEY)
  } catch {
    return null
  }
}

function loadDateFilter(): DateFilter {
  try {
    const v = localStorage.getItem(DATE_KEY)
    return v === 'today' || v === 'month' || v === 'all' ? v : 'week'
  } catch {
    return 'week'
  }
}

/** Treats a timestamp with no explicit timezone as UTC — matching how the
 * backend stores `exit_time` — instead of the browser's local-time guess. */
function parseTime(iso: string): number {
  const hasZone = /[zZ]|[+-]\d\d:\d\d$/.test(iso)
  const t = new Date(hasZone ? iso : `${iso}Z`).getTime()
  return Number.isNaN(t) ? 0 : t
}

/** Start of the ISO (Monday-based) week containing `d`, at local midnight. */
function startOfWeek(d: Date): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const day = out.getDay()
  out.setDate(out.getDate() - (day === 0 ? 6 : day - 1))
  return out
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function dateFilterCutoff(filter: DateFilter): number {
  const now = new Date()
  if (filter === 'today') return startOfDay(now).getTime()
  if (filter === 'week') return startOfWeek(now).getTime()
  if (filter === 'month') return startOfMonth(now).getTime()
  return 0
}

/** Filters a journal snapshot down to one account and/or a date window, recomputing the summary totals
 * to match — the raw fetch always carries everything so the dropdowns themselves have something to list.
 * A specific `selectedDay` (from the calendar) wins over the rolling `dateFilter` preset when both are set. */
function filterJournal(data: JournalResponse, account: string, dateFilter: DateFilter, selectedDay: string | null): JournalResponse {
  let entries = data.entries
  if (account !== 'ALL') entries = entries.filter((e) => e.account_id === account)
  if (selectedDay) {
    // The calendar's day belongs to when a trade was OPENED, not closed -- a trade opened late one day
    // and closed into the next shouldn't land on the day it happened to close (see JournalDayPicker).
    entries = entries.filter((e) => localDayIso(parseTime(e.entry_time)) === selectedDay)
  } else {
    const cutoff = dateFilterCutoff(dateFilter)
    if (cutoff > 0) entries = entries.filter((e) => parseTime(e.exit_time) >= cutoff)
  }
  if (entries === data.entries) return data
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
  const { state, data, error, refreshing, refetch, applyEntry, removeEntry } = useJournal()
  const openPositions = useOpenPositions()
  const sync = useSyncControl(refetch)
  const [params] = useSearchParams()
  const focusTradeId = params.get('trade')
  // A deep-link from the calendar ("?trade=...") wants the highlighted-row
  // scroll-to behaviour the table view has — honour that regardless of the
  // remembered preference; a plain visit to the page uses it as normal.
  const [view, setView] = useState<ViewMode>(() => (focusTradeId ? 'table' : loadView()))
  const [account, setAccount] = useState<string>(() => loadStoredAccount() ?? 'ALL')
  // A deep-linked trade might be older than "this week" — land on "All time"
  // instead of the default so the link still resolves instead of hiding it.
  const [dateFilter, setDateFilter] = useState<DateFilter>(() => (focusTradeId ? 'all' : loadDateFilter()))
  // A specific day picked from the calendar; overrides `dateFilter` above while set. Not persisted —
  // like the Analytics calendar, a picked day is a one-off look, not a standing preference.
  const [selectedDay, setSelectedDay] = useState<string | null>(null)

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

  // First-ever visit (nothing stored yet, including a fresh browser/profile) defaults to Capital.com
  // over dumping every account together — same rule the Analytics page uses. Once anything has been
  // explicitly picked here before (including "All accounts" again), that choice sticks instead.
  const appliedDefault = useRef(false)
  useEffect(() => {
    if (appliedDefault.current || !data || data.accounts.length === 0) return
    appliedDefault.current = true
    if (loadStoredAccount() != null) return
    const capital = data.accounts.find((a) => describeAccount(a).platform === 'Capital.com')
    if (capital) changeAccount(capital)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  function changeDateFilter(f: DateFilter) {
    setDateFilter(f)
    setSelectedDay(null) // a preset window and a picked day are mutually exclusive
    try {
      localStorage.setItem(DATE_KEY, f)
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

  const filtered = useMemo(
    () => (data ? filterJournal(data, account, dateFilter, selectedDay) : null),
    [data, account, dateFilter, selectedDay],
  )
  // Account-scoped but NOT date-scoped — the calendar needs every day to navigate through, not just the
  // window the preset buttons currently show.
  const accountEntries = useMemo(() => {
    if (!data) return []
    return account === 'ALL' ? data.entries : data.entries.filter((e) => e.account_id === account)
  }, [data, account])
  const openPositionsForAccount = useMemo(() => {
    const all = openPositions.data?.positions ?? []
    return account === 'ALL' ? all : all.filter((p) => p.account_id === account)
  }, [openPositions.data, account])
  // A deep-linked trade might belong to an account this filter is hiding —
  // fall back to unfiltered so the link still resolves instead of 404-ing.
  const viewData = focusTradeId && filtered && !filtered.entries.some((e) => e.trade_id === focusTradeId) ? data : filtered

  const syncBusy = sync.syncing || Boolean(sync.status?.cycle_in_progress)

  return (
    <PageContainer
      title="Journal"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-xs text-muted" aria-live="polite">Updating…</span> : null}
          <button
            type="button"
            onClick={exportCsv}
            disabled={!viewData || viewData.entries.length === 0}
            className="tl-btn tl-btn--ghost"
            title="Download the trades shown below as a spreadsheet"
          >
            Export
          </button>
          <button
            type="button"
            onClick={() => void sync.syncNow()}
            disabled={syncBusy}
            className="tl-btn tl-btn--primary"
            title="Pull your latest trades and positions from your broker now"
          >
            {syncBusy ? 'Syncing…' : 'Sync now'}
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="tl-toolbar">
          {data && data.accounts.length > 1 ? (
            <label className="flex items-center">
              <span className="sr-only">Account</span>
              <select value={account} onChange={(e) => changeAccount(e.target.value)} className="tl-select">
                <option value="ALL">All accounts</option>
                {data.accounts.map((a) => (
                  <option key={a} value={a}>{describeAccount(a).label}</option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="tl-seg" role="group" aria-label="Date range">
            {(Object.keys(DATE_FILTER_LABEL) as DateFilter[]).map((f) => (
              <button key={f} type="button" aria-pressed={!selectedDay && dateFilter === f} onClick={() => changeDateFilter(f)}>
                {DATE_FILTER_LABEL[f]}
              </button>
            ))}
          </div>
          <JournalDayPicker entries={accountEntries} selected={selectedDay} onSelect={setSelectedDay} />
          <div className="tl-seg ml-auto" role="group" aria-label="Layout">
            <button type="button" aria-pressed={view === 'feed'} onClick={() => changeView('feed')}>
              Cards
            </button>
            <button type="button" aria-pressed={view === 'table'} onClick={() => changeView('table')}>
              Table
            </button>
          </div>
        </div>

        {view === 'table' ? (
          <OpenPositionsTable positions={openPositionsForAccount} />
        ) : (
          <OpenTradesStrip positions={openPositionsForAccount} />
        )}

        {state === 'loading' && !data ? (
          <div className="tl-card p-5">
            <SkeletonRows rows={8} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="tl-card">
            <SectionError message={error ?? 'Your journal could not be loaded.'} onRetry={refetch} />
          </div>
        ) : data && viewData ? (
          <div className="tl-fade-in space-y-4">
            {state === 'error' && error ? (
              <p className="rounded-[var(--tl-radius)] border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                Couldn&rsquo;t refresh just now — showing your journal from a moment ago.
              </p>
            ) : null}
            <JournalSummary data={viewData} />
            {viewData.entries.length === 0 && data.entries.length > 0 ? (
              <div className="tl-state tl-state--quiet text-sm text-muted">
                {selectedDay
                  ? `No trades closed on ${new Date(`${selectedDay}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}.`
                  : 'No trades match the current filter.'}
              </div>
            ) : view === 'feed' ? (
              <JournalFeed data={viewData} onEntryUpdated={applyEntry} onEntryDeleted={removeEntry} />
            ) : (
              <JournalView data={viewData} onEntryUpdated={applyEntry} onEntryDeleted={removeEntry} focusTradeId={focusTradeId} />
            )}
            <FreeEntries />
          </div>
        ) : null}

      </div>
    </PageContainer>
  )
}
