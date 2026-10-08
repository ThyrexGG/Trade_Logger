import { Link } from 'react-router-dom'
import type { PositionItem } from '../../types/positions'
import { assetName } from '../../lib/plainEnglish'
import { formatPrice, formatSignedAmount } from '../../lib/format'

function isLong(direction: string): boolean {
  const d = direction.toUpperCase()
  return d.startsWith('B') || d === 'LONG'
}

/** Where a price sits between the stop (0) and the target (1). Works for buys and sells alike. */
function along(price: number, sl: number, tp: number): number {
  return (price - sl) / (tp - sl)
}

const clamp = (v: number) => Math.max(0, Math.min(1, v))

/**
 * Position Track — each open trade drawn as its own short journey: stop on
 * the left, target on the right, the entry as a tick, and the live price as a
 * dot, with the stretch between entry and price filled in. Direction is
 * normalised so "toward the target" is always rightward, for buys and sells.
 * The R multiple (how many times the risk you are up or down) sits beside it.
 * A trade with no stop loss can't be drawn this way — it is flagged instead,
 * because that is the one thing a beginner most needs to see.
 */
export function PositionTracks({ positions }: { positions: PositionItem[] }) {
  if (positions.length === 0) {
    return <p className="py-2 text-sm text-muted">No open trades on this account.</p>
  }
  return (
    <ul className="divide-y divide-[var(--tl-border-subtle)]">
      {positions.map((p) => (
        <li key={p.position_id} className="py-3 first:pt-1 last:pb-1">
          <Track p={p} />
        </li>
      ))}
    </ul>
  )
}

function Track({ p }: { p: PositionItem }) {
  const long = isLong(p.direction)
  const hasSl = Number.isFinite(p.sl) && p.sl > 0
  const hasTp = Number.isFinite(p.tp) && p.tp > 0
  const name = assetName(p.symbol)
  const pnlTone = p.floating_pnl >= 0 ? 'text-positive' : 'text-negative'

  const risk = hasSl ? Math.abs(p.entry_price - p.sl) : 0
  const moved = (p.current_price - p.entry_price) * (long ? 1 : -1)
  const r = risk > 0 ? moved / risk : null

  // Without a target, place the target as far beyond entry as the stop is behind it, so the track still reads.
  const tp = hasTp ? p.tp : hasSl ? p.entry_price + (p.entry_price - p.sl) * 2 : NaN
  const drawable = hasSl && Number.isFinite(tp) && tp !== p.sl
  const fEntry = drawable ? clamp(along(p.entry_price, p.sl, tp)) : 0
  const fNow = drawable ? clamp(along(p.current_price, p.sl, tp)) : 0
  const lo = Math.min(fEntry, fNow)
  const hi = Math.max(fEntry, fNow)

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 sm:grid-cols-[11rem_minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className={`font-mono text-[11px] font-medium ${long ? 'text-positive' : 'text-negative'}`}>{long ? 'BUY' : 'SELL'}</span>
          <Link to={`/research/intelligence/asset/${encodeURIComponent(p.symbol)}`} className="font-medium text-primary hover:text-accent">
            {p.symbol}
          </Link>
          <span className="font-mono text-[11px] text-muted">{p.volume} lots</span>
        </div>
        {name ? <p className="truncate text-xs text-muted">{name}</p> : null}
      </div>

      <div className="col-span-2 row-start-2 sm:col-span-1 sm:row-start-auto">
        {drawable ? (
          <div className="relative h-7" role="img" aria-label={`${p.symbol}: stop ${formatPrice(p.sl)}, entry ${formatPrice(p.entry_price)}, now ${formatPrice(p.current_price)}${hasTp ? `, target ${formatPrice(p.tp)}` : ''}`}>
            <span className="absolute inset-x-0 top-[13px] h-[2px] rounded-full bg-[var(--tl-grid-line)]" />
            <span
              className={`absolute top-[13px] h-[2px] rounded-full ${moved >= 0 ? 'bg-positive' : 'bg-negative'}`}
              style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }}
            />
            <span className="absolute left-0 top-[8px] h-3 w-px bg-negative" />
            <span className="absolute -bottom-0.5 left-0 font-mono text-[9.5px] text-muted">SL {formatPrice(p.sl)}</span>
            <span className="absolute right-0 top-[8px] h-3 w-px bg-positive" style={{ opacity: hasTp ? 1 : 0.35 }} />
            <span className="absolute -bottom-0.5 right-0 font-mono text-[9.5px] text-muted">{hasTp ? `TP ${formatPrice(p.tp)}` : 'no target'}</span>
            <span className="absolute top-[9px] h-[10px] w-px bg-[var(--tl-text-secondary)]" style={{ left: `${fEntry * 100}%` }} title={`Entry ${formatPrice(p.entry_price)}`} />
            <span
              className={`absolute top-[9px] h-[10px] w-[10px] -translate-x-1/2 rounded-full border-2 border-surface ${moved >= 0 ? 'bg-positive' : 'bg-negative'}`}
              style={{ left: `${fNow * 100}%` }}
              title={`Now ${formatPrice(p.current_price)}`}
            />
          </div>
        ) : (
          <p className="rounded-[var(--tl-radius-sm)] border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-xs text-warning">
            No stop loss — there&rsquo;s no limit on how much this trade can lose.
          </p>
        )}
      </div>

      <div className="text-right">
        <p className={`tl-figure text-sm ${pnlTone}`}>{formatSignedAmount(p.floating_pnl)}</p>
        <p className="font-mono text-[11px] text-muted">{r != null ? `${r >= 0 ? '+' : ''}${r.toFixed(2)}R` : '—'}</p>
      </div>
    </div>
  )
}
