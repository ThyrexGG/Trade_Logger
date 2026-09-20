import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useRef, useState } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getWeeklySummary, setWeeklySummaryEnabled } from '../api/weeklySummary'
import { Card } from '../components/ui'
import { formatMoney } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { WeekBlock, WeekDay } from '../types/weeklySummary'

const DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const CHART_HALF = 44

/** "Sep 14 – Sep 20". The dates are UTC calendar days, so they are formatted in UTC. */
function rangeLabel(start: string, end: string): string {
  const fmt = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  return `${fmt(start)} – ${fmt(end)}`
}

const tone = (v: number) => (v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textSecondary)

/** One bar per day around a zero line: green up for a winning day, red down for a losing one. */
function DayBars({ days }: { days: WeekDay[] }) {
  const max = Math.max(1, ...days.map((d) => Math.abs(d.net)))
  return (
    <View style={styles.bars} accessibilityLabel="Net result for each day of the week">
      {days.map((d, i) => {
        const h = Math.round((Math.abs(d.net) / max) * CHART_HALF)
        return (
          <View key={d.date} style={styles.barCol}>
            <View style={styles.barHalf}>{d.net > 0 ? <View style={[styles.bar, { height: Math.max(3, h), backgroundColor: colors.positive }]} /> : null}</View>
            <View style={styles.zero} />
            <View style={[styles.barHalf, { justifyContent: 'flex-start' }]}>
              {d.net < 0 ? <View style={[styles.bar, { height: Math.max(3, h), backgroundColor: colors.negative }]} /> : null}
            </View>
            <Text style={styles.dayLetter}>{DAY_LETTERS[i]}</Text>
          </View>
        )
      })}
    </View>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
  )
}

function WeekCard({ week, onTag }: { week: WeekBlock; onTag: () => void }) {
  const s = week.summary
  const title = week.is_current ? 'This week so far' : 'Last week'
  return (
    <Card title={title} right={rangeLabel(week.start, week.end)}>
      {s.trades === 0 ? (
        <Text style={styles.muted}>No closed trades {week.is_current ? 'yet this week' : 'that week'}.</Text>
      ) : (
        <>
          <Text style={[styles.net, { color: tone(s.net) }]}>{formatMoney(s.net)}</Text>
          <Text style={styles.muted}>
            {s.trades} trade{s.trades === 1 ? '' : 's'} · {s.wins} won · {s.losses} lost
          </Text>
          <View style={styles.statRow}>
            <Stat label="Win rate" value={s.win_rate == null ? '—' : `${Math.round(s.win_rate * 100)}%`} />
            <Stat label="Profit factor" value={s.profit_factor == null ? '—' : s.profit_factor.toFixed(2)} />
            <Stat label="Best trade" value={s.best_trade ? `${s.best_trade.symbol} ${formatMoney(s.best_trade.net)}` : '—'} color={colors.positive} />
            <Stat label="Worst trade" value={s.worst_trade ? `${s.worst_trade.symbol} ${formatMoney(s.worst_trade.net)}` : '—'} color={s.worst_trade ? colors.negative : undefined} />
          </View>
          <DayBars days={s.by_day} />
          {s.best_tag ? (
            <Text style={styles.body}>
              Best setup: <Text style={styles.strong}>{s.best_tag.tag}</Text> <Text style={{ color: colors.positive }}>{formatMoney(s.best_tag.net)}</Text> over {s.best_tag.trades} trades
            </Text>
          ) : null}
          {s.worst_tag ? (
            <Text style={styles.body}>
              Costliest setup: <Text style={styles.strong}>{s.worst_tag.tag}</Text> <Text style={{ color: colors.negative }}>{formatMoney(s.worst_tag.net)}</Text> over {s.worst_tag.trades} trades
            </Text>
          ) : null}
          {s.untagged > 0 ? (
            <Pressable onPress={onTag} accessibilityRole="button">
              <Text style={styles.link}>
                {s.untagged} trade{s.untagged === 1 ? '' : 's'} without a setup tag — tag {s.untagged === 1 ? 'it' : 'them'} ›
              </Text>
            </Pressable>
          ) : null}
        </>
      )}
    </Card>
  )
}

/** This week so far and last week, and the switch for the Sunday notification that sends the same summary. */
export function WeeklySummaryScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [weeks, setWeeks] = useState<WeekBlock[] | null>(null)
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const res = await getWeeklySummary(controller.signal)
      if (controller.signal.aborted) return
      setWeeks(res.weeks)
      setEnabled(res.enabled)
      setNote(res.note)
      setError(null)
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load your weekly summary.')
    } finally {
      if (!controller.signal.aborted) setRefreshing(false)
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load()
      return () => inFlight.current?.abort()
    }, [load]),
  )

  async function toggle(next: boolean) {
    const before = enabled
    setEnabled(next)
    setError(null)
    try {
      await setWeeklySummaryEnabled(next)
    } catch (err) {
      setEnabled(before)
      setError(err instanceof Error ? err.message : 'Could not change that setting.')
    }
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} />}
      >
        <View style={styles.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.toggleTitle}>Send me this every Sunday</Text>
            <Text style={styles.muted}>One notification with the numbers below, at about 12:00 UTC. A week with no closed trades sends nothing.</Text>
          </View>
          {enabled == null ? (
            <ActivityIndicator color={colors.accent} />
          ) : (
            <Switch value={enabled} onValueChange={(v) => void toggle(v)} trackColor={{ true: colors.accent, false: colors.surfaceElevated }} thumbColor="#ffffff" />
          )}
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {weeks == null && !error ? <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} /> : null}
        {weeks?.map((w) => <WeekCard key={w.key} week={w} onTag={() => navigation.navigate('Setups')} />)}
        {note ? <Text style={styles.muted}>{note}</Text> : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.lg, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  toggleTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: '600', marginBottom: 2 },
  muted: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  body: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  strong: { color: colors.textPrimary, fontWeight: '600' },
  link: { color: colors.accent, fontSize: 13, fontWeight: '600', paddingVertical: 4 },
  error: { color: colors.negative, fontSize: 13 },
  net: { fontSize: 30, fontWeight: '700', fontVariant: ['tabular-nums'] },
  statRow: { flexDirection: 'row', flexWrap: 'wrap', rowGap: spacing.md, columnGap: spacing.lg, marginTop: spacing.sm },
  stat: { minWidth: '40%', flexGrow: 1 },
  statLabel: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6 },
  statValue: { color: colors.textPrimary, fontSize: 15, fontWeight: '600', fontVariant: ['tabular-nums'] },
  bars: { flexDirection: 'row', alignItems: 'stretch', gap: 6, marginTop: spacing.md },
  barCol: { flex: 1, alignItems: 'center' },
  barHalf: { height: CHART_HALF, width: '100%', justifyContent: 'flex-end', alignItems: 'center' },
  bar: { width: '62%', borderRadius: 3 },
  zero: { height: StyleSheet.hairlineWidth, width: '100%', backgroundColor: colors.border },
  dayLetter: { color: colors.textMuted, fontSize: 11, marginTop: 4 },
})
