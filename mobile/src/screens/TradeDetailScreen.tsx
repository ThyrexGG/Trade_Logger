import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useState } from 'react'
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { clearAnalyticsCache } from '../analytics/useAnalytics'
import { deleteManualTrade, patchJournalEntry } from '../api/journal'
import { AnnotationEditor } from '../components/AnnotationEditor'
import { ScreenshotGallery } from '../components/ScreenshotGallery'
import { ExitsPill, TradeLegsCard } from '../components/TradeLegs'
import { formatMoney, formatPrice, formatUpdated, isBuy } from '../format'
import { useJournal } from '../journal/JournalContext'
import { formatDuration } from '../journal/filters'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'

export function TradeDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'TradeDetail'>>()
  const { params } = useRoute<RouteProp<RootStackParamList, 'TradeDetail'>>()
  const { data, applyEntry, loading, refreshing, refresh } = useJournal()
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const tagSuggestions = useTagSuggestions()
  // A link to one partial close (an old notification) opens the trade it belongs to.
  const trade = data?.entries.find((e) => e.trade_id === params.tradeId || e.legs?.some((l) => l.trade_id === params.tradeId))

  // Opened from a push notification: the trade may still be on its way in from the server.
  if (!trade && (loading || refreshing)) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.missing}>
          <ActivityIndicator color={colors.accent} size="large" />
        </View>
      </SafeAreaView>
    )
  }

  if (!trade) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.missing}>
          <Text style={styles.missingText}>This trade is no longer in your journal.</Text>
          <Pressable onPress={() => navigation.goBack()} style={styles.backBtn} accessibilityRole="button">
            <Text style={styles.backText}>Go back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    )
  }

  const isManual = trade.trade_id.startsWith('MANUAL_')

  function confirmDelete() {
    if (!trade) return
    Alert.alert('Delete this trade?', 'It is removed from your Journal, Analytics and calendar, along with its notes and screenshots. This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          setDeleting(true)
          setDeleteError(null)
          try {
            await deleteManualTrade(trade.trade_id)
            clearAnalyticsCache()
            await refresh()
            navigation.goBack()
          } catch (err) {
            setDeleteError(err instanceof Error ? err.message : 'Could not delete the trade.')
            setDeleting(false)
          }
        },
      },
    ])
  }

  const dirColor = isBuy(trade.direction) ? colors.positive : colors.negative
  const netColor = trade.net_profit > 0 ? colors.positive : trade.net_profit < 0 ? colors.negative : colors.textSecondary

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <View style={styles.heroTop}>
              <Text style={styles.symbol}>{trade.symbol}</Text>
              <View style={[styles.dirPill, { borderColor: dirColor }]}>
                <Text style={[styles.dirText, { color: dirColor }]}>{trade.direction.toUpperCase()}</Text>
              </View>
              <ExitsPill t={trade} />
            </View>
            <Text style={[styles.net, { color: netColor }]}>{formatMoney(trade.net_profit)}</Text>
            <Text style={styles.sub}>
              {trade.account_id} · closed {formatUpdated(trade.exit_time)}
            </Text>
          </View>

          <TradeLegsCard t={trade} />

          <View style={styles.card}>
            <ScreenshotGallery
              ownerId={trade.trade_id}
              onCountChange={(n) => {
                if ((trade.screenshot_count ?? 0) !== n) applyEntry({ ...trade, screenshot_count: n })
              }}
            />
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Journal</Text>
            <AnnotationEditor
              key={trade.trade_id}
              initial={{
                setup_tag: trade.setup_tag ?? '',
                notes: trade.notes ?? '',
                chart_snapshot_url: trade.chart_snapshot_url ?? '',
                rating: trade.rating ?? 0,
              }}
              tagSuggestions={tagSuggestions}
              save={async (patch) => {
                const res = await patchJournalEntry(trade.trade_id, patch)
                applyEntry(res.entry)
              }}
            />
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Execution</Text>
            <Fact label="Volume" value={String(trade.volume)} />
            <Fact label="Entry" value={formatPrice(trade.entry_price)} />
            <Fact label="Exit" value={formatPrice(trade.exit_price)} />
            <Fact label="Opened" value={formatUpdated(trade.entry_time)} />
            <Fact label="Closed" value={formatUpdated(trade.exit_time)} />
            <Fact label="Duration" value={formatDuration(trade.duration_minutes)} />
            <Fact label="Gross P&L" value={formatMoney(trade.gross_profit)} />
            <Fact label="Commission" value={formatMoney(trade.commission)} />
            <Fact label="Swap" value={formatMoney(trade.swap)} last />
          </View>

          {isManual ? (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Logged by hand</Text>
              <Text style={styles.sub}>You entered this trade yourself, so you can fix or remove it. Trades synced from a broker can't be changed here.</Text>
              <View style={styles.manualRow}>
                <Pressable onPress={() => navigation.navigate('ManualTrade', { trade })} style={styles.editBtn} accessibilityRole="button">
                  <Text style={styles.editText}>Edit trade</Text>
                </Pressable>
                <Pressable onPress={confirmDelete} disabled={deleting} style={[styles.deleteBtn, deleting && { opacity: 0.6 }]} accessibilityRole="button">
                  {deleting ? <ActivityIndicator color={colors.negative} /> : <Text style={styles.deleteText}>Delete trade</Text>}
                </Pressable>
              </View>
              {deleteError ? <Text style={styles.deleteError}>{deleteError}</Text> : null}
            </View>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

function Fact({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.fact, !last && styles.factBorder]}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={styles.factValue} numberOfLines={1}>
        {value}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  hero: { gap: spacing.xs },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  symbol: { color: colors.textPrimary, fontSize: 26, fontWeight: '700' },
  dirPill: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  dirText: { fontSize: 12, fontWeight: '700' },
  net: { fontSize: 34, fontWeight: '700', fontVariant: ['tabular-nums'] },
  sub: { color: colors.textMuted, fontSize: 13 },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  fact: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.md, gap: spacing.lg },
  factBorder: { borderBottomColor: colors.borderSubtle, borderBottomWidth: 1 },
  factLabel: { color: colors.textMuted, fontSize: 13 },
  factValue: { color: colors.textPrimary, fontSize: 14, fontVariant: ['tabular-nums'], flexShrink: 1 },
  manualRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  editBtn: { flex: 1, alignItems: 'center', borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.1)', borderWidth: 1, borderRadius: radius.md, paddingVertical: spacing.md },
  editText: { color: colors.accent, fontWeight: '700', fontSize: 14 },
  deleteBtn: { flex: 1, alignItems: 'center', borderColor: 'rgba(239,68,68,0.5)', backgroundColor: 'rgba(239,68,68,0.08)', borderWidth: 1, borderRadius: radius.md, paddingVertical: spacing.md },
  deleteText: { color: colors.negative, fontWeight: '700', fontSize: 14 },
  deleteError: { color: colors.negative, fontSize: 13, marginTop: spacing.sm },
  missing: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.lg, padding: spacing.xl },
  missingText: { color: colors.textSecondary, fontSize: 15, textAlign: 'center' },
  backBtn: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  backText: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
})
