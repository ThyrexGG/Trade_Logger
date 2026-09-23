import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useOpenPositions } from '../lib/useOpenPositions'
import { useSyncControl } from '../lib/useSyncControl'
import { describeAccount } from '../lib/accountLabel'
import { PageContainer } from '../components/shell/PageContainer'
import { PositionsSummary, PositionsView } from '../components/operations/PositionsView'
import {
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

const ACCOUNT_KEY = 'tl.positions.account'

function loadAccount(): string {
  try {
    return localStorage.getItem(ACCOUNT_KEY) ?? 'ALL'
  } catch {
    return 'ALL'
  }
}

/**
 * Full read-only positions terminal (`/workspace/positions`). Reuses the
 * existing optimized `GET /api/positions`, fed by the broker sync (Capital.com
 * live positions, or paper/shadow positions in research mode) into the same
 * `open_positions` table. The Risk Gateway keeps its own compact exposure
 * panel — this is the full view. No close / modify / reverse / execute control.
 */
export function PositionsPage() {
  const { state, data, error, refetch } = useOpenPositions()
  const sync = useSyncControl(refetch)
  const [account, setAccount] = useState<string>(loadAccount)

  function changeAccount(a: string) {
    setAccount(a)
    try {
      localStorage.setItem(ACCOUNT_KEY, a)
    } catch {
      /* private browsing / storage blocked — the choice just won't stick */
    }
  }

  const accounts = useMemo(
    () => Array.from(new Set((data?.positions ?? []).map((p) => p.account_id))).sort(),
    [data],
  )
  // account_id isn't returned server-side once filtered out, so this recomputes the two totals locally —
  // same approach the Journal page uses for its own account filter.
  const viewData = useMemo(() => {
    if (!data || account === 'ALL') return data
    const positions = data.positions.filter((p) => p.account_id === account)
    return {
      ...data,
      positions,
      total_open: positions.length,
      total_floating_pnl: Math.round(positions.reduce((sum, p) => sum + p.floating_pnl, 0) * 100) / 100,
    }
  }, [data, account])

  const lastRun = sync.status?.last_run
  const lastRunLabel = lastRun
    ? `synced ${new Date(lastRun.at).toLocaleTimeString()}${lastRun.capital_ok ? '' : ' · Capital failed'}`
    : null

  return (
    <PageContainer
      title="Positions"
      description="Live open positions synced from your broker, with excursion metrics. Read-only operational state — nothing here is executed."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void sync.syncNow()}
            disabled={sync.syncing || sync.status?.cycle_in_progress}
            className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs text-accent hover:bg-accent/20 disabled:opacity-50"
            title="Pull the latest trades & positions from Capital.com now"
          >
            {sync.syncing || sync.status?.cycle_in_progress ? 'Syncing…' : 'Sync now'}
          </button>
          <button
            type="button"
            onClick={sync.toggleAuto}
            disabled={sync.busyAuto || !sync.status}
            className={`flex items-center gap-1.5 rounded border px-2 py-1 text-xs transition-colors disabled:opacity-50 ${
              sync.status?.auto_enabled
                ? 'border-positive/40 bg-positive/10 text-positive hover:bg-positive/20'
                : 'border-border bg-surface-elevated text-muted hover:text-secondary'
            }`}
            title={
              sync.status?.auto_enabled
                ? `Auto-sync ON — the server re-syncs every ${sync.status.interval_seconds}s. Click to turn off.`
                : 'Auto-sync OFF — click to have the server keep positions fresh automatically.'
            }
          >
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${sync.status?.auto_enabled ? 'bg-positive' : 'bg-muted'}`}
            />
            Auto-sync {sync.status ? (sync.status.auto_enabled ? 'ON' : 'OFF') : '…'}
          </button>
          <Link to="/workspace/risk" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Risk Gateway
          </Link>
          <Link to="/workspace/journal" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
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
        {sync.error ? (
          <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
            Sync: {sync.error}
          </p>
        ) : lastRunLabel ? (
          <p className="text-[11px] text-muted">
            {lastRunLabel}
            {sync.status?.last_run?.new_closed_trades
              ? ` · ${sync.status.last_run.new_closed_trades} new closed trade(s)`
              : ''}
            {sync.status?.auto_enabled ? ' · auto-sync on' : ''}
          </p>
        ) : null}

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
        ) : data && viewData ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good positions — refresh failed: {error}
              </p>
            ) : null}
            {accounts.length > 1 ? (
              <label className="block w-fit text-[11px] text-muted">
                Account
                <select
                  value={account}
                  onChange={(e) => changeAccount(e.target.value)}
                  className="mt-1 block w-full min-w-[10rem] rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
                >
                  <option value="ALL">All accounts ({data.positions.length})</option>
                  {accounts.map((a) => (
                    <option key={a} value={a}>{describeAccount(a).label}</option>
                  ))}
                </select>
              </label>
            ) : null}
            <PositionsSummary data={viewData} />
            <PositionsView data={viewData} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          Positions are live operational state — not historical backtest research
          and not forward-evidence records. Refreshes every 45s, paused while the
          tab is hidden, and immediately after a sync. "Last updated" uses the
          backend response timestamp.
        </p>
      </div>
    </PageContainer>
  )
}
