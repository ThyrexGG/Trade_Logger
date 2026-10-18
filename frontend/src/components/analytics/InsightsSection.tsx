import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { InsightBucket, RulesRow, StreakStats, TradeInsights } from '../../types/analytics'
import { SectionCard } from '../research/primitives'
import { formatUsd } from '../../lib/format'

/**
 * The "TradeZella-style" reports under the calendar (api/insights.py):
 * what breaking your own rules costs, streaks and best/worst days, and when
 * you trade best. Every card leads with one plain-English sentence; the
 * numbers sit underneath for anyone who wants them.
 */

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}

function toneText(v: number): string {
  return v > 0 ? 'text-positive' : v < 0 ? 'text-negative' : 'text-secondary'
}

function plural(n: number, word: string, many = `${word}s`): string {
  return `${n} ${n === 1 ? word : many}`
}

function winPct(wins: number, trades: number): number {
  return trades ? Math.round((wins / trades) * 100) : 0
}

function prettyDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

/** A figure in the house style: money in tone, never colour alone (the sign is in the text). */
function Money({ v, strong = false }: { v: number; strong?: boolean }) {
  return <span className={`tl-figure ${toneText(v)} ${strong ? 'font-semibold' : ''}`}>{signedUsd(v)}</span>
}

function Headline({ children }: { children: ReactNode }) {
  return <p className="text-sm leading-relaxed text-primary">{children}</p>
}

// ---------------------------------------------------------------------------
// Rules vs. results

const RULE_LABELS: Record<string, string> = {
  'By my rules': 'By my rules',
  'Bent my rules': 'Bent my rules',
  Rushed: 'Rushed / off-plan',
}

function RulePanel({ row, max }: { row: RulesRow; max: number }) {
  return (
    <div className="flex flex-col rounded border border-border-subtle bg-surface-elevated/30 p-3">
      <span className="text-xs text-secondary">{RULE_LABELS[row.tag] ?? row.tag}</span>
      {row.trades ? (
        <>
          <span className={`tl-figure mt-1 text-lg ${toneText(row.net_profit)}`}>{signedUsd(row.net_profit)}</span>
          <span className="relative mt-2 h-1 rounded-full bg-surface-elevated" aria-hidden="true">
            <span
              className={`absolute inset-y-0 left-0 rounded-full ${row.net_profit >= 0 ? 'bg-positive' : 'bg-negative'}`}
              style={{ width: `${Math.max(3, (Math.abs(row.net_profit) / max) * 100)}%` }}
            />
          </span>
          <span className="mt-2 font-mono text-[10px] text-muted">
            {plural(row.trades, 'trade')} · {winPct(row.wins, row.trades)}% win
          </span>
          <span className="font-mono text-[10px] text-muted">avg {signedUsd(row.avg_per_trade)} a trade</span>
        </>
      ) : (
        <span className="mt-1 text-xs text-muted">No trades yet</span>
      )}
    </div>
  )
}

function RulesCard({ rows }: { rows: RulesRow[] }) {
  const by = Object.fromEntries(rows.map((r) => [r.tag, r])) as Record<string, RulesRow>
  const empty: RulesRow = { tag: '', trades: 0, wins: 0, net_profit: 0, avg_per_trade: 0 }
  const kept = by['By my rules'] ?? empty
  const bent = by['Bent my rules'] ?? empty
  const rushed = by.Rushed ?? empty
  const unmarked = by['Not marked'] ?? empty
  const marked = kept.trades + bent.trades + rushed.trades
  const total = marked + unmarked.trades
  const offN = bent.trades + rushed.trades
  const offNet = bent.net_profit + rushed.net_profit
  const max = Math.max(1e-9, ...[kept, bent, rushed].map((r) => Math.abs(r.net_profit)))
  const info =
    'Uses the one tap under each trade in the Journal: By my rules, Bent my rules or Rushed. Shows what each kind of trade made or lost, so you can see whether sticking to your plan pays.'

  // Nothing marked yet: a slim one-row prompt instead of a half-empty card.
  if (marked === 0) {
    return (
      <SectionCard title="Your rules vs. your results" feature info={info}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
          <div className="min-w-0 space-y-1">
            <Headline>You haven’t marked any trades yet, so this can’t show what breaking your rules costs.</Headline>
            <p className="text-xs text-secondary">
              Under each trade in the Journal, tap <span className="text-primary">By my rules</span>,{' '}
              <span className="text-primary">Bent my rules</span> or <span className="text-primary">Rushed</span>. One tap per trade.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="font-mono text-[11px] text-muted">0 of {plural(total, 'trade')} marked</span>
            <Link to="/workspace/journal" className="tl-btn tl-btn--secondary">
              Open the Journal
            </Link>
          </div>
        </div>
      </SectionCard>
    )
  }

  let headline: ReactNode
  if (offN === 0) {
    headline = (
      <>
        All {plural(marked, 'marked trade')} followed your rules — <Money v={kept.net_profit} strong /> so far.
      </>
    )
  } else if (offNet < 0) {
    headline = (
      <>
        Breaking your rules has cost you <span className="tl-figure font-semibold text-negative">{formatUsd(-offNet)}</span>{' '}
        over {plural(offN, 'trade')}.
      </>
    )
  } else {
    headline = (
      <>
        Your off-plan trades are up <Money v={offNet} strong /> over {plural(offN, 'trade')} — but that’s hard to repeat on purpose.
      </>
    )
  }

  return (
    <SectionCard title="Your rules vs. your results" feature info={info}>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-6">
        <div className="flex flex-col gap-2">
          <Headline>{headline}</Headline>
          {kept.trades > 0 && offN > 0 ? (
            <p className="text-xs text-secondary">
              A trade by your rules averages <Money v={kept.avg_per_trade} />; an off-plan one averages <Money v={offNet / offN} />.
            </p>
          ) : null}
          <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-1">
            <span className="font-mono text-[11px] text-muted">
              {marked} of {plural(total, 'trade')} marked
            </span>
            {unmarked.trades > 0 ? (
              <Link to="/workspace/journal" className="text-xs font-medium text-accent hover:underline">
                Mark the other {unmarked.trades} →
              </Link>
            ) : null}
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {[kept, bent, rushed].map((r, i) => (
            <RulePanel key={r.tag || i} row={r} max={max} />
          ))}
        </div>
      </div>
    </SectionCard>
  )
}

// ---------------------------------------------------------------------------
// Streaks & best days

function Cell({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`tl-figure mt-0.5 text-sm ${tone ?? 'text-primary'}`}>{value}</p>
      {sub ? <p className="font-mono text-[10px] text-muted">{sub}</p> : null}
    </div>
  )
}

function streakHeadline(s: StreakStats): ReactNode {
  const n = s.current_count
  if (s.current_kind === 'win') {
    return n >= 2 ? <>You’re on a {n}-trade winning streak.</> : <>Your last trade was a win.</>
  }
  if (s.current_kind === 'loss') {
    if (n >= 3) {
      return (
        <>
          {n} losses in a row{s.longest_loss > n ? <> (your worst run is {s.longest_loss})</> : <> — your longest losing run yet</>}. A good moment to
          step back.
        </>
      )
    }
    return n === 2 ? <>Two losses in a row.</> : <>Your last trade was a loss.</>
  }
  return <>Your last trade broke even.</>
}

function StreaksCard({ s }: { s: StreakStats }) {
  const days = s.green_days + s.red_days
  const dayTone = s.current_day_kind === 'win' ? 'text-positive' : s.current_day_kind === 'loss' ? 'text-negative' : 'text-secondary'
  return (
    <SectionCard
      title="Streaks & best days"
      info="Streaks count trades in the order they closed; a break-even trade ends a streak. Days use the same dates as the calendar, and days with no trades are skipped."
    >
      <div className="space-y-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
          <Headline>{streakHeadline(s)}</Headline>
          {days > 0 ? (
            <p className="shrink-0 font-mono text-[11px] text-muted">
              Days in a row now{' '}
              <span className={dayTone}>
                {s.current_day_kind === 'none' ? '—' : `${s.current_day_count} ${s.current_day_kind === 'win' ? 'green' : 'red'}`}
              </span>{' '}
              · best <span className="text-positive">{s.longest_green_days} green</span> · worst{' '}
              <span className="text-negative">{s.longest_red_days} red</span>
            </p>
          ) : null}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          <Cell
            label="Current streak"
            value={s.current_kind === 'none' ? '—' : plural(s.current_count, s.current_kind === 'win' ? 'win' : 'loss', s.current_kind === 'win' ? 'wins' : 'losses')}
            sub="in a row"
            tone={s.current_kind === 'win' ? 'text-positive' : s.current_kind === 'loss' ? 'text-negative' : undefined}
          />
          <Cell label="Best winning run" value={plural(s.longest_win, 'trade')} sub="wins in a row" />
          <Cell label="Worst losing run" value={plural(s.longest_loss, 'trade')} sub="losses in a row" />
          <Cell
            label="Green days"
            value={`${s.green_days} of ${days}`}
            sub={`${days ? Math.round((s.green_days / days) * 100) : 0}% of trading days`}
          />
          <Cell
            label="Best day"
            value={s.best_day ? signedUsd(s.best_day.net_profit) : '—'}
            sub={s.best_day ? prettyDate(s.best_day.date) : undefined}
            tone={s.best_day ? toneText(s.best_day.net_profit) : undefined}
          />
          <Cell
            label="Worst day"
            value={s.worst_day ? signedUsd(s.worst_day.net_profit) : '—'}
            sub={s.worst_day ? prettyDate(s.worst_day.date) : undefined}
            tone={s.worst_day ? toneText(s.worst_day.net_profit) : undefined}
          />
        </div>
      </div>
    </SectionCard>
  )
}

// ---------------------------------------------------------------------------
// When you trade best

type Mode = 'day' | 'hour' | 'hold'
const MODES: [Mode, string][] = [
  ['day', 'Day of week'],
  ['hour', 'Time of day'],
  ['hold', 'Holding time'],
]
const MODE_KEY = 'tl.analytics.when'
const FULL_DAY: Record<string, string> = {
  Mon: 'Monday', Tue: 'Tuesday', Wed: 'Wednesday', Thu: 'Thursday', Fri: 'Friday', Sat: 'Saturday', Sun: 'Sunday',
}
const FEW = 3
/** Axis-only short forms (sentences use the full label from the API). */
const HOLD_AXIS: Record<string, string> = {
  lt5m: '< 5m', '5_15m': '5–15m', '15_60m': '15–60m', '1_4h': '1–4h', '4_24h': '4–24h', gt1d: '> 1 day',
}

function loadMode(): Mode {
  try {
    const v = localStorage.getItem(MODE_KEY)
    return v === 'hour' || v === 'hold' ? v : 'day'
  } catch {
    return 'day'
  }
}

/** "Tuesday" / "14:00–15:00" / "15–60 min" — how a bucket reads in a sentence. */
function bucketName(mode: Mode, b: InsightBucket): string {
  if (mode === 'day') return FULL_DAY[b.label] ?? b.label
  if (mode === 'hour') {
    const h = Number(b.key)
    return `${String(h).padStart(2, '0')}:00–${String((h + 1) % 24).padStart(2, '0')}:00`
  }
  return b.label.toLowerCase()
}

function whenHeadline(mode: Mode, buckets: InsightBucket[]): ReactNode {
  const traded = buckets.filter((b) => b.trades > 0)
  if (traded.length === 0) return <>No trades in this range.</>
  const solid = traded.filter((b) => b.trades >= FEW)
  const pool = solid.length ? solid : traded
  const best = pool.reduce((a, b) => (b.net_profit > a.net_profit ? b : a))
  const worst = pool.reduce((a, b) => (b.net_profit < a.net_profit ? b : a))
  const unit = mode === 'day' ? 'day' : mode === 'hour' ? 'hour' : 'holding time'
  const tail = (b: InsightBucket) => (
    <span className="text-secondary">
      {' '}
      (<Money v={b.net_profit} /> over {plural(b.trades, 'trade')})
    </span>
  )
  if (best.net_profit <= 0) {
    return (
      <>
        No {unit} is in profit overall yet. The smallest loss is{' '}
        <span className="font-medium">{bucketName(mode, best)}</span>
        {tail(best)}.
      </>
    )
  }
  return (
    <>
      Your best {unit} is <span className="font-medium">{bucketName(mode, best)}</span>
      {tail(best)}.{' '}
      {worst.net_profit < 0 && worst !== best ? (
        <>
          Your worst is <span className="font-medium">{bucketName(mode, worst)}</span>
          {tail(worst)}.
        </>
      ) : (
        <>Every {unit} you trade is in profit overall.</>
      )}
    </>
  )
}

/** Diverging columns: profit grows up from the baseline, loss grows down. Hover or tap a column for its numbers. */
function ColumnChart({ mode, buckets }: { mode: Mode; buckets: InsightBucket[] }) {
  const [active, setActive] = useState<number | null>(null)
  const max = Math.max(1e-9, ...buckets.map((b) => Math.abs(b.net_profit)))
  const hasPos = buckets.some((b) => b.net_profit > 0)
  const hasNeg = buckets.some((b) => b.net_profit < 0)
  // share of the plot height above the baseline
  const up = hasPos && hasNeg ? 0.5 : hasNeg ? 0 : 1
  const fallback = buckets.reduce((a, b, i) => (b.trades > 0 && (a < 0 || b.net_profit > buckets[a].net_profit) ? i : a), -1)
  const shown = active ?? (fallback >= 0 ? fallback : null)
  const cur = shown != null ? buckets[shown] : null
  const narrow = buckets.length > 12

  return (
    <div>
      <div className="flex min-h-[1.25rem] flex-wrap items-baseline gap-x-2 text-[11px]" aria-live="polite">
        {cur ? (
          <>
            <span className="font-medium text-primary">{bucketName(mode, cur)}</span>
            {cur.trades ? (
              <>
                <Money v={cur.net_profit} />
                <span className="font-mono text-muted">
                  {plural(cur.trades, 'trade')} · {winPct(cur.wins, cur.trades)}% win
                </span>
                {cur.trades < FEW ? <span className="text-muted">· too few trades to judge</span> : null}
              </>
            ) : (
              <span className="text-muted">no trades</span>
            )}
          </>
        ) : null}
      </div>

      <div className="relative mt-2 h-40" onMouseLeave={() => setActive(null)}>
        <span className="absolute inset-x-0 h-px bg-border" style={{ top: `${up * 100}%` }} aria-hidden="true" />
        <div className="absolute inset-0 flex gap-[2px]">
          {buckets.map((b, i) => {
            const h = (Math.abs(b.net_profit) / max) * 100
            const isOn = i === shown
            const pos = b.net_profit > 0
            const neg = b.net_profit < 0
            return (
              <button
                key={b.key}
                type="button"
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onClick={() => setActive(i)}
                aria-label={`${bucketName(mode, b)}: ${b.trades ? `${signedUsd(b.net_profit)}, ${plural(b.trades, 'trade')}, ${winPct(b.wins, b.trades)}% win` : 'no trades'}`}
                aria-pressed={isOn}
                data-silent
                className={`relative h-full min-w-0 flex-1 rounded-[4px] transition-colors ${i === active ? 'bg-surface-hover/50' : ''}`}
              >
                <span
                  aria-hidden="true"
                  className={`absolute left-1/2 w-[72%] -translate-x-1/2 transition-opacity ${narrow ? 'max-w-[1.1rem]' : 'max-w-[2.75rem]'} ${
                    pos ? 'rounded-t-[4px] bg-positive' : neg ? 'rounded-b-[4px] bg-negative' : 'bg-border'
                  } ${isOn ? 'opacity-100' : 'opacity-70'}`}
                  style={
                    pos
                      ? { bottom: `${(1 - up) * 100}%`, height: `max(2px, ${h * up}%)` }
                      : neg
                        ? { top: `${up * 100}%`, height: `max(2px, ${h * (1 - up)}%)` }
                        : b.trades
                          ? { top: `calc(${up * 100}% - 1px)`, height: '2px' }
                          : { display: 'none' }
                  }
                />
              </button>
            )
          })}
        </div>
      </div>

      {mode === 'hour' ? (
        // 24 columns are too narrow for a label each: every third hour, centred on its column and free to overflow it.
        <div className="relative mt-1.5 h-4" aria-hidden="true">
          {buckets.map((b, i) =>
            i % 3 === 0 ? (
              <span
                key={b.key}
                className={`absolute -translate-x-1/2 whitespace-nowrap font-mono text-[10px] ${i === shown ? 'text-primary' : 'text-muted'}`}
                style={{ left: `${((i + 0.5) / buckets.length) * 100}%` }}
              >
                {b.label}
              </span>
            ) : null,
          )}
        </div>
      ) : (
        <div className="mt-1.5 flex gap-[2px]" aria-hidden="true">
          {buckets.map((b, i) => (
            <span
              key={b.key}
              className={`min-w-0 flex-1 truncate text-center font-mono text-[10px] ${i === shown ? 'text-primary' : 'text-muted'}`}
              title={b.label}
            >
              {mode === 'hold' ? (HOLD_AXIS[b.key] ?? b.label) : b.label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function WhenCard({ insights }: { insights: TradeInsights }) {
  const [mode, setModeState] = useState<Mode>(loadMode)
  const setMode = (m: Mode) => {
    setModeState(m)
    try {
      localStorage.setItem(MODE_KEY, m)
    } catch {
      /* remembered per device when storage works */
    }
  }
  const buckets = mode === 'day' ? insights.by_weekday : mode === 'hour' ? insights.by_hour : insights.by_hold
  const tz = insights.timezone.replace(/_/g, ' ')

  return (
    <SectionCard
      title="When you trade best"
      info="Your profit or loss grouped by the day and hour you opened each trade (your local time) and by how long you held it. Groups with fewer than 3 trades are left out of the summary sentence."
    >
      <div className="space-y-3">
        <div className="tl-seg" role="tablist" aria-label="Group trades by">
          {MODES.map(([m, label]) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}>
              {label}
            </button>
          ))}
        </div>
        <Headline>{whenHeadline(mode, buckets)}</Headline>
        <ColumnChart key={mode} mode={mode} buckets={buckets} />
        <p className="text-[11px] text-muted">
          {mode === 'day'
            ? `By the day you opened the trade, in your time (${tz}).`
            : mode === 'hour'
              ? `By the hour you opened the trade, in your time (${tz}). Hover or tap a bar for its numbers.`
              : 'From open to close.'}
          {insights.open_unknown
            ? ` ${plural(insights.open_unknown, 'trade')} ${insights.open_unknown === 1 ? 'has' : 'have'} no recorded open time, so ${insights.open_unknown === 1 ? 'it’s' : 'they’re'} left out rather than guessed.`
            : ''}
        </p>
      </div>
    </SectionCard>
  )
}

// ---------------------------------------------------------------------------

export function InsightsSection({ insights }: { insights: TradeInsights }) {
  return (
    <>
      <RulesCard rows={insights.rules} />
      <StreaksCard s={insights.streaks} />
      <WhenCard insights={insights} />
    </>
  )
}
