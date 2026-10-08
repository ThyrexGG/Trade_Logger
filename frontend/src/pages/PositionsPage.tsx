import { useMemo, useState } from 'react'
import { useOpenPositions } from '../lib/useOpenPositions'
import { useSyncControl } from '../lib/useSyncControl'
import { describeAccount } from '../lib/accountLabel'
import { PositionTracks } from '../components/home/PositionTracks'
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

  const syncBusy = sync.syncing || Boolean(sync.status?.cycle_in_progress)

  return (
    <PageContainer
      title="Positions"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            role="switch"
            aria-checked={Boolean(sync.status?.auto_enabled)}
            onClick={sync.toggleAuto}
            disabled={sync.busyAuto || !sync.status}
            className="tl-btn tl-btn--ghost"
            title={
              sync.status?.auto_enabled
                ? `Auto-sync is on — your broker is checked every ${sync.status.interval_seconds}s. Click to turn it off.`
                : 'Auto-sync is off — click to keep positions fresh automatically.'
            }
          >
            <span className={`relative h-4 w-7 rounded-full transition-colors ${sync.status?.auto_enabled ? 'bg-accent-fill' : 'bg-surface-hover'}`} aria-hidden="true">
              <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-[left] ${sync.status?.auto_enabled ? 'left-[14px]' : 'left-0.5'}`} />
            </span>
            Auto-sync
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
      <div className="space-y-4">
        <div className="tl-toolbar">
          {accounts.length > 1 ? (
            <label className="flex items-center">
              <span className="sr-only">Account</span>
              <select value={account} onChange={(e) => changeAccount(e.target.value)} className="tl-select">
                <option value="ALL">All accounts</option>
                {accounts.map((a) => (
                  <option key={a} value={a}>{describeAccount(a).label}</option>
                ))}
              </select>
            </label>
          ) : null}
          {sync.error ? (
            <span className="text-xs text-warning">Last sync had a problem: {sync.error}</span>
          ) : lastRunLabel ? (
            <span className="text-xs text-muted">
              {lastRunLabel}
              {sync.status?.last_run?.new_closed_trades ? ` · ${sync.status.last_run.new_closed_trades} newly closed` : ''}
            </span>
          ) : null}
        </div>

        {state === 'loading' && !data ? (
          <div className="tl-card p-5">
            <SkeletonRows rows={6} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="tl-card">
            <SectionError message={error ?? 'Your positions could not be loaded.'} onRetry={refetch} />
          </div>
        ) : data && viewData ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded-[var(--tl-radius)] border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                Couldn&rsquo;t refresh just now — showing your positions from a moment ago.
              </p>
            ) : null}
            <PositionsSummary data={viewData} />
            <section className="tl-card" aria-label="Your open trades">
              <div className="tl-card-head">
                <h2 className="tl-card-title">At a glance</h2>
                <span className="tl-label hidden sm:inline">stop · entry · now · target</span>
                <span className="tl-rule" aria-hidden="true" />
              </div>
              <div className="tl-card-body">
                <PositionTracks positions={viewData.positions} />
              </div>
            </section>
            <PositionsView data={viewData} />
          </>
        ) : null}

      </div>
    </PageContainer>
  )
}
