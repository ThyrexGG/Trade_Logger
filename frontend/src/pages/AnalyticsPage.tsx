import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAnalytics } from '../lib/useAnalytics'
import { useSyncControl } from '../lib/useSyncControl'
import { describeAccount } from '../lib/accountLabel'
import type { AnalyticsQuery } from '../types/analytics'
import { PageContainer } from '../components/shell/PageContainer'
import { AnalyticsControls } from '../components/analytics/AnalyticsControls'
import { AnalyticsView } from '../components/analytics/AnalyticsView'
import { ChallengeTracker } from '../components/analytics/ChallengeTracker'
import {
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

const ACCOUNT_KEY = 'tl.analytics.account'

function loadStoredAccount(): string | null {
  try {
    return localStorage.getItem(ACCOUNT_KEY)
  } catch {
    return null
  }
}

function storeAccount(account: string | undefined) {
  try {
    localStorage.setItem(ACCOUNT_KEY, account ?? 'ALL')
  } catch {
    /* private browsing / storage blocked — the choice just won't stick */
  }
}

/**
 * Analytics (`/workspace/analytics`). Migrated from the Streamlit
 * "ANALYTICS & OVERVIEW" tab. Account / symbol / date-filtered trading
 * performance over the closed-trade journal. Read-only — every metric comes
 * from the backend `analytics.calculate_performance_metrics`.
 */
export function AnalyticsPage() {
  const [query, setQuery] = useState<AnalyticsQuery>({ initial_balance: 10000 })
  const { state, data, error, refreshing, refetch } = useAnalytics(query)
  const sync = useSyncControl(refetch)
  const syncing = sync.syncing || sync.status?.cycle_in_progress

  const available = useMemo(
    () => data?.available ?? { accounts: [], symbols: [], date_min: null, date_max: null, suggested_initial_balance: null, saved_initial_balance: null },
    [data],
  )

  // Remembers the account you last picked here — same "sticks across visits" behaviour the Journal page's
  // account filter already has. The very first time this has never been chosen (no stored value at all),
  // default to Capital.com over "All accounts" rather than dumping everything together; once you've
  // explicitly picked anything (including "All accounts" again later), that choice is respected forever.
  const appliedDefault = useRef(false)
  useEffect(() => {
    if (appliedDefault.current || available.accounts.length === 0) return
    appliedDefault.current = true
    const stored = loadStoredAccount()
    if (stored != null) {
      if (stored !== 'ALL' && available.accounts.includes(stored)) {
        setQuery((q) => ({ ...q, account: stored, symbols: undefined, start: undefined, end: undefined }))
      }
      return
    }
    const capital = available.accounts.find((a) => describeAccount(a).platform === 'Capital.com')
    if (capital) setQuery((q) => ({ ...q, account: capital, symbols: undefined, start: undefined, end: undefined }))
  }, [available.accounts])

  const handleQueryChange = useCallback((next: AnalyticsQuery) => {
    setQuery(next)
    storeAccount(next.account)
  }, [])

  return (
    <PageContainer
      title="Analytics"
      description="Account, symbol and date-filtered trading performance over the closed-trade journal. Read-only — nothing here is executed."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Updating…</span> : null}
          {sync.error ? <span className="text-[11px] text-warning" aria-live="polite">{sync.error}</span> : null}
          <button
            type="button"
            onClick={() => void sync.syncNow()}
            disabled={syncing}
            className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs text-accent hover:bg-accent/20 disabled:opacity-50"
            title="Pull the latest closed trades from the broker now, then refresh"
          >
            {syncing ? 'Syncing…' : 'Sync now'}
          </button>
          <Link to="/workspace/journal" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Journal
          </Link>
          <button type="button" onClick={refetch} className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Refresh
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
            <SectionError message={error ?? 'The analytics service could not be reached.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <div className="tl-fade-in space-y-4">
            {error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                {/HTTP\s*4/.test(error) || error.includes('422')
                  ? `Filter rejected — showing the last valid result. ${error}`
                  : `Showing last good analytics — refresh failed: ${error}`}
              </p>
            ) : null}
            <AnalyticsControls
              available={available}
              availableAccount={data.filters_applied.account}
              query={query}
              onChange={handleQueryChange}
            />
            <ChallengeTracker account={query.account} />
            <AnalyticsView data={data} />
          </div>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Source: <code>closed_trades</code> via <code>analytics.calculate_performance_metrics</code>.
          Data comes in through the broker sync (the <strong>Sync now</strong> button above).
        </p>
      </div>
    </PageContainer>
  )
}
