import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { formatMoney, formatPrice, formatUpdated, isBuy } from '../format'
import { useJournal } from '../journal/JournalContext'
import { formatDuration } from '../journal/filters'
import type { JournalStackParamList } from '../navigation/JournalStack'
import { colors, radius, spacing } from '../theme'

export function TradeDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<JournalStackParamList, 'TradeDetail'>>()
  const { params } = useRoute<RouteProp<JournalStackParamList, 'TradeDetail'>>()
  const { data } = useJournal()
  const trade = data?.entries.find((e) => e.trade_id === params.tradeId)

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

  const dirColor = isBuy(trade.direction) ? colors.positive : colors.negative
  const netColor = trade.net_profit > 0 ? colors.positive : trade.net_profit < 0 ? colors.negative : colors.textSecondary

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <View style={styles.heroTop}>
            <Text style={styles.symbol}>{trade.symbol}</Text>
            <View style={[styles.dirPill, { borderColor: dirColor }]}>
              <Text style={[styles.dirText, { color: dirColor }]}>{trade.direction.toUpperCase()}</Text>
            </View>
          </View>
          <Text style={[styles.net, { color: netColor }]}>{formatMoney(trade.net_profit)}</Text>
          <Text style={styles.sub}>
            {trade.account_id} · closed {formatUpdated(trade.exit_time)}
          </Text>
        </View>

        <View style={styles.card}>
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

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Journal</Text>
          <Fact label="Setup tag" value={trade.setup_tag || '—'} />
          <Fact label="Rating" value={trade.rating ? '★'.repeat(trade.rating) : '—'} />
          <Fact label="Screenshots" value={trade.screenshot_count ? String(trade.screenshot_count) : '—'} />
          <View style={styles.notesBlock}>
            <Text style={styles.factLabel}>Notes</Text>
            <Text style={trade.notes ? styles.notes : styles.notesEmpty}>{trade.notes || 'No notes yet.'}</Text>
          </View>
          {trade.chart_snapshot_url ? (
            <Pressable onPress={() => void Linking.openURL(trade.chart_snapshot_url!)} accessibilityRole="link">
              <Text style={styles.link} numberOfLines={1}>
                {trade.chart_snapshot_url}
              </Text>
            </Pressable>
          ) : null}
        </View>
        <Text style={styles.hint}>Editing arrives in the next step (M5).</Text>
      </ScrollView>
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
  content: { padding: spacing.lg, gap: spacing.md },
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
    paddingVertical: spacing.xs,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    paddingTop: spacing.md,
  },
  fact: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.md, gap: spacing.lg },
  factBorder: { borderBottomColor: colors.borderSubtle, borderBottomWidth: 1 },
  factLabel: { color: colors.textMuted, fontSize: 13 },
  factValue: { color: colors.textPrimary, fontSize: 14, fontVariant: ['tabular-nums'], flexShrink: 1 },
  notesBlock: { paddingVertical: spacing.md, gap: spacing.xs },
  notes: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  notesEmpty: { color: colors.textMuted, fontSize: 14 },
  link: { color: colors.accent, fontSize: 13, paddingBottom: spacing.md },
  hint: { color: colors.textMuted, fontSize: 12, textAlign: 'center' },
  missing: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.lg, padding: spacing.xl },
  missingText: { color: colors.textSecondary, fontSize: 15, textAlign: 'center' },
  backBtn: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  backText: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
})
