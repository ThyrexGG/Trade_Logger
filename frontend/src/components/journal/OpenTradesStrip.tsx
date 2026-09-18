import { Link } from 'react-router-dom'
import type { PositionItem } from '../../types/positions'
import { formatUsd } from '../../lib/format'

function money(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v).replace('$', '')}`
}

/**
 * Currently-open trades, shown inline at the top of the journal — pulled from
 * the same live `open_positions` feed as the Positions page, so it updates on
 * the same schedule (45s, or immediately after a sync). Once a trade closes
 * it drops out of here on the next refresh and shows up as a normal journal
 * card instead — no separate action needed to "convert" it.
 */
export function OpenTradesStrip({ positions }: { positions: PositionItem[] }) {
  if (positions.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
        </span>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Open now ({positions.length})
        </h3>
      </div>
      {positions.map((p) => {
        const win = p.floating_pnl > 0
        const loss = p.floating_pnl < 0
        return (
          <div
            key={p.position_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-accent/30 bg-accent/5 p-3"
          >
            <div className="flex flex-wrap items-baseline gap-2">
              <Link
                to={`/workspace/market?symbol=${encodeURIComponent(p.symbol)}`}
                className="font-mono text-base font-semibold text-primary hover:text-accent"
              >
                {p.symbol}
              </Link>
              <span
                className={`font-mono text-xs ${
                  p.direction.includes('BUY') || p.direction.includes('LONG') ? 'text-positive' : 'text-negative'
                }`}
              >
                {p.direction}
              </span>
              <span className="text-[11px] text-muted">
                {p.volume} @ {p.entry_price} → {p.current_price}
              </span>
            </div>
            <span
              className={`font-mono text-lg font-semibold ${win ? 'text-positive' : loss ? 'text-negative' : 'text-secondary'}`}
            >
              Floating: {money(p.floating_pnl)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
