import { useMemo, useState } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { colors, radius, spacing } from '../../theme'
import type { DailyPnl } from '../../types/analytics'

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const pad = (n: number) => String(n).padStart(2, '0')

/** "+12.5" / "-4.2" / "+1.2k" — short enough for a phone-sized day cell. */
function compact(v: number): string {
  const abs = Math.abs(v)
  const sign = v > 0 ? '+' : v < 0 ? '-' : ''
  if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(1)}k`
  return `${sign}${abs.toFixed(abs < 10 ? 2 : abs < 100 ? 1 : 0)}`
}

function money(v: number): string {
  return `${v >= 0 ? '+' : '-'}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

interface Cell {
  key: string
  day: number
  iso: string
  data?: DailyPnl
}

/** Month grid of daily net P&L (Monday first, like the website). Tap a day that has trades to see them. */
export function MonthCalendar({ daily, onDayPress }: { daily: DailyPnl[]; onDayPress: (iso: string) => void }) {
  const byIso = useMemo(() => new Map(daily.map((d) => [d.date, d])), [daily])
  const [cursor, setCursor] = useState(() => {
    const latest = daily.length ? [...daily].sort((a, b) => (a.date < b.date ? 1 : -1))[0].date : null
    const d = latest ? new Date(`${latest}T00:00:00`) : new Date()
    return { y: d.getFullYear(), m: d.getMonth() }
  })

  const { weeks, summary, maxAbs } = useMemo(() => {
    const first = new Date(cursor.y, cursor.m, 1)
    const lead = (first.getDay() + 6) % 7
    const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate()
    const out: Cell[] = []
    for (let i = 0; i < lead; i += 1) out.push({ key: `lead-${i}`, day: 0, iso: '' })
    for (let d = 1; d <= daysInMonth; d += 1) {
      const iso = `${cursor.y}-${pad(cursor.m + 1)}-${pad(d)}`
      out.push({ key: iso, day: d, iso, data: byIso.get(iso) })
    }
    while (out.length % 7 !== 0) out.push({ key: `trail-${out.length}`, day: 0, iso: '' })
    const days = out.filter((c) => c.data).map((c) => c.data as DailyPnl)
    const chunks: Cell[][] = []
    for (let i = 0; i < out.length; i += 7) chunks.push(out.slice(i, i + 7))
    return {
      weeks: chunks,
      summary: {
        pnl: days.reduce((a, d) => a + d.net_profit, 0),
        trades: days.reduce((a, d) => a + d.trades, 0),
        wins: days.reduce((a, d) => a + d.wins, 0),
        greenDays: days.filter((d) => d.net_profit > 0).length,
        redDays: days.filter((d) => d.net_profit < 0).length,
      },
      maxAbs: Math.max(1, ...days.map((d) => Math.abs(d.net_profit))),
    }
  }, [byIso, cursor])

  const shift = (delta: number) =>
    setCursor((c) => {
      const d = new Date(c.y, c.m + delta, 1)
      return { y: d.getFullYear(), m: d.getMonth() }
    })

  const pnlColor = summary.pnl > 0 ? colors.positive : summary.pnl < 0 ? colors.negative : colors.textSecondary

  return (
    <View>
      <View style={styles.nav}>
        <Pressable onPress={() => shift(-1)} hitSlop={10} style={styles.navBtn} accessibilityLabel="Previous month">
          <Text style={styles.navArrow}>‹</Text>
        </Pressable>
        <Text style={styles.month}>
          {MONTHS[cursor.m]} {cursor.y}
        </Text>
        <Pressable onPress={() => shift(1)} hitSlop={10} style={styles.navBtn} accessibilityLabel="Next month">
          <Text style={styles.navArrow}>›</Text>
        </Pressable>
      </View>

      <View style={styles.summary}>
        <Text style={[styles.summaryPnl, { color: pnlColor }]}>{money(summary.pnl)}</Text>
        <Text style={styles.summarySub}>
          {summary.trades} trades · {summary.wins} wins · {summary.greenDays} green / {summary.redDays} red days
        </Text>
      </View>

      <View style={styles.weekRow}>
        {WEEKDAYS.map((w, i) => (
          <Text key={i} style={styles.weekday}>
            {w}
          </Text>
        ))}
      </View>
      <View>
        {weeks.map((week, wi) => (
          <View key={wi} style={styles.weekLine}>
            {week.map((c) => {
              if (!c.day) return <View key={c.key} style={styles.cellWrap} />
              const v = c.data?.net_profit
              const tint =
                v === undefined || v === 0
                  ? undefined
                  : v > 0
                    ? `rgba(16,185,129,${0.14 + 0.4 * (v / maxAbs)})`
                    : `rgba(239,68,68,${0.14 + 0.4 * (Math.abs(v) / maxAbs)})`
              const inner = (
                <View style={[styles.cell, tint ? { backgroundColor: tint } : null]}>
                  <Text style={styles.dayNum}>{c.day}</Text>
                  {v !== undefined ? (
                    <Text
                      style={[styles.dayPnl, { color: v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textSecondary }]}
                      numberOfLines={1}
                      adjustsFontSizeToFit
                    >
                      {compact(v)}
                    </Text>
                  ) : null}
                </View>
              )
              return c.data ? (
                <Pressable
                  key={c.key}
                  style={styles.cellWrap}
                  onPress={() => onDayPress(c.iso)}
                  accessibilityRole="button"
                  accessibilityLabel={`${c.iso}, ${money(c.data.net_profit)}`}
                >
                  {inner}
                </Pressable>
              ) : (
                <View key={c.key} style={styles.cellWrap}>
                  {inner}
                </View>
              )
            })}
          </View>
        ))}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  navBtn: { paddingHorizontal: spacing.md, paddingVertical: 2 },
  navArrow: { color: colors.accent, fontSize: 28, lineHeight: 30 },
  month: { color: colors.textPrimary, fontSize: 16, fontWeight: '700' },
  summary: { alignItems: 'center', marginVertical: spacing.sm },
  summaryPnl: { fontSize: 20, fontWeight: '800', fontVariant: ['tabular-nums'] },
  summarySub: { color: colors.textMuted, fontSize: 12, marginTop: 2, textAlign: 'center' },
  weekRow: { flexDirection: 'row', marginTop: spacing.xs },
  weekday: { flex: 1, textAlign: 'center', color: colors.textMuted, fontSize: 11, paddingVertical: 4 },
  weekLine: { flexDirection: 'row' },
  cellWrap: { flex: 1, padding: 2 },
  cell: {
    aspectRatio: 1,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceElevated,
    padding: 3,
    justifyContent: 'space-between',
  },
  dayNum: { color: colors.textMuted, fontSize: 10 },
  dayPnl: { fontSize: 11, fontWeight: '700', textAlign: 'center', fontVariant: ['tabular-nums'] },
})
