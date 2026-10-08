/**
 * Trading-session and killzone windows, placed on the viewer's own clock.
 *
 * Each window is defined in the time zone it actually belongs to, so daylight
 * saving shifts happen by themselves: the FX sessions in their exchange
 * cities, the killzones in New York time — the same boundaries the backend
 * scanner uses (market_data.detect_active_killzone).
 */

export interface Window {
  id: string
  label: string
  tz: string
  /** hours as decimals in `tz` local time; end may be 24 */
  start: number
  end: number
}

export const SESSIONS: Window[] = [
  { id: 'sydney', label: 'Sydney', tz: 'Australia/Sydney', start: 7, end: 16 },
  { id: 'tokyo', label: 'Tokyo', tz: 'Asia/Tokyo', start: 9, end: 18 },
  { id: 'london', label: 'London', tz: 'Europe/London', start: 8, end: 17 },
  { id: 'newyork', label: 'New York', tz: 'America/New_York', start: 8, end: 17 },
]

export const KILLZONES: Window[] = [
  { id: 'kz-asia', label: 'Asian range', tz: 'America/New_York', start: 20, end: 24 },
  { id: 'kz-london', label: 'London killzone', tz: 'America/New_York', start: 2, end: 5 },
  { id: 'kz-nyam', label: 'NY AM killzone', tz: 'America/New_York', start: 8.5, end: 11 },
  { id: 'kz-nypm', label: 'NY PM killzone', tz: 'America/New_York', start: 13.5, end: 16 },
]

/** Offset of `tz` from UTC at instant `ms`, in ms (e.g. +3_600_000 for UTC+1). */
function tzOffset(tz: string, ms: number): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(ms))
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0)
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return asUtc - ms
}

/** The calendar date (y, m, d) it is in `tz` at instant `ms`. */
function dateIn(tz: string, ms: number): [number, number, number] {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(ms))
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0)
  return [get('year'), get('month') - 1, get('day')]
}

/** UTC ms of `hours` o'clock on calendar day (y, m, d) in `tz`. */
function zonedToUtc(tz: string, y: number, m: number, d: number, hours: number): number {
  const guess = Date.UTC(y, m, d) + hours * 3_600_000
  const first = guess - tzOffset(tz, guess)
  return guess - tzOffset(tz, first)
}

export interface PlacedWindow {
  id: string
  label: string
  /** 0..1 position on the viewer's local day */
  from: number
  to: number
  startMs: number
  endMs: number
}

/**
 * Every occurrence of the windows that overlaps the viewer's local day
 * [dayStart, dayStart + 24h), clipped to it, as 0..1 fractions.
 */
export function placeWindows(windows: Window[], dayStart: number): PlacedWindow[] {
  const dayEnd = dayStart + 86_400_000
  const out: PlacedWindow[] = []
  for (const w of windows) {
    for (const shift of [-1, 0, 1]) {
      const [y, m, d] = dateIn(w.tz, dayStart + 12 * 3_600_000 + shift * 86_400_000)
      const s = zonedToUtc(w.tz, y, m, d, w.start)
      const e = zonedToUtc(w.tz, y, m, d, w.end)
      const a = Math.max(s, dayStart)
      const b = Math.min(e, dayEnd)
      if (b > a) out.push({ id: `${w.id}:${shift}`, label: w.label, from: (a - dayStart) / 86_400_000, to: (b - dayStart) / 86_400_000, startMs: s, endMs: e })
    }
  }
  return out
}

/** Local midnight (ms) of the day containing `now`. */
export function localDayStart(now: number): number {
  const d = new Date(now)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

export function formatDuration(ms: number): string {
  const mins = Math.max(0, Math.round(ms / 60_000))
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`
}
