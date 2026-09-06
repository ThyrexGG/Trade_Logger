import { useCallback, useEffect, useMemo, useState } from 'react'
import type { DayTrade, DailyPnl } from '../../types/analytics'
import { getDayTrades } from '../../api/analytics'
import { formatPercent, formatUsd } from '../../lib/format'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}

/** Monday-indexed weekday (0 = Mon … 6 = Sun). */
function mondayIndex(d: Date): number {
  return (d.getDay() + 6) % 7
}

const TODAY_ISO = new Date().toISOString().slice(0, 10)

interface DayCell {
  day: number
  iso: string
  inMonth: boolean
  data?: DailyPnl
}

/**
 * Month calendar of daily P&L — the signature view from the legacy analytics
 * page. Full width, one uniform grid; read-only, every figure straight from
 * `daily_pnl`.
 */
function fmtTime(iso: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function DayDetail({
  date,
  account,
  symbols,
  onClose,
}: {
  date: string
  account: string
  symbols: string[]
  onClose: () => void
}) {
  const [trades, setTrades] = useState<DayTrade[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const c = new AbortController()
    setTrades(null)
    setError(null)
    getDayTrades(date, { account, symbols }, c.signal)
      .then((r) => setTrades(r.trades))
      .catch((e: unknown) => {
        if (c.signal.aborted) return
        setError(e instanceof Error ? e.message : 'Failed to load trades')
      })
    return () => c.abort()
  }, [date, account, symbols])

  const net = trades ? trades.reduce((s, t) => s + t.net_profit, 0) : 0

  return (
    <div className="mt-3 rounded-lg border border-border-subtle bg-surface-elevated/30 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-primary">
          {new Date(`${date}T00:00:00`).toLocaleDateString(undefined, {
            weekday: 'long', month: 'short', day: 'numeric',
          })}
          {trades ? (
            <span className={`ml-2 font-mono text-xs ${net >= 0 ? 'text-positive' : 'text-negative'}`}>
              {signedUsd(net)} · {trades.length} trade{trades.length === 1 ? '' : 's'}
            </span>
          ) : null}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-muted hover:bg-surface-hover hover:text-primary"
          aria-label="Close day detail"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {error ? (
        <p className="text-[11px] text-negative">{error}</p>
      ) : !trades ? (
        <p className="text-[11px] text-muted">Loading…</p>
      ) : trades.length === 0 ? (
        <p className="text-[11px] text-muted">No trades closed on this day.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="text-muted">
              <tr>
                <th className="py-1 pr-3">Symbol</th>
                <th className="py-1 pr-3">Side</th>
                <th className="py-1 pr-3 text-right">Volume</th>
                <th className="py-1 pr-3 text-right">Entry</th>
                <th className="py-1 pr-3 text-right">Exit</th>
                <th className="py-1 pr-3">Closed</th>
                <th className="py-1 pr-3">Tag</th>
                <th className="py-1 text-right">Net P&amp;L</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {trades.map((t) => (
                <tr key={t.trade_id} className="border-t border-border-subtle/50">
                  <td className="py-1 pr-3 text-secondary">{t.symbol}</td>
                  <td className={`py-1 pr-3 ${t.direction === 'LONG' ? 'text-positive' : 'text-negative'}`}>
                    {t.direction}
                  </td>
                  <td className="py-1 pr-3 text-right tabular-nums">{t.volume}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{t.entry_price}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{t.exit_price}</td>
                  <td className="py-1 pr-3 text-muted">{fmtTime(t.exit_time)}</td>
                  <td className="py-1 pr-3 text-muted">{t.setup_tag ?? '—'}</td>
                  <td
                    className={`py-1 text-right tabular-nums ${
                      t.net_profit > 0 ? 'text-positive' : t.net_profit < 0 ? 'text-negative' : 'text-secondary'
                    }`}
                  >
                    {signedUsd(t.net_profit)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function MonthlyCalendar({
  daily,
  initialBalance,
  account,
  symbols,
}: {
  daily: DailyPnl[]
  initialBalance: number
  account: string
  symbols: string[]
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const selectDay = useCallback(
    (iso: string) => setSelected((cur) => (cur === iso ? null : iso)),
    [],
  )

  const byIso = useMemo(() => {
    const map = new Map<string, DailyPnl>()
    for (const d of daily) map.set(d.date, d)
    return map
  }, [daily])

  const lastIso = daily.length ? daily[daily.length - 1].date : null
  const [cursor, setCursor] = useState(() => {
    const base = lastIso ? new Date(`${lastIso}T00:00:00`) : new Date()
    return { y: base.getFullYear(), m: base.getMonth() }
  })

  const firstDay = new Date(cursor.y, cursor.m, 1)
  const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate()
  const lead = mondayIndex(firstDay)

  const cells: DayCell[] = []
  for (let i = 0; i < lead; i += 1) cells.push({ day: 0, iso: `lead-${i}`, inMonth: false })
  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = `${cursor.y}-${String(cursor.m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    cells.push({ day, iso, inMonth: true, data: byIso.get(iso) })
  }
  while (cells.length % 7 !== 0) cells.push({ day: 0, iso: `trail-${cells.length}`, inMonth: false })

  const monthDays = cells.filter((c) => c.inMonth && c.data).map((c) => c.data as DailyPnl)
  const summary = monthDays.reduce(
    (acc, d) => {
      acc.trades += d.trades
      acc.wins += d.wins
      acc.pnl += d.net_profit
      return acc
    },
    { trades: 0, wins: 0, pnl: 0 },
  )
  const gainPct = initialBalance > 0 ? (summary.pnl / initialBalance) * 100 : 0
  const dayMax = Math.max(1, ...monthDays.map((d) => Math.abs(d.net_profit)))

  const Chip = ({ label, value, tone }: { label: string; value: string; tone?: 'pos' | 'neg' }) => (
    <span className="flex items-baseline gap-1 rounded bg-surface-elevated/50 px-2 py-1">
      <span className="text-[10px] uppercase tracking-wide text-muted">{label}</span>
      <span
        className={`font-mono text-xs tabular-nums ${
          tone === 'pos' ? 'text-positive' : tone === 'neg' ? 'text-negative' : 'text-secondary'
        }`}
      >
        {value}
      </span>
    </span>
  )

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 }))}
            className="rounded p-1 text-muted hover:bg-surface-hover hover:text-primary"
            aria-label="Previous month"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <span className="min-w-[9.5rem] text-center text-sm font-semibold text-primary">
            {MONTHS[cursor.m]} {cursor.y}
          </span>
          <button
            type="button"
            onClick={() => setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 }))}
            className="rounded p-1 text-muted hover:bg-surface-hover hover:text-primary"
            aria-label="Next month"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Chip label="Trades" value={String(summary.trades)} />
          <Chip label="Wins" value={String(summary.wins)} />
          <Chip label="P&L" value={signedUsd(summary.pnl)} tone={summary.pnl >= 0 ? 'pos' : 'neg'} />
          <Chip
            label="Gain"
            value={`${gainPct >= 0 ? '+' : ''}${formatPercent(gainPct)}`}
            tone={gainPct >= 0 ? 'pos' : 'neg'}
          />
        </div>
      </div>

      <div className="grid grid-cols-7 border-b border-border-subtle text-[10px] font-medium uppercase tracking-wider text-muted">
        {WEEKDAYS.map((w) => (
          <div key={w} className="px-2 pb-1.5">
            {w}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((c, i) => {
          const col = i % 7
          const weekend = col >= 5
          const edges = `border-b border-border-subtle/50 ${col === 6 ? '' : 'border-r'}`

          if (!c.inMonth) {
            return (
              <div
                key={c.iso}
                className={`min-h-[92px] ${edges} ${weekend ? 'bg-surface-elevated/[0.04]' : ''}`}
              />
            )
          }

          const d = c.data
          const isToday = c.iso === TODAY_ISO
          const isSelected = c.iso === selected
          const intensity = d ? Math.min(0.16, 0.05 + (Math.abs(d.net_profit) / dayMax) * 0.11) : 0
          const bg = d
            ? d.net_profit >= 0
              ? `rgba(34,197,94,${intensity})`
              : `rgba(239,68,68,${intensity})`
            : undefined
          const dayPct = d && initialBalance > 0 ? (d.net_profit / initialBalance) * 100 : null

          const inner = (
            <>
              <span
                className={`text-[11px] tabular-nums ${
                  isToday ? 'font-semibold text-accent' : d ? 'text-secondary' : 'text-muted/60'
                }`}
              >
                {c.day}
              </span>
              {d ? (
                <div className="mt-auto text-left">
                  <div
                    className={`font-mono text-sm font-semibold tabular-nums ${
                      d.net_profit >= 0 ? 'text-positive' : 'text-negative'
                    }`}
                  >
                    {signedUsd(d.net_profit)}
                  </div>
                  <div className="flex items-baseline justify-between font-mono text-[10px] text-muted">
                    <span>{dayPct !== null ? `${dayPct >= 0 ? '+' : ''}${dayPct.toFixed(2)}%` : ''}</span>
                    <span>{d.trades}t</span>
                  </div>
                </div>
              ) : null}
            </>
          )

          const cls = `relative flex min-h-[92px] flex-col p-2 ${edges} ${
            !d && weekend ? 'bg-surface-elevated/[0.04]' : ''
          } ${isSelected ? 'ring-2 ring-inset ring-accent' : isToday ? 'ring-1 ring-inset ring-accent/50' : ''}`

          if (d) {
            return (
              <button
                key={c.iso}
                type="button"
                onClick={() => selectDay(c.iso)}
                className={`${cls} text-left transition-shadow hover:ring-2 hover:ring-inset hover:ring-accent/40`}
                style={bg ? { backgroundColor: bg } : undefined}
                title={`${c.iso} · ${signedUsd(d.net_profit)} · ${d.trades} trade${d.trades === 1 ? '' : 's'} · ${d.wins} win${d.wins === 1 ? '' : 's'} — click for trades`}
              >
                {inner}
              </button>
            )
          }
          return (
            <div key={c.iso} className={cls} title={c.iso}>
              {inner}
            </div>
          )
        })}
      </div>

      {selected ? (
        <DayDetail
          date={selected}
          account={account}
          symbols={symbols}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </div>
  )
}
