/**
 * Pure helpers behind the Killzone chart — no React, so they can be unit-tested with node.
 * Ported from frontend/src/components/scanner/KillzoneChart.tsx so the boxes and levels
 * match the website's chart.
 */
import type { Candle } from '../types/market'

/** ICT killzone windows, in New York clock minutes-from-midnight — the same windows
 *  `killzone_scanner.py::_killzone_for_timestamp` uses. */
export const KILLZONES = [
  { name: 'ASIA', start: 20 * 60, end: 24 * 60, rgb: '59,130,246' },
  { name: 'LONDON', start: 2 * 60, end: 5 * 60, rgb: '239,68,68' },
  { name: 'NY AM', start: 9 * 60 + 30, end: 11 * 60, rgb: '20,184,166' },
  { name: 'NY PM', start: 13 * 60 + 30, end: 16 * 60, rgb: '217,70,239' },
] as const

let nyFmt: Intl.DateTimeFormat | null | undefined

/** Epoch seconds -> New York calendar date + minutes past midnight (follows US daylight saving),
 *  or null when this JS engine has no time-zone support. */
export function nyParts(ts: number): { date: string; minutes: number } | null {
  if (nyFmt === undefined) {
    try {
      nyFmt = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        hour12: false,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      nyFmt = null
    }
  }
  if (!nyFmt) return null
  const parts = nyFmt.formatToParts(new Date(ts * 1000))
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0)
  const hour = get('hour') % 24 // some engines print midnight as 24
  return {
    date: `${get('year')}-${String(get('month')).padStart(2, '0')}-${String(get('day')).padStart(2, '0')}`,
    minutes: hour * 60 + get('minute'),
  }
}

export interface SessionBox {
  name: string
  rgb: string
  from: number
  to: number
  high: number
  low: number
  /** Set once the session has ended and price later traded through the level. */
  highTakenAt: number | null
  lowTakenAt: number | null
}

/** Group candles into killzone session instances, tracking each session's high/low and when
 *  (if ever) price later traded through them. */
export function buildSessions(candles: Candle[]): SessionBox[] {
  const byKey = new Map<string, SessionBox>()
  for (const c of candles) {
    const p = nyParts(c.time)
    if (!p) return []
    for (const kz of KILLZONES) {
      if (p.minutes < kz.start || p.minutes >= kz.end) continue
      const key = `${kz.name}|${p.date}`
      const existing = byKey.get(key)
      if (existing) {
        existing.to = c.time
        existing.high = Math.max(existing.high, c.high)
        existing.low = Math.min(existing.low, c.low)
      } else {
        byKey.set(key, { name: kz.name, rgb: kz.rgb, from: c.time, to: c.time, high: c.high, low: c.low, highTakenAt: null, lowTakenAt: null })
      }
    }
  }
  const sessions = [...byKey.values()].sort((a, b) => a.from - b.from)
  // A level only counts as taken AFTER its session closes — during it price is still forming that high/low.
  for (const s of sessions) {
    for (const c of candles) {
      if (c.time <= s.to) continue
      if (s.highTakenAt === null && c.high > s.high) s.highTakenAt = c.time
      if (s.lowTakenAt === null && c.low < s.low) s.lowTakenAt = c.time
      if (s.highTakenAt !== null && s.lowTakenAt !== null) break
    }
  }
  return sessions
}

/** Previous completed day's / week's high and low from the candles already loaded; null when the
 *  window doesn't cover a full prior period (a missing level beats a wrong one). */
export function previousLevels(candles: Candle[]): {
  prevDay: { high: number; low: number } | null
  prevWeek: { high: number; low: number } | null
} {
  const days = new Map<string, { high: number; low: number }>()
  for (const c of candles) {
    const p = nyParts(c.time)
    if (!p) return { prevDay: null, prevWeek: null }
    const d = days.get(p.date)
    if (d) {
      d.high = Math.max(d.high, c.high)
      d.low = Math.min(d.low, c.low)
    } else {
      days.set(p.date, { high: c.high, low: c.low })
    }
  }
  const keys = [...days.keys()].sort()
  const prevDay = keys.length >= 2 ? (days.get(keys[keys.length - 2]) ?? null) : null
  let prevWeek: { high: number; low: number } | null = null
  if (keys.length >= 7) {
    const slice = keys.slice(-6, -1).map((k) => days.get(k)!)
    prevWeek = { high: Math.max(...slice.map((d) => d.high)), low: Math.min(...slice.map((d) => d.low)) }
  }
  return { prevDay, prevWeek }
}

/** Index of the last candle at or before `ts`, so an event found on one timeframe still lands on the
 *  right bar when the chart shows another. Clamped into the loaded range. */
export function nearestBarIndex(candles: Candle[], ts: number): number {
  let result = 0
  for (let i = 0; i < candles.length; i++) {
    if (candles[i].time <= ts) result = i
    else break
  }
  return result
}

/** The visible price range: every candle, plus the nearest liquidity target on each side (and the
 *  focused candidate's target) when they sit outside the candles — "draw on liquidity" is usually
 *  beyond current price and would otherwise be off the chart. */
export function priceRange(candles: Candle[], extra: (number | null | undefined)[]): { min: number; max: number } {
  let min = Infinity
  let max = -Infinity
  for (const c of candles) {
    if (c.low < min) min = c.low
    if (c.high > max) max = c.high
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 }
  const candleMin = min
  const candleMax = max
  for (const v of extra) {
    if (v == null || !Number.isFinite(v)) continue
    if (v > candleMax) max = Math.max(max, v)
    if (v < candleMin) min = Math.min(min, v)
  }
  const pad = (max - min) * 0.04 || Math.abs(max) * 0.001 || 1
  return { min: min - pad, max: max + pad }
}

/** Nudge axis labels apart so they stay readable: sorted by y, each at least `gap` below the previous,
 *  and the whole stack kept above `bottom`. Returns the adjusted y for each input, in input order. */
export function spreadLabels(ys: number[], gap: number, top: number, bottom: number): number[] {
  const order = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y)
  let prev = top - gap
  const out = new Array<number>(ys.length)
  for (const o of order) {
    const y = Math.max(o.y, prev + gap)
    out[o.i] = y
    prev = y
  }
  let limit = bottom
  for (let k = order.length - 1; k >= 0; k--) {
    const i = order[k].i
    if (out[i] > limit) out[i] = limit
    limit = out[i] - gap
  }
  return out
}
