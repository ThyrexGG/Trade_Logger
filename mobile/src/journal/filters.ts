import type { JournalTradeItem } from '../types/journal'

export type DateFilter = 'today' | 'week' | 'month' | 'all'

export const DATE_FILTERS: { key: DateFilter; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This week' },
  { key: 'month', label: 'This month' },
  { key: 'all', label: 'All time' },
]

/** Same rule as the web Journal: a timestamp with no zone is UTC (that is how the backend stores exit_time). */
export function parseTime(iso: string): number {
  const hasZone = /[zZ]|[+-]\d\d:\d\d$/.test(iso)
  const t = new Date(hasZone ? iso : `${iso}Z`).getTime()
  return Number.isNaN(t) ? 0 : t
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

/** Start of the ISO (Monday-based) week, at local midnight — same as the web. */
function startOfWeek(d: Date): Date {
  const out = startOfDay(d)
  const day = out.getDay()
  out.setDate(out.getDate() - (day === 0 ? 6 : day - 1))
  return out
}

export function cutoffFor(filter: DateFilter, now = new Date()): number {
  if (filter === 'today') return startOfDay(now).getTime()
  if (filter === 'week') return startOfWeek(now).getTime()
  if (filter === 'month') return new Date(now.getFullYear(), now.getMonth(), 1).getTime()
  return 0
}

export function filterEntries(entries: JournalTradeItem[], account: string, dateFilter: DateFilter): JournalTradeItem[] {
  const cutoff = cutoffFor(dateFilter)
  return entries
    .filter((e) => account === 'ALL' || e.account_id === account)
    .filter((e) => cutoff === 0 || parseTime(e.exit_time) >= cutoff)
    .sort((a, b) => parseTime(b.exit_time) - parseTime(a.exit_time))
}

export interface JournalSummary {
  total: number
  wins: number
  losses: number
  net: number
}

export function summarize(entries: JournalTradeItem[]): JournalSummary {
  let wins = 0
  let losses = 0
  let net = 0
  for (const e of entries) {
    if (e.net_profit > 0) wins++
    else if (e.net_profit < 0) losses++
    net += e.net_profit
  }
  return { total: entries.length, wins, losses, net: Math.round(net * 100) / 100 }
}

export function formatDuration(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes <= 0) return '—'
  if (minutes < 60) return `${Math.round(minutes)}m`
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h < 24) return m ? `${h}h ${m}m` : `${h}h`
  const d = Math.floor(h / 24)
  return `${d}d ${h % 24}h`
}
