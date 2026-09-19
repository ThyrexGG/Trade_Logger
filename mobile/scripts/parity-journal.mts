// Parity check: the phone app's Journal filtering/summary must produce the same
// numbers as the website's. The web logic lives inside a React page, so this
// pulls the pure functions straight out of frontend/src/pages/JournalPage.tsx
// (never a copy) and runs both implementations over the same random trades,
// under several "now" dates and time zones.
//
//   npm run parity   (in mobile/; Node 24+ strips TypeScript types natively)
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const webSource = readFileSync(join(here, '../../frontend/src/pages/JournalPage.tsx'), 'utf8').split('\r\n').join('\n')

// Slice from `function parseTime` up to (and including) the end of `filterJournal`.
const start = webSource.indexOf('/** Treats a timestamp with no explicit timezone as UTC')
const endMarker = webSource.indexOf('/**\n * Trade journal (`/workspace/journal`)')
assert.ok(start > 0 && endMarker > start, 'could not locate the filter code in JournalPage.tsx — update the markers')
const webFilterCode = webSource.slice(start, endMarker)

const tmp = mkdtempSync(join(tmpdir(), 'tl-parity-'))
const webFile = join(tmp, 'web-filter.mts')
writeFileSync(
  webFile,
  `type DateFilter = 'today' | 'week' | 'month' | 'all'\ntype JournalResponse = any\n${webFilterCode}\nexport { filterJournal, dateFilterCutoff }\n`,
)
const web = await import(pathToFileURL(webFile).href)
const mobile = await import(pathToFileURL(join(here, '../src/journal/filters.ts')).href)

// --- deterministic data ------------------------------------------------------
let seed = 20260919
const rnd = () => {
  seed = (seed * 1664525 + 1013904223) % 4294967296
  return seed / 4294967296
}
const pick = <T,>(xs: T[]): T => xs[Math.floor(rnd() * xs.length)]

function isoVariants(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  const base = `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}T${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`
  return pick([base, base, `${base}Z`, `${base}.123Z`, `${base}+00:00`, `${base}+02:00`, `${base}-05:00`])
}

const NOWS = [
  new Date(2026, 8, 16, 12, 0, 0), // Wed mid-week
  new Date(2026, 8, 20, 23, 59, 59), // Sunday night (ISO week edge)
  new Date(2026, 8, 14, 0, 0, 0), // Monday 00:00 exactly
  new Date(2026, 9, 1, 0, 0, 0), // first of month 00:00
  new Date(2026, 11, 31, 23, 30, 0), // year end
  new Date(2026, 0, 1, 0, 0, 1), // new year
]

const ACCOUNTS = ['CAP_A', 'CAP_B', 'MT5_1']
const FILTERS = ['today', 'week', 'month', 'all'] as const

const RealDate = Date
function withNow<T>(now: Date, fn: () => T): T {
  const fixed = now.getTime()
  class FakeDate extends RealDate {
    constructor(...args: unknown[]) {
      // @ts-expect-error variadic passthrough
      if (args.length === 0) super(fixed)
      // @ts-expect-error variadic passthrough
      else super(...args)
    }
    static now() {
      return fixed
    }
  }
  ;(globalThis as { Date: unknown }).Date = FakeDate
  try {
    return fn()
  } finally {
    ;(globalThis as { Date: unknown }).Date = RealDate
  }
}

// Windows Node ignores TZ from the shell, but assigning it inside the process works.
const ZONES = ['UTC', 'Asia/Bangkok', 'Asia/Kolkata', 'Europe/London', 'America/New_York', 'America/Los_Angeles', 'Pacific/Auckland']

let checked = 0
for (const zone of ZONES) {
process.env.TZ = zone
const zoneNow = NOWS.map((n) => new RealDate(n.getFullYear(), n.getMonth(), n.getDate(), n.getHours(), n.getMinutes(), n.getSeconds()))
for (const now of zoneNow) {
  // 400 trades spread across the ~3 weeks around `now`, including boundary-hugging ones.
  const entries = Array.from({ length: 400 }, (_, i) => {
    const offsetMin = Math.floor((rnd() - 0.75) * 60 * 24 * 21)
    const t = new RealDate(now.getTime() + offsetMin * 60_000)
    const cents = Math.round((rnd() - 0.45) * 20000) / 100
    return {
      trade_id: `t${i}`,
      account_id: pick(ACCOUNTS),
      exit_time: isoVariants(t),
      net_profit: i % 17 === 0 ? 0 : cents, // include breakeven trades
    }
  })
  // Trades sitting exactly on the boundaries.
  for (const b of ['today', 'week', 'month'] as const) {
    const cut = withNow(now, () => web.dateFilterCutoff(b))
    for (const dm of [-1, 0, 1]) {
      const t = new RealDate(cut + dm * 60_000)
      entries.push({ trade_id: `edge-${b}-${dm}`, account_id: 'CAP_A', exit_time: isoVariants(t), net_profit: 1 })
    }
  }
  const data = { entries, total_trades: entries.length, wins: 0, losses: 0, total_net_profit: 0, accounts: ACCOUNTS }

  for (const filter of FILTERS) {
    for (const account of ['ALL', ...ACCOUNTS]) {
      const w = withNow(now, () => web.filterJournal(data, account, filter))
      const m = withNow(now, () => mobile.filterEntries(entries, account, filter))
      const ms = mobile.summarize(m)
      const label = `tz=${zone} now=${now.toISOString()} filter=${filter} account=${account}`

      assert.deepEqual([...w.entries.map((e: { trade_id: string }) => e.trade_id)].sort(), m.map((e: { trade_id: string }) => e.trade_id).sort(), `entries differ: ${label}`)
      if (w.entries !== data.entries) {
        // web recomputes only when a filter applied; with none it echoes the server totals — recompute here to compare.
        assert.equal(ms.total, w.total_trades, `total differs: ${label}`)
        assert.equal(ms.wins, w.wins, `wins differ: ${label}`)
        assert.equal(ms.losses, w.losses, `losses differ: ${label}`)
        assert.equal(ms.net, w.total_net_profit, `net differs: ${label}`)
      }
      checked++
    }
  }
}
}
console.log(`PARITY_OK  ${ZONES.length} time zones x ${NOWS.length} dates: ${checked} filter/account/date combinations identical`)

// --- chart-link resolver: web lib/tradingview.ts vs the phone's port ------------------
const webChart = await import(pathToFileURL(join(here, '../../frontend/src/lib/tradingview.ts')).href)
const mobileChart = await import(pathToFileURL(join(here, '../src/lib/chartImage.ts')).href)
const CHART_CORPUS: Array<string | null | undefined> = [
  'https://www.tradingview.com/x/aBcDeFgH/',
  'https://www.tradingview.com/x/ZyXw1234',
  'http://tradingview.com/x/Q9/',
  'HTTPS://WWW.TRADINGVIEW.COM/X/abcdef/',
  'https://www.tradingview.com/x/',
  'https://www.tradingview.com/chart/ABC/',
  'https://example.com/shot.png',
  'https://example.com/shot.JPG?x=1',
  'https://example.com/shot.jpeg#frag',
  'https://example.com/shot.webp',
  'https://example.com/shot.gif',
  'https://example.com/shot.pngx',
  'https://example.com/page',
  '  https://example.com/a.png  ',
  '   ',
  '',
  null,
  undefined,
  'not a url',
  'ftp://example.com/x.png',
]
for (const c of CHART_CORPUS) {
  assert.equal(mobileChart.resolveChartImage(c), webChart.resolveChartImage(c), `resolveChartImage differs for ${JSON.stringify(c)}`)
  assert.equal(mobileChart.isLinkable(c), webChart.isLinkable(c), `isLinkable differs for ${JSON.stringify(c)}`)
}
console.log(`PARITY_OK  chart-link resolver identical on ${CHART_CORPUS.length} inputs`)
