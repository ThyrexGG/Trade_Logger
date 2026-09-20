import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import * as Haptics from 'expo-haptics'
import { useCallback, useMemo, useRef, useState } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getJournalTagStats, patchJournalEntry, type JournalTagStats } from '../api/journal'
import { Card, Pill } from '../components/ui'
import { invalidateTagRecord } from '../components/TagRecord'
import { formatMoney, formatUpdated, isBuy } from '../format'
import { parseTime } from '../journal/filters'
import { useJournal } from '../journal/JournalContext'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { JournalTradeItem } from '../types/journal'

/** A setup needs this many trades before it is called best or costliest — fewer is noise. */
const MIN_TRADES = 5
const QUICK_CHIPS = 8
const UNTAGGED_SHOWN = 20

const tone = (v: number) => (v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textSecondary)

/** One untagged trade with one-tap chips: tapping a chip tags it and the row drops out of the list. */
function UntaggedRow({ trade, chips, busy, onTag, onOpen }: { trade: JournalTradeItem; chips: string[]; busy: boolean; onTag: (tag: string) => void; onOpen: () => void }) {
  return (
    <View style={styles.untagged}>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={`Open ${trade.symbol} trade`} style={styles.untaggedHead}>
        <Text style={styles.symbol}>{trade.symbol}</Text>
        <Text style={{ color: isBuy(trade.direction) ? colors.positive : colors.negative, fontSize: 12 }}>{trade.direction}</Text>
        <Text style={styles.muted}>{formatUpdated(trade.exit_time)}</Text>
        <Text style={[styles.pnl, { color: tone(trade.net_profit) }]}>{formatMoney(trade.net_profit)}</Text>
      </Pressable>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.chips}>
        {chips.map((c) => (
          <Pressable key={c} disabled={busy} onPress={() => onTag(c)} accessibilityRole="button" accessibilityLabel={`Tag as ${c}`} style={[styles.chip, busy && { opacity: 0.5 }]}>
            <Text style={styles.chipText}>{c}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  )
}

/** Which setups make money, and a fast way to tag the closed trades that have no setup yet. */
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
      setSaveError(err instanceof Error ? err.message : 'Could not save that tag.')
    } finally {
      setBusyId(null)
    }
  }

  const total = stats?.total_trades ?? 0
  const tagged = total - (stats?.untagged.n ?? 0)

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} />}
      >
        <Text style={styles.muted}>
          A setup tag says why you took a trade. Once trades are tagged, this shows which setups actually pay you. It uses closed trades only.
        </Text>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {stats == null && !error ? <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} /> : null}

        {stats && total > 0 ? (
          <Card title="Tagged trades" right={`${tagged} of ${total}`}>
            <View style={styles.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round((tagged / total) * 100) }}>
              <View style={[styles.fill, { width: `${(tagged / total) * 100}%` }]} />
            </View>
            <Text style={styles.muted}>
              {stats.untagged.n === 0 ? 'Every closed trade has a setup. Nice.' : `${stats.untagged.n} still have none — the untagged trades made ${formatMoney(stats.untagged.net_total)} between them.`}
            </Text>
          </Card>
        ) : null}

        {stats && stats.tags.length > 0 ? (
          <Card title="Your setups" right={`${stats.tags.length} setup${stats.tags.length === 1 ? "" : "s"}`}>
            {stats.tags.map((t) => {
              const exp = t.expectancy ?? 0
              return (
                <View key={t.tag} style={styles.setupRow}>
                  <View style={{ flex: 1, gap: 2 }}>
                    <View style={styles.setupTitle}>
                      <Text style={styles.setupName} numberOfLines={2}>{t.tag}</Text>
                      {best && t.tag === best.tag ? <Pill text="BEST" color={colors.positive} /> : null}
                      {worst && t.tag === worst.tag && (worst.expectancy ?? 0) < 0 ? <Pill text="COSTLY" color={colors.negative} /> : null}
                    </View>
                    <Text style={styles.muted}>
                      {t.n} trade{t.n === 1 ? '' : 's'} · {t.win_rate == null ? '—' : `${Math.round(t.win_rate * 100)}%`} win · {formatMoney(exp)} avg
                      {t.n < MIN_TRADES ? ' · too few trades to judge' : ''}
                    </Text>
                  </View>
                  <Text style={[styles.net, { color: tone(t.net_total) }]}>{formatMoney(t.net_total)}</Text>
                </View>
              )
            })}
          </Card>
        ) : null}

        {stats && stats.tags.length === 0 && total > 0 ? <Text style={styles.muted}>No setups yet. Tag a trade below, or from any trade&apos;s screen.</Text> : null}
        {stats && total === 0 ? <Text style={styles.muted}>No closed trades yet. Once you have some, they show up here.</Text> : null}

        {untagged.length > 0 ? (
          <Card title="Tag the rest" right={untagged.length > UNTAGGED_SHOWN ? `newest ${UNTAGGED_SHOWN} of ${untagged.length}` : `${untagged.length} left`}>
            <Text style={styles.muted}>Tap a setup to tag the trade (swipe for more). Tap the trade to add notes or type your own.</Text>
            {saveError ? <Text style={styles.error}>{saveError}</Text> : null}
            {untagged.slice(0, UNTAGGED_SHOWN).map((t) => (
              <UntaggedRow key={t.trade_id} trade={t} chips={chips} busy={busyId === t.trade_id} onTag={(c) => void tag(t, c)} onOpen={() => navigation.navigate('TradeDetail', { tradeId: t.trade_id })} />
            ))}
          </Card>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  muted: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  error: { color: colors.negative, fontSize: 13 },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: colors.surfaceElevated, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: colors.accent, borderRadius: radius.pill },
  setupRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.borderSubtle },
  setupTitle: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
  setupName: { color: colors.textPrimary, fontSize: 14, fontWeight: '600', flexShrink: 1 },
  net: { fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  untagged: { gap: spacing.sm, paddingVertical: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.borderSubtle },
  untaggedHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  symbol: { color: colors.textPrimary, fontSize: 14, fontWeight: '700' },
  pnl: { marginLeft: 'auto', fontSize: 14, fontWeight: '600', fontVariant: ['tabular-nums'] },
  chips: { flexDirection: 'row', gap: spacing.sm, paddingRight: spacing.lg },
  chip: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 7, backgroundColor: colors.surfaceElevated },
  chipText: { color: colors.textSecondary, fontSize: 12 },
})
