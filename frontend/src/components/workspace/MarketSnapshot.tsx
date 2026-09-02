import { useEffect, useState, type ReactNode } from 'react'
import type { MarketSnapshot as MarketSnapshotData } from '../../types/market'
import type { LoadState } from '../../lib/useWatchlist'
import {
  ageSeconds,
  formatPrice,
  formatScore,
  formatSpread,
  timeAgo,
} from '../../lib/format'
import { StateTag } from './StateTag'

interface MarketSnapshotProps {
  symbol: string | null
  state: LoadState
  data: MarketSnapshotData | null
  error: string | null
  refreshing: boolean
  onRetry: () => void
}

const MTF_ORDER = ['1D', '4H', '1H', '15M', '5M', '1M']
const STALE_AFTER_S = 60

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-0.5 font-mono text-sm tabular-nums text-primary">
        {children}
      </p>
    </div>
  )
}

function Block() {
  return <div className="h-6 w-24 rounded bg-surface-elevated" />
}

function qualityTone(q: number): string {
  if (q >= 90) return 'text-positive'
  if (q >= 75) return 'text-warning'
  return 'text-negative'
}

/** Snapshot panel for the selected symbol. Renders only fields the API returns. */
export function MarketSnapshot({
  symbol,
  state,
  data,
  error,
  refreshing,
  onRetry,
}: MarketSnapshotProps) {
  // Re-tick once a second so the "x s ago" age stays honest.
  const [, force] = useState(0)
  useEffect(() => {
    const t = window.setInterval(() => force((n) => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [])

  if (!symbol) {
    return (
      <section aria-label="Market snapshot" className="p-6">
        <p className="text-sm text-muted">Select an instrument to view its snapshot.</p>
      </section>
    )
  }

  const age = data ? ageSeconds(data.timestamp) : null
  const stale = age !== null && age > STALE_AFTER_S
  const noUsableData =
    state === 'ready' &&
    data !== null &&
    data.price === 0 &&
    data.bid === 0 &&
    data.ask === 0

  return (
    <section
      aria-label="Market snapshot"
      className="flex min-h-0 flex-col overflow-y-auto"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-border-subtle px-4 py-3">
        <div className="flex items-baseline gap-2">
          <h2 className="font-mono text-base font-semibold text-primary">
            {data?.display ?? symbol}
          </h2>
          {data ? (
            <span className="text-xs text-secondary">{data.session}</span>
          ) : null}
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          {refreshing ? <span className="text-muted">Refreshing…</span> : null}
          {data ? (
            <span
              className={stale ? 'text-stale' : 'text-muted'}
              title={new Date(data.timestamp).toLocaleString()}
            >
              {stale ? 'Stale · ' : ''}
              {timeAgo(data.timestamp) ?? 'unknown age'}
            </span>
          ) : null}
          {data?.cached ? (
            <span className="rounded bg-surface-elevated px-1 text-muted">
              cached
            </span>
          ) : null}
        </div>
      </header>

      {state === 'loading' ? (
        <div className="space-y-4 p-4">
          <Block />
          <div className="flex gap-6">
            <Block />
            <Block />
            <Block />
          </div>
          <div className="flex gap-2">
            {MTF_ORDER.map((tf) => (
              <div key={tf} className="h-6 w-14 rounded bg-surface-elevated" />
            ))}
          </div>
        </div>
      ) : state === 'error' && !data ? (
        <div className="p-4 text-sm">
          <p className="text-negative">Snapshot unavailable for {symbol}</p>
          <p className="mt-1 text-xs text-muted">{error}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
          >
            Retry
          </button>
        </div>
      ) : noUsableData ? (
        <div className="p-4 text-sm text-muted">
          No usable market data is available for {symbol} right now.
        </div>
      ) : data ? (
        <div className="space-y-5 p-4">
          {state === 'error' && error ? (
            <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
              Showing last snapshot — refresh failed
            </p>
          ) : null}

          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted">Price</p>
            <p className="font-mono text-2xl font-semibold tabular-nums text-primary">
              {formatPrice(data.price)}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
            <Field label="Bid">{formatPrice(data.bid)}</Field>
            <Field label="Ask">{formatPrice(data.ask)}</Field>
            <Field label="Spread">{formatSpread(data.spread)}</Field>
            <Field label="Data quality">
              <span className={qualityTone(data.data_quality)}>
                {data.data_quality}
                <span className="text-muted">/100</span>
              </span>
            </Field>
          </div>

          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wider text-muted">
              Market state
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <StateTag value={data.setup_state} />
              <span className="font-mono text-xs text-secondary">
                edge {formatScore(data.edge_score)}
              </span>
              <span className="font-mono text-xs text-secondary">
                macro {formatScore(data.macro_score)}
              </span>
            </div>
          </div>

          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wider text-muted">
              Multi-timeframe bias
            </p>
            <div className="flex flex-wrap gap-1.5">
              {MTF_ORDER.filter((tf) => tf in data.mtf_bias).map((tf) => (
                <StateTag key={tf} label={tf} value={data.mtf_bias[tf]} />
              ))}
            </div>
          </div>

          <div className="border-t border-border-subtle pt-3">
            <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-negative">
              <span aria-hidden="true">🔒</span>
              LIVE BROKER TRANSMISSION: {data.live_broker_transmission}
            </span>
          </div>
        </div>
      ) : null}
    </section>
  )
}
