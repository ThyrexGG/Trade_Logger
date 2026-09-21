import { formatSignedAmount } from '../../lib/format'
import type { JournalTradeItem, TradeLeg } from '../../types/operations'

const tone = (v: number) => (v > 0 ? 'text-positive' : v < 0 ? 'text-negative' : 'text-secondary')
const when = (iso: string) => iso.slice(5, 16).replace('T', ' ')

/** How many exits the position had, or null for an ordinary single-exit trade. */
export function exitCount(entry: JournalTradeItem): number | null {
  const n = entry.legs?.length ?? 0
  return n > 0 ? n : null
}

/** "3 partials + final" — the one-line answer to "which was partial and which was the main exit?" */
export function legsSummary(entry: JournalTradeItem): string {
  const legs = entry.legs ?? []
  const partials = legs.filter((l) => l.kind === 'partial').length
  const part = `${partials} partial${partials === 1 ? '' : 's'}`
  return entry.position_open ? `${part} · position still open` : `${part} + final exit`
}

function LegRow({ leg }: { leg: TradeLeg }) {
  const final = leg.kind === 'final'
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-1">
      <span className={`w-20 shrink-0 text-[11px] font-semibold ${final ? 'text-accent' : 'text-secondary'}`}>
        {final ? 'Final exit' : `Partial ${leg.n}`}
      </span>
      <span className="font-mono text-[11px] text-muted">{when(leg.time)}</span>
      {leg.volume != null && leg.price != null ? (
        <span className="font-mono text-[11px] text-secondary">
          {leg.volume} @ {leg.price}
        </span>
      ) : null}
      <span className={`ml-auto font-mono text-[11px] tabular-nums ${tone(leg.net)}`}>{formatSignedAmount(leg.net)}</span>
    </li>
  )
}

/** Small pill for a trade row / card header: "4 exits". */
export function ExitsBadge({ entry }: { entry: JournalTradeItem }) {
  const n = exitCount(entry)
  if (n === null) return null
  return (
    <span
      className="rounded border border-accent/30 bg-accent/10 px-1.5 py-px text-[10px] font-medium text-accent"
      title={`${legsSummary(entry)} — the P&L shown is the whole position`}
    >
      {entry.position_open ? `${n} partial${n === 1 ? '' : 's'} · open` : `${n} exits`}
    </span>
  )
}

/** Every exit of a scaled-out trade, oldest first, partials labelled apart from the final exit. */
export function TradeLegs({ entry }: { entry: JournalTradeItem }) {
  const legs = entry.legs ?? []
  if (legs.length === 0) return null
  const total = legs.reduce((s, l) => s + l.net, 0)
  return (
    <div className="rounded border border-border bg-background/40 px-3 py-2">
      <p className="text-[11px] text-muted">
        One trade, {legs.length} exit{legs.length === 1 ? '' : 's'} — {legsSummary(entry)}
      </p>
      <ul className="mt-1 divide-y divide-border-subtle/60">
        {legs.map((l) => (
          <LegRow key={`${l.n}:${l.trade_id ?? l.time}`} leg={l} />
        ))}
      </ul>
      <p className="mt-1 flex justify-between border-t border-border pt-1 text-[11px] text-muted">
        <span>Position total</span>
        <span className={`font-mono tabular-nums ${tone(total)}`}>{formatSignedAmount(total)}</span>
      </p>
    </div>
  )
}
