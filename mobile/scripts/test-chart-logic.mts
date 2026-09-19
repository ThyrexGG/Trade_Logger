/**
 * Checks the Killzone chart's pure helpers with node (no emulator needed):  npm run test:chart
 * Session windows are New York clock time, so they must follow US daylight saving.
 */
import assert from 'node:assert/strict'
import { buildSessions, nearestBarIndex, nyParts, previousLevels, priceRange, spreadLabels } from '../src/scanner/chartLogic.ts'

const utc = (iso: string) => Math.floor(Date.parse(iso) / 1000)
const bar = (iso: string, o: number, h: number, l: number, c: number) => ({ time: utc(iso), open: o, high: h, low: l, close: c })

let passed = 0
const test = (name: string, fn: () => void) => {
  fn()
  passed += 1
  console.log(`ok  ${name}`)
}

test('nyParts follows daylight saving', () => {
  assert.deepEqual(nyParts(utc('2026-09-15T13:30:00Z')), { date: '2026-09-15', minutes: 9 * 60 + 30 }) // EDT = UTC-4
  assert.deepEqual(nyParts(utc('2026-01-15T14:30:00Z')), { date: '2026-01-15', minutes: 9 * 60 + 30 }) // EST = UTC-5
  assert.deepEqual(nyParts(utc('2026-09-16T00:00:00Z')), { date: '2026-09-15', minutes: 20 * 60 }) // 8pm the evening before
})

test('buildSessions groups candles into the right killzones', () => {
  const candles = [
    bar('2026-09-15T06:00:00Z', 1, 2, 0.5, 1.5), // 02:00 NY -> LONDON
    bar('2026-09-15T07:00:00Z', 1.5, 3, 1, 2), // 03:00 NY -> LONDON
    bar('2026-09-15T09:00:00Z', 2, 2.2, 1.9, 2.1), // 05:00 NY -> outside every window
    bar('2026-09-15T13:30:00Z', 2, 2.5, 1.8, 2.2), // 09:30 NY -> NY AM
    bar('2026-09-15T14:00:00Z', 2.2, 4, 2.1, 3.5), // 10:00 NY -> NY AM
    bar('2026-09-15T15:00:00Z', 3.5, 3.6, 3, 3.1), // 11:00 NY -> outside
  ]
  const s = buildSessions(candles)
  assert.deepEqual(s.map((x) => x.name), ['LONDON', 'NY AM'])
  assert.equal(s[0].high, 3)
  assert.equal(s[0].low, 0.5)
  assert.equal(s[1].high, 4)
  assert.equal(s[1].low, 1.8)
})

test('a session level counts as taken only after the session ends', () => {
  const candles = [
    bar('2026-09-15T06:00:00Z', 1, 2, 0.5, 1.5), // LONDON high 2, low 0.5
    bar('2026-09-15T07:00:00Z', 1.5, 2, 1, 1.8),
    bar('2026-09-15T10:00:00Z', 1.8, 2.4, 1.7, 2.3), // after the session, trades above 2 -> high taken
    bar('2026-09-15T11:00:00Z', 2.3, 2.5, 1.6, 2.0), // low 0.5 never traded
  ]
  const [london] = buildSessions(candles)
  assert.equal(london.highTakenAt, utc('2026-09-15T10:00:00Z'))
  assert.equal(london.lowTakenAt, null)
})

test('previousLevels needs a full prior day and does not invent a week', () => {
  const one = [bar('2026-09-15T13:00:00Z', 1, 2, 0.5, 1)]
  assert.equal(previousLevels(one).prevDay, null)
  const two = [bar('2026-09-14T13:00:00Z', 1, 5, 0.2, 1), bar('2026-09-15T13:00:00Z', 1, 2, 0.5, 1)]
  const l = previousLevels(two)
  assert.deepEqual(l.prevDay, { high: 5, low: 0.2 })
  assert.equal(l.prevWeek, null)
})

test('nearestBarIndex snaps to the last bar at or before the time', () => {
  const c = [bar('2026-09-15T10:00:00Z', 1, 1, 1, 1), bar('2026-09-15T10:15:00Z', 1, 1, 1, 1), bar('2026-09-15T10:30:00Z', 1, 1, 1, 1)]
  assert.equal(nearestBarIndex(c, utc('2026-09-15T10:20:00Z')), 1)
  assert.equal(nearestBarIndex(c, utc('2026-09-15T09:00:00Z')), 0) // before the first bar -> clamp
  assert.equal(nearestBarIndex(c, utc('2026-09-15T12:00:00Z')), 2)
})

test('priceRange pulls in liquidity beyond the candles, and ignores levels already inside', () => {
  const c = [bar('2026-09-15T10:00:00Z', 10, 12, 9, 11)]
  const inside = priceRange(c, [10.5, null, undefined])
  assert.ok(inside.min < 9 && inside.max > 12 && inside.max < 12.5)
  const beyond = priceRange(c, [20, 1])
  assert.ok(beyond.max > 20 && beyond.min < 1)
  assert.deepEqual(priceRange([], [5]), { min: 0, max: 1 })
})

test('spreadLabels keeps tags apart and inside the plot', () => {
  const out = spreadLabels([50, 51, 52, 300], 13, 6, 200)
  const sorted = [...out].sort((a, b) => a - b)
  for (let i = 1; i < sorted.length; i++) assert.ok(sorted[i] - sorted[i - 1] >= 13 - 1e-9)
  assert.ok(Math.max(...out) <= 200 && Math.min(...out) >= 6)
})

console.log(`\n${passed} chart-logic checks passed`)
