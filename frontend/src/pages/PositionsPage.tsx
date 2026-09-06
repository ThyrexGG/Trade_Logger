import { Link } from 'react-router-dom'
import { useOpenPositions } from '../lib/useOpenPositions'
import { useSyncControl } from '../lib/useSyncControl'
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
  const sync = useSyncControl(refetch)

  const lastRun = sync.status?.last_run
  const lastRunLabel = lastRun
    ? `synced ${new Date(lastRun.at).toLocaleTimeString()}${lastRun.capital_ok ? '' : ' · Capital failed'}`
    : null

  return (
    <PageContainer
      title="Positions"
      description="Open paper / shadow positions with excursion metrics. Read-only operational state — nothing here is executed."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void sync.syncNow()}
            disabled={sync.syncing || sync.status?.cycle_in_progress}
            className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs text-accent hover:bg-accent/20 disabled:opacity-50"
            title="Pull the latest trades & positions from Capital.com / MT5 now"
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
