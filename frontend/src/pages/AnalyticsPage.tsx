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
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-xs text-muted" aria-live="polite">Updating…</span> : null}
          {sync.error ? <span className="text-xs text-warning" aria-live="polite">{sync.error}</span> : null}
          <Link to="/workspace/journal" className="tl-btn tl-btn--ghost">
            Open Journal
          </Link>
          <button
            type="button"
            onClick={() => void sync.syncNow()}
            disabled={syncing}
            className="tl-btn tl-btn--primary"
            title="Pull your latest closed trades from your broker, then refresh"
          >
            {syncing ? 'Syncing…' : 'Sync now'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {state === 'loading' && !data ? (
          <div className="tl-card p-5">
            <SkeletonRows rows={8} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="tl-card">
            <SectionError message={error ?? 'Your analytics could not be loaded.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <div className="tl-fade-in space-y-4">
            {error ? (
              <p className="rounded-[var(--tl-radius)] border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                {/HTTP\s*4/.test(error) || error.includes('422')
                  ? 'Those filters didn\u2019t work — showing the last result that did.'
                  : 'Couldn\u2019t refresh just now — showing your numbers from a moment ago.'}
              </p>
            ) : null}
            <AnalyticsControls
              available={available}
              availableAccount={data.filters_applied.account}
              query={query}
              onChange={handleQueryChange}
            />
            <AnalyticsView data={data} />
            <ChallengeTracker account={query.account} />
          </div>
        ) : null}

      </div>
    </PageContainer>
  )
}
