import { useMemo, useState } from 'react'
import type { DailyPnl } from '../../types/analytics'
import { formatPercent, formatUsd } from '../../lib/format'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}

/** Monday-indexed weekday (0 = Mon … 6 = Sun) for a Date. */
function mondayIndex(d: Date): number {
  return (d.getDay() + 6) % 7
}

interface DayCell {
  day: number
  iso: string
  inMonth: boolean
  data?: DailyPnl
}

/**
 * Month calendar of daily P&L — the signature view from the legacy Streamlit
 * analytics page. Read-only; every figure comes straight from `daily_pnl`.
 */
export function MonthlyCalendar({
  daily,
  initialBalance,
}: {
  daily: DailyPnl[]
  initialBalance: number
}) {
  const byIso = useMemo(() => {
    const map = new Map<string, DailyPnl>()
    for (const d of daily) map.set(d.date, d)
    return map
  }, [daily])

  // Default to the month of the most recent trading day.
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

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 }))}
            className="rounded border border-border px-2 py-0.5 text-xs text-secondary hover:text-primary"
            aria-label="Previous month"
          >
            ‹
          </button>
          <span className="font-mono text-sm text-primary">
            {MONTHS[cursor.m]} {cursor.y}
          </span>
          <button
            type="button"
            onClick={() => setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 }))}
            className="rounded border border-border px-2 py-0.5 text-xs text-secondary hover:text-primary"
            aria-label="Next month"
          >
            ›
          </button>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[11px] text-muted">
          <span>Trades <span className="text-secondary">{summary.trades}</span></span>
          <span>Wins <span className="text-secondary">{summary.wins}</span></span>
          <span>
            PnL{' '}
            <span className={summary.pnl >= 0 ? 'text-positive' : 'text-negative'}>
              {signedUsd(summary.pnl)}
            </span>
          </span>
          <span>
            Gain{' '}
            <span className={gainPct >= 0 ? 'text-positive' : 'text-negative'}>
              {gainPct >= 0 ? '+' : ''}
              {formatPercent(gainPct)}
            </span>
          </span>
        </div>
      </div>

      <div className="mx-auto max-w-3xl">
        <div className="grid grid-cols-7 text-[10px] font-medium uppercase tracking-wider text-muted">
          {WEEKDAYS.map((w) => (
            <div key={w} className="px-1 pb-1 text-center">
              {w}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 overflow-hidden rounded-lg border border-border-subtle">
          {cells.map((c, i) => {
            const col = i % 7
            const weekend = col >= 5
            if (!c.inMonth) {
              return (
                <div
                  key={c.iso}
                  className={`min-h-[68px] border-b border-r border-border-subtle/60 ${
                    col === 6 ? 'border-r-0' : ''
                  } ${weekend ? 'bg-surface-elevated/10' : ''}`}
                />
              )
            }
            const d = c.data
            const intensity = d ? Math.min(0.2, 0.06 + (Math.abs(d.net_profit) / dayMax) * 0.14) : 0
            const bg = d
              ? d.net_profit >= 0
                ? `rgba(34,197,94,${intensity})`
                : `rgba(239,68,68,${intensity})`
              : undefined
            const dayPct =
              d && initialBalance > 0 ? (d.net_profit / initialBalance) * 100 : null
            return (
              <div
                key={c.iso}
                className={`flex min-h-[68px] flex-col border-b border-r border-border-subtle/60 px-1.5 py-1 ${
                  col === 6 ? 'border-r-0' : ''
                } ${!d && weekend ? 'bg-surface-elevated/10' : ''}`}
                style={bg ? { backgroundColor: bg } : undefined}
                title={
                  d
                    ? `${c.iso}: ${signedUsd(d.net_profit)} · ${d.trades} trade${d.trades === 1 ? '' : 's'} · ${d.wins}W`
                    : c.iso
                }
              >
                <div
                  className={`text-right text-[10px] tabular-nums ${
                    d ? 'text-secondary' : 'text-muted/70'
                  }`}
                >
                  {c.day}
                </div>
                {d ? (
                  <div className="mt-auto leading-tight">
                    <div
                      className={`font-mono text-[12px] font-semibold tabular-nums ${
                        d.net_profit >= 0 ? 'text-positive' : 'text-negative'
                      }`}
                    >
                      {signedUsd(d.net_profit)}
                    </div>
                    <div className="flex items-baseline justify-between font-mono text-[9px] text-muted">
                      <span>{dayPct !== null ? `${dayPct >= 0 ? '+' : ''}${dayPct.toFixed(2)}%` : ''}</span>
                      <span>{d.trades}t</span>
                    </div>
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
