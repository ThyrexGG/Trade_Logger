import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useRef, useState } from 'react'
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getWeeklySummary, setWeeklySummaryEnabled } from '../api/weeklySummary'
import { Text } from '../components/Text'
import { Card, Figures, Loading, Notice, Row, Stat, ToggleRow, ui } from '../components/ui'
import { formatMoney } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, pnlColor, spacing, type } from '../theme'
import type { WeekBlock, WeekDay } from '../types/weeklySummary'

const DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const CHART_HALF = 40

/** "Sep 14 – Sep 20". The dates are UTC calendar days, so they are formatted in UTC. */
function rangeLabel(start: string, end: string): string {
  const fmt = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  return `${fmt(start)} – ${fmt(end)}`
}

/** One bar per day around a zero line: green up for a winning day, red down for a losing one. */
function DayBars({ days }: { days: WeekDay[] }) {
  const max = Math.max(1, ...days.map((d) => Math.abs(d.net)))
  return (
    <View style={styles.bars} accessibilityLabel="Net result for each day of the week">
      {days.map((d, i) => {
        const h = Math.round((Math.abs(d.net) / max) * CHART_HALF)
        return (
          <View key={d.date} style={styles.barCol}>
            <View style={styles.barHalf}>{d.net > 0 ? <View style={[styles.bar, styles.barUp, { height: Math.max(3, h) }]} /> : null}</View>
            <View style={styles.zero} />
            <View style={[styles.barHalf, { justifyContent: 'flex-start' }]}>{d.net < 0 ? <View style={[styles.bar, styles.barDown, { height: Math.max(3, h) }]} /> : null}</View>
            <Text style={styles.dayLetter}>{DAY_LETTERS[i]}</Text>
          </View>
        )
      })}
    </View>
  )
}

function WeekCard({ week, onTag }: { week: WeekBlock; onTag: () => void }) {
  const s = week.summary
  const title = week.is_current ? 'This week so far' : 'Last week'
  if (s.trades === 0) {
    return (
      <Card title={title} right={rangeLabel(week.start, week.end)}>
        <Text style={ui.muted}>No closed trades {week.is_current ? 'yet this week' : 'that week'}.</Text>
      </Card>
    )
  }
  return (
    <Card title={title} right={rangeLabel(week.start, week.end)} feature={week.is_current} flush>
      <View style={styles.heroBlock}>
        <Text style={[styles.net, { color: pnlColor(s.net) }]} numberOfLines={1} adjustsFontSizeToFit>
          {formatMoney(s.net)}
        </Text>
        <Text style={ui.muted}>
          {s.trades} trade{s.trades === 1 ? '' : 's'} · {s.wins} won · {s.losses} lost
        </Text>
        <DayBars days={s.by_day} />
      </View>
      <Figures style={styles.topRule}>
        <Stat small label="Win rate" value={s.win_rate == null ? '—' : `${Math.round(s.win_rate * 100)}%`} />
        <Stat small label="Profit factor" value={s.profit_factor == null ? '—' : s.profit_factor.toFixed(2)} />
        <Stat small label="Best trade" value={s.best_trade ? formatMoney(s.best_trade.net) : '—'} color={s.best_trade ? pnlColor(s.best_trade.net) : undefined} sub={s.best_trade?.symbol} />
        <Stat small label="Worst trade" value={s.worst_trade ? formatMoney(s.worst_trade.net) : '—'} color={s.worst_trade ? pnlColor(s.worst_trade.net) : undefined} sub={s.worst_trade?.symbol} />
      </Figures>
      {s.best_tag || s.worst_tag ? (
        <View style={styles.tagBlock}>
          {s.best_tag ? (
            <Text style={ui.sub}>
              Paid best: <Text style={styles.strong}>{s.best_tag.tag}</Text> <Text style={[ui.num, { color: pnlColor(s.best_tag.net) }]}>{formatMoney(s.best_tag.net)}</Text> over {s.best_tag.trades} trades
            </Text>
          ) : null}
          {s.worst_tag ? (
            <Text style={ui.sub}>
              Cost most: <Text style={styles.strong}>{s.worst_tag.tag}</Text> <Text style={[ui.num, { color: pnlColor(s.worst_tag.net) }]}>{formatMoney(s.worst_tag.net)}</Text> over {s.worst_tag.trades} trades
            </Text>
          ) : null}
        </View>
      ) : null}
      {s.untagged > 0 ? (
        <View style={styles.topRule}>
          <Row title={`${s.untagged} trade${s.untagged === 1 ? '' : 's'} not marked yet`} sub="Mark them so this shows which kind of trade pays" chevron onPress={onTag} />
        </View>
      ) : null}
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
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={ui.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} colors={[colors.accent]} />}
      >
        {error ? <Notice>{error}</Notice> : null}
        {weeks == null && !error ? <Loading /> : null}
        {weeks?.map((w) => <WeekCard key={w.key} week={w} onTag={() => navigation.navigate('Setups')} />)}

        {/* the setting sits under the results */}
        <Card flush>
          <ToggleRow
            title="Send me this every Sunday"
            sub="One notification with these numbers, around 12:00 UTC. A week with no closed trades sends nothing."
            value={enabled === true}
            onChange={(v) => void toggle(v)}
            busy={enabled == null && !error}
            disabled={enabled == null}
          />
        </Card>
        {note ? <Text style={ui.muted}>{note}</Text> : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  heroBlock: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.md, gap: 2 },
  net: { ...type.hero, fontSize: 30, lineHeight: 36 },
  topRule: { borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  tagBlock: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, gap: 4, borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  strong: { color: colors.textPrimary, fontWeight: '500' },
  bars: { flexDirection: 'row', alignItems: 'stretch', gap: 6, marginTop: spacing.md },
  barCol: { flex: 1, alignItems: 'center' },
  barHalf: { height: CHART_HALF, width: '100%', justifyContent: 'flex-end', alignItems: 'center' },
  // rounded at the data end, square against the zero line
  bar: { width: '56%' },
  barUp: { backgroundColor: colors.positive, borderTopLeftRadius: 3, borderTopRightRadius: 3 },
  barDown: { backgroundColor: colors.negative, borderBottomLeftRadius: 3, borderBottomRightRadius: 3 },
  zero: { height: 1, width: '100%', backgroundColor: colors.border },
  dayLetter: { ...type.label, marginTop: 5 },
})
