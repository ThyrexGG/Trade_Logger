import type { DailyPnl } from '../../types/analytics'
import { localDayIso } from '../../lib/dates'

/** One square in the heatmap: a single calendar day on the viewer's clock. */
export interface HeatCell {
  iso: string
  col: number
  /** 0 = Mon … 6 = Sun */
  row: number
  future: boolean
  data?: DailyPnl
  /** cumulative net P&L from the first visible day through this one */
  cumulative: number
}

export interface HeatGrid {
  weeks: number
  cells: HeatCell[]
  /** |P&L| at the 90th percentile — anything at or above it gets full colour */
  scale: number
  /** first column index of each month that starts inside the window */
  monthMarks: { col: number; label: string }[]
  /** first visible day, for the analytics `start` filter */
  startIso: string
  todayIso: string
}

const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** YYYY-MM-DD of the LOCAL day — same buckets as the API's `daily_pnl` (it gets our timezone). */
export function isoDay(ms: number): string {
  return localDayIso(ms)
}

/** Local midnight of the Monday that starts the window ending this week. */
export function windowStartMs(weeks: number, now: number = Date.now()): number {
  const d = new Date(now)
  const dow = (d.getDay() + 6) % 7
  // calendar-day arithmetic (not "minus N × 24h"), so a daylight-saving change can't shift a day
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() - dow - (weeks - 1) * 7).getTime()
}

/** Local midnight `days` calendar days after `startMs`. */
function addDays(startMs: number, days: number): number {
  const d = new Date(startMs)
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days).getTime()
}

export function buildGrid(daily: DailyPnl[], weeks: number, now: number = Date.now()): HeatGrid {
  const byDay = new Map(daily.map((d) => [d.date.slice(0, 10), d]))
  const start = windowStartMs(weeks, now)
  const todayIso = isoDay(now)
  const cells: HeatCell[] = []
  const monthMarks: HeatGrid['monthMarks'] = []
  let running = 0
  let lastMonth = -1
  for (let i = 0; i < weeks * 7; i++) {
    const ms = addDays(start, i)
    const iso = isoDay(ms)
    const col = Math.floor(i / 7)
    const row = i % 7
    const data = byDay.get(iso)
    if (data) running += data.net_profit
    cells.push({ iso, col, row, future: iso > todayIso, data, cumulative: running })
    const month = new Date(ms).getMonth()
    if (row === 0 && month !== lastMonth) {
      // only label a month once its first Monday is in view, and keep labels from colliding
      if (!monthMarks.length || col - monthMarks[monthMarks.length - 1].col >= 3) {
        monthMarks.push({ col, label: SHORT_MONTHS[month] })
      }
      lastMonth = month
    }
  }
  const mags = cells
    .filter((c) => c.data && c.data.net_profit !== 0)
    .map((c) => Math.abs(c.data!.net_profit))
    .sort((a, b) => a - b)
  const scale = mags.length ? mags[Math.min(mags.length - 1, Math.floor(mags.length * 0.9))] : 1
  return { weeks, cells, scale: scale || 1, monthMarks, startIso: isoDay(start), todayIso }
}

/** 0..1 colour strength for a day's P&L, with a floor so a tiny day is still visible. */
export function intensity(pnl: number, scale: number): number {
  return 0.28 + 0.72 * Math.min(1, Math.abs(pnl) / scale)
}

export interface MonthSummary {
  pnl: number
  tradingDays: number
  greenDays: number
  trades: number
}

export function monthSummary(daily: DailyPnl[], now: number = Date.now()): MonthSummary {
  const prefix = isoDay(now).slice(0, 7)
  const rows = daily.filter((d) => d.date.startsWith(prefix))
  return {
    pnl: rows.reduce((s, d) => s + d.net_profit, 0),
    tradingDays: rows.length,
    greenDays: rows.filter((d) => d.net_profit > 0).length,
    trades: rows.reduce((s, d) => s + d.trades, 0),
  }
}

/** Consecutive green (or red) trading days ending at the most recent one. */
export function currentStreak(daily: DailyPnl[]): { length: number; green: boolean } | null {
  const rows = [...daily].filter((d) => d.net_profit !== 0).sort((a, b) => a.date.localeCompare(b.date))
  if (!rows.length) return null
  const green = rows[rows.length - 1].net_profit > 0
  let length = 0
  for (let i = rows.length - 1; i >= 0 && rows[i].net_profit > 0 === green; i--) length++
  return { length, green }
}

export function bestAndWorst(daily: DailyPnl[]): { best: DailyPnl | null; worst: DailyPnl | null } {
  let best: DailyPnl | null = null
  let worst: DailyPnl | null = null
  for (const d of daily) {
    if (!best || d.net_profit > best.net_profit) best = d
    if (!worst || d.net_profit < worst.net_profit) worst = d
  }
  return {
    best: best && best.net_profit > 0 ? best : null,
    worst: worst && worst.net_profit < 0 ? worst : null,
  }
}

export function prettyDate(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'short' }): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { ...opts, timeZone: 'UTC' })
}
