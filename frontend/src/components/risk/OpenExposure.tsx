import type { PositionsResponse } from '../../types/positions'
import type { LoadState } from '../../lib/useWatchlist'
import { formatLots, formatUsd } from '../../lib/format'

interface OpenExposureProps {
  state: LoadState
  data: PositionsResponse | null
  error: string | null
}

/**
 * Compact, read-only open-exposure context for the risk gateway — gives the
 * correlation warnings something to reference. Not the full Positions page:
 * no excursion audit, no actions, no editing.
 */
export function OpenExposure({ state, data, error }: OpenExposureProps) {
  return (
    <section aria-label="Open exposure" className="text-sm">
      <div className="flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-secondary">
          Open exposure
        </h3>
        {data ? (
          <span className="text-[11px] text-muted">
            {data.total_open} open · net{' '}
            <span
              className={
                data.total_floating_pnl > 0
                  ? 'text-positive'
                  : data.total_floating_pnl < 0
                    ? 'text-negative'
                    : 'text-secondary'
              }
            >
              {formatUsd(data.total_floating_pnl)}
            </span>
          </span>
        ) : null}
      </div>

      {state === 'loading' ? (
        <p className="mt-2 text-xs text-muted">Loading positions…</p>
      ) : state === 'error' ? (
        <p className="mt-2 text-xs text-muted">
          Positions unavailable{error ? ` — ${error}` : ''}
        </p>
      ) : data && data.positions.length === 0 ? (
        <p className="mt-2 text-xs text-muted">No open positions.</p>
      ) : data ? (
        <ul className="mt-2 divide-y divide-border-subtle">
          {data.positions.map((p) => (
            <li
              key={p.position_id}
              className="flex items-center justify-between gap-2 py-1.5 font-mono text-xs"
            >
              <span className="flex items-center gap-2">
                <span className="text-primary">{p.symbol}</span>
                <span
                  className={
                    p.direction.toUpperCase().includes('BUY')
                      ? 'text-positive'
                      : 'text-negative'
                  }
                >
                  {p.direction}
                </span>
                <span className="text-muted">{formatLots(p.volume)}</span>
              </span>
              <span className="flex items-center gap-2">
                <span
                  className={
                    p.floating_pnl > 0
                      ? 'text-positive'
                      : p.floating_pnl < 0
                        ? 'text-negative'
                        : 'text-secondary'
                  }
                >
                  {formatUsd(p.floating_pnl)}
                </span>
                <span className="text-muted">{p.unrealized_r}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
