import { useMemo, useState } from 'react'
import type { BacktestTrade } from '../../types/research'
import { ResearchUnavailable, SectionCard } from './primitives'

type Segment = 'all' | 'is' | 'oos'
const PAGE = 50

function n(v: number | null, d = 2): string {
  return v === null || !Number.isFinite(v) ? '—' : v.toFixed(d)
}

/**
 * Compact backtest trade list. Client-side only over the trades the run
 * returned — no per-row detail request (no trade-detail endpoint exists), no
 * client-side result calculation.
 */
export function BacktestTradeTable({
  trades,
  total,
  truncated,
}: {
  trades: BacktestTrade[]
  total: number
  truncated: boolean
}) {
  const [segment, setSegment] = useState<Segment>('all')
  const [limit, setLimit] = useState(PAGE)

  const filtered = useMemo(() => {
    if (segment === 'all') return trades
    const wantOos = segment === 'oos'
    return trades.filter((t) => (t.is_oos ?? false) === wantOos)
  }, [trades, segment])

  const shown = filtered.slice(0, limit)

  return (
    <SectionCard
      title="Trade list"
      action={
        <span className="font-mono text-[11px] text-muted">
          {total.toLocaleString()} trades{truncated ? ` · first ${trades.length} shown` : ''}
        </span>
      }
    >
      {trades.length === 0 ? (
        <ResearchUnavailable>No trades were executed in this run.</ResearchUnavailable>
      ) : (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-1">
            {(['all', 'is', 'oos'] as Segment[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  setSegment(s)
                  setLimit(PAGE)
                }}
                className={`rounded border px-2 py-0.5 text-[11px] ${
                  segment === s
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-border text-secondary hover:text-primary'
                }`}
              >
                {s === 'all' ? 'All' : s === 'is' ? 'In-sample' : 'Out-of-sample'}
              </button>
            ))}
            <span className="ml-auto font-mono text-[11px] text-muted">
              {filtered.length} rows
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[11px]">
              <thead className="border-b border-border text-muted">
                <tr>
                  <th className="px-2 py-1.5 text-left font-medium">Entry</th>
                  <th className="px-2 py-1.5 text-left font-medium">Dir</th>
                  <th className="px-2 py-1.5 text-right font-medium">Entry px</th>
                  <th className="px-2 py-1.5 text-right font-medium">Exit px</th>
                  <th className="px-2 py-1.5 text-right font-medium">Size</th>
                  <th className="px-2 py-1.5 text-right font-medium">P&L</th>
                  <th className="px-2 py-1.5 text-right font-medium">Equity</th>
                  <th className="px-2 py-1.5 text-left font-medium">Seg</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((t, i) => (
                  <tr key={i} className="border-b border-border-subtle/60">
                    <td className="px-2 py-1 font-mono text-secondary">
                      {t.entry_time?.slice(0, 16) ?? '—'}
                    </td>
                    <td
                      className={`px-2 py-1 font-mono ${
                        t.direction === 'BUY'
                          ? 'text-positive'
                          : t.direction === 'SELL'
                            ? 'text-negative'
                            : 'text-secondary'
                      }`}
                    >
                      {t.direction ?? '—'}
                    </td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-primary">
                      {n(t.entry_price, 4)}
                    </td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-primary">
                      {n(t.exit_price, 4)}
                    </td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">
                      {n(t.position_size)}
                    </td>
                    <td
                      className={`px-2 py-1 text-right font-mono tabular-nums ${
                        (t.pnl ?? 0) >= 0 ? 'text-positive' : 'text-negative'
                      }`}
                    >
                      {t.pnl === null ? '—' : `${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}`}
                    </td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">
                      {n(t.equity)}
                    </td>
                    <td className="px-2 py-1">
                      <span
                        className={`rounded px-1 text-[10px] ${
                          t.is_oos
                            ? 'bg-info/10 text-info'
                            : 'bg-surface-elevated text-muted'
                        }`}
                      >
                        {t.is_oos ? 'OOS' : 'IS'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {limit < filtered.length ? (
            <button
              type="button"
              onClick={() => setLimit((l) => l + PAGE)}
              className="mt-2 rounded border border-border px-2.5 py-1 text-[11px] text-primary hover:bg-surface-hover"
            >
              Show {Math.min(PAGE, filtered.length - limit)} more
            </button>
          ) : null}

          <p className="mt-2 text-[11px] text-muted">
            A per-trade detail endpoint is not exposed by the current API — rows
            show only the fields the backtester returns.
          </p>
        </>
      )}
    </SectionCard>
  )
}
