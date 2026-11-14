import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import * as Haptics from 'expo-haptics'
import { useCallback, useMemo, useRef, useState } from 'react'
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getJournalTagStats, patchJournalEntry, type JournalTagStats } from '../api/journal'
import { invalidateTagRecord } from '../components/TagRecord'
import { Text } from '../components/Text'
import { Card, DirTag, Empty, Loading, Notice, Pill, Rows, ui } from '../components/ui'
import { formatMoney, formatUpdated } from '../format'
import { parseTime } from '../journal/filters'
import { useJournal } from '../journal/JournalContext'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, pnlColor, radius, spacing, type } from '../theme'
import type { JournalTradeItem } from '../types/journal'

/** A setup needs this many trades before it is called best or costliest — fewer is noise. */
const MIN_TRADES = 5
const QUICK_CHIPS = 8
const UNTAGGED_SHOWN = 20

/** One unmarked trade with one-tap chips: tapping a chip labels it and the row drops out of the list. */
function UntaggedRow({ trade, chips, busy, onTag, onOpen }: { trade: JournalTradeItem; chips: string[]; busy: boolean; onTag: (tag: string) => void; onOpen: () => void }) {
  return (
    <View style={styles.untagged}>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={`Open ${trade.symbol} trade`} style={styles.untaggedHead}>
        <Text style={ui.heading}>{trade.symbol}</Text>
        <DirTag direction={trade.direction} />
        <Text style={styles.time}>{formatUpdated(trade.exit_time)}</Text>
        <Text style={[styles.pnl, { color: pnlColor(trade.net_profit) }]}>{formatMoney(trade.net_profit)}</Text>
      </Pressable>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" style={styles.chipScroll} contentContainerStyle={styles.chips}>
        {chips.map((c) => (
          <Pressable key={c} disabled={busy} onPress={() => onTag(c)} accessibilityRole="button" accessibilityLabel={`Mark as ${c}`} style={[styles.chip, busy && { opacity: 0.5 }]}>
            <Text style={styles.chipText}>{c}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  )
}

/** Which kinds of trade make money, and a fast way to mark the closed trades that have no label yet. */
export function SetupsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { data: journal, applyEntry } = useJournal()
  const suggestions = useTagSuggestions()
  const [stats, setStats] = useState<JournalTagStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const res = await getJournalTagStats(controller.signal)
      if (controller.signal.aborted) return
      setStats(res)
      setError(null)
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load your setups.')
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

  const untagged = useMemo(
    () => (journal?.entries ?? []).filter((e) => !e.setup_tag?.trim()).sort((a, b) => parseTime(b.exit_time) - parseTime(a.exit_time)),
    [journal],
  )
  const chips = useMemo(() => suggestions.slice(0, QUICK_CHIPS), [suggestions])

  const ranked = useMemo(() => (stats?.tags ?? []).filter((t) => t.n >= MIN_TRADES && t.expectancy != null), [stats])
  const best = ranked.length > 1 ? [...ranked].sort((a, b) => (b.expectancy ?? 0) - (a.expectancy ?? 0))[0] : null
  const worst = ranked.length > 1 ? [...ranked].sort((a, b) => (a.expectancy ?? 0) - (b.expectancy ?? 0))[0] : null

  async function tag(trade: JournalTradeItem, setup: string) {
    setBusyId(trade.trade_id)
    setSaveError(null)
    try {
      const res = await patchJournalEntry(trade.trade_id, { setup_tag: setup })
      applyEntry(res.entry)
      invalidateTagRecord()
      void Haptics.selectionAsync().catch(() => {})
      await load()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not save that label.')
    } finally {
      setBusyId(null)
    }
  }

  const total = stats?.total_trades ?? 0
  const tagged = total - (stats?.untagged.n ?? 0)

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={ui.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} colors={[colors.accent]} />}
      >
        <Text style={ui.muted}>A label says how or why you took a trade. Once trades are marked, this shows which kind actually pays you. Closed trades only.</Text>
        {error ? <Notice>{error}</Notice> : null}
        {stats == null && !error ? <Loading /> : null}

        {stats && total > 0 ? (
          <Card title="Trades marked" right={`${tagged} of ${total}`}>
            <View style={styles.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round((tagged / total) * 100) }}>
              <View style={[styles.fill, { width: `${(tagged / total) * 100}%` }]} />
            </View>
            <Text style={ui.muted}>
              {stats.untagged.n === 0 ? 'Every closed trade is marked.' : `${stats.untagged.n} still have no label. Between them they made ${formatMoney(stats.untagged.net_total)}.`}
            </Text>
          </Card>
        ) : null}

        {stats && stats.tags.length > 0 ? (
          <Card title="What pays you" right={`${stats.tags.length} label${stats.tags.length === 1 ? '' : 's'}`} flush>
            <Rows>
              {stats.tags.map((t) => {
                const exp = t.expectancy ?? 0
                return (
                  <View key={t.tag} style={styles.setupRow}>
                    <View style={styles.setupText}>
                      <View style={ui.rowWrap}>
                        <Text style={styles.setupName} numberOfLines={2}>
                          {t.tag}
                        </Text>
                        {best && t.tag === best.tag ? <Pill text="Best" color={colors.positive} /> : null}
                        {worst && t.tag === worst.tag && (worst.expectancy ?? 0) < 0 ? <Pill text="Costly" color={colors.negative} /> : null}
                      </View>
                      <Text style={ui.muted}>
                        {t.n} trade{t.n === 1 ? '' : 's'} · {t.win_rate == null ? '—' : `${Math.round(t.win_rate * 100)}%`} win · {formatMoney(exp)} avg
                      </Text>
                      {t.n < MIN_TRADES ? <Text style={ui.muted}>Too few trades to judge yet</Text> : null}
                    </View>
                    <Text style={[styles.net, { color: pnlColor(t.net_total) }]}>{formatMoney(t.net_total)}</Text>
                  </View>
                )
              })}
            </Rows>
          </Card>
        ) : null}

        {stats && stats.tags.length === 0 && total > 0 ? <Text style={ui.muted}>Nothing marked yet. Mark a trade below, or from any trade's screen.</Text> : null}
        {stats && total === 0 ? <Empty icon="pricetags-outline" title="No closed trades yet" text="Once you have some, they show up here to be marked." /> : null}

        {untagged.length > 0 ? (
          <Card title="Still to mark" right={untagged.length > UNTAGGED_SHOWN ? `newest ${UNTAGGED_SHOWN} of ${untagged.length}` : `${untagged.length} left`} flush>
            <Text style={styles.cardIntro}>Tap a label to mark the trade (swipe for more). Tap the trade itself to add a note or type your own.</Text>
            {saveError ? <Notice style={styles.inNotice}>{saveError}</Notice> : null}
            <Rows>
              {untagged.slice(0, UNTAGGED_SHOWN).map((t) => (
                <UntaggedRow key={t.trade_id} trade={t} chips={chips} busy={busyId === t.trade_id} onTag={(c) => void tag(t, c)} onOpen={() => navigation.navigate('TradeDetail', { tradeId: t.trade_id })} />
              ))}
            </Rows>
          </Card>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  track: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceElevated, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: colors.accent, borderRadius: radius.pill },
  setupRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  setupText: { flex: 1, gap: 3, minWidth: 0 },
  setupName: { ...type.heading, fontWeight: '500', flexShrink: 1 },
  time: { ...type.small, fontVariant: ['tabular-nums'] },
  net: { ...type.num, fontSize: 15, fontWeight: '600' },
  cardIntro: { ...type.small, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.borderSubtle },
  inNotice: { margin: spacing.lg, marginBottom: 0 },
  untagged: { gap: spacing.sm, paddingVertical: spacing.md },
  untaggedHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.lg },
  pnl: { ...type.num, fontWeight: '600', marginLeft: 'auto' },
  chipScroll: { flexGrow: 0 },
  chips: { flexDirection: 'row', gap: spacing.sm, paddingHorizontal: spacing.lg },
  chip: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: spacing.md, minHeight: 32, justifyContent: 'center', backgroundColor: colors.surfaceElevated },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: '500' },
})
