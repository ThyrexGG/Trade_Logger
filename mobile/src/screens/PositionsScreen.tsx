import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { formatMoney, formatPrice, formatUpdated, isBuy } from '../format'
import { colors, radius, spacing } from '../theme'
import type { PositionItem } from '../types/positions'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { AccountTag } from '../components/AccountTag'

function pnlColor(v: number): string {
  return v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textSecondary
}

function PositionCard({ p, onPress, showAccount }: { p: PositionItem; onPress: () => void; showAccount: boolean }) {
  const buy = isBuy(p.direction)
  const dirColor = buy ? colors.positive : colors.negative
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.card, pressed && { opacity: 0.75 }]}>
      <View style={styles.cardTop}>
        <View style={styles.symbolRow}>
          <View style={styles.liveDot} />
          <Text style={styles.symbol}>{p.symbol}</Text>
          <View style={[styles.dirPill, { borderColor: dirColor }]}>
            <Text style={[styles.dirText, { color: dirColor }]}>{p.direction.toUpperCase()}</Text>
          </View>
          {showAccount ? <AccountTag accountId={p.account_id} /> : null}
        </View>
        <Text style={[styles.pnl, { color: pnlColor(p.floating_pnl) }]}>{formatMoney(p.floating_pnl)}</Text>
      </View>

      <View style={styles.grid}>
        {p.open_time ? <Stat label="Opened" value={formatUpdated(p.open_time)} /> : null}
        <Stat label="Volume" value={String(p.volume)} />
        <Stat label="Entry" value={formatPrice(p.entry_price)} />
        <Stat label="Current" value={formatPrice(p.current_price)} />
        {p.sl ? <Stat label="Stop" value={formatPrice(p.sl)} /> : null}
        {p.tp ? <Stat label="Target" value={formatPrice(p.tp)} /> : null}
      </View>

      {p.setup_tag || p.notes || p.screenshot_count ? (
        <View style={styles.noteRow}>
          {p.setup_tag ? <Text style={styles.tag}>{p.setup_tag}</Text> : null}
          {p.screenshot_count ? <Text style={styles.meta}>📷 {p.screenshot_count}</Text> : null}
          {p.notes ? (
            <Text style={styles.note} numberOfLines={2}>
              {p.notes}
            </Text>
          ) : null}
        </View>
      ) : null}
      <Text style={styles.tapHint}>Tap to journal this trade ›</Text>
    </Pressable>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  )
}

export function PositionsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { data, loading, refreshing, error, refresh, syncing, syncError, syncNow } = usePositionsContext()
  const positions = data?.positions ?? []
  const total = data?.total_floating_pnl ?? 0
  const multiAccount = new Set(positions.map((p) => p.account_id)).size > 1

  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>Open positions</Text>
          <Text style={styles.updated}>
            {data ? `${data.total_open} open · updated ${formatUpdated(data.timestamp)}` : 'Loading…'}
          </Text>
        </View>
        <Pressable
          onPress={() => void syncNow()}
          disabled={syncing}
          accessibilityRole="button"
          style={({ pressed }) => [styles.syncBtn, (syncing || pressed) && { opacity: 0.6 }]}
        >
          {syncing ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={styles.syncText}>Sync now</Text>}
        </Pressable>
      </View>

      {data ? (
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>Total floating P&L</Text>
          <Text style={[styles.totalValue, { color: pnlColor(total) }]}>{formatMoney(total)}</Text>
        </View>
      ) : null}

      <ConnectionBanner />
      {syncError ? <Text style={styles.warn}>Sync: {syncError}</Text> : null}
      {error ? (
        <Text style={styles.err}>
          {data ? `Showing last loaded data — refresh failed: ${error}` : error}
        </Text>
      ) : null}

      {loading && !data ? (
        <View style={styles.centerFill}>
          <ActivityIndicator color={colors.accent} size="large" />
        </View>
      ) : (
        <FlatList
          data={positions}
          keyExtractor={(p) => p.position_id}
          renderItem={({ item }) => (
            <PositionCard p={item} showAccount={multiAccount} onPress={() => navigation.navigate('PositionDetail', { positionId: item.position_id })} />
          )}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.accent} colors={[colors.accent]} />}
          ListEmptyComponent={
            data ? (
              <View style={styles.empty}>
                <Text style={styles.emptyTitle}>No open positions</Text>
                <Text style={styles.emptyText}>Open a trade on Capital.com, then tap Sync now or pull down to refresh.</Text>
              </View>
            ) : null
          }
        />
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.md,
  },
  headerText: { flexShrink: 1 },
  title: { color: colors.textPrimary, fontSize: 22, fontWeight: '700' },
  updated: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  syncBtn: {
    minWidth: 92,
    alignItems: 'center',
    borderColor: 'rgba(240,185,11,0.4)',
    backgroundColor: 'rgba(240,185,11,0.1)',
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
  },
  syncText: { color: colors.accent, fontSize: 14, fontWeight: '600' },
  totalCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  totalLabel: { color: colors.textSecondary, fontSize: 13 },
  totalValue: { fontSize: 24, fontWeight: '700', fontVariant: ['tabular-nums'] },
  warn: {
    color: colors.warning,
    backgroundColor: 'rgba(245,158,11,0.1)',
    borderColor: 'rgba(245,158,11,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
    fontSize: 12,
  },
  err: {
    color: colors.negative,
    backgroundColor: 'rgba(239,68,68,0.1)',
    borderColor: 'rgba(239,68,68,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
    fontSize: 12,
  },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl, gap: spacing.md, flexGrow: 1 },
  centerFill: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  card: {
    backgroundColor: colors.surface,
    borderColor: 'rgba(240,185,11,0.3)',
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  symbolRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexShrink: 1 },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent },
  symbol: { color: colors.textPrimary, fontSize: 18, fontWeight: '700', flexShrink: 1 },
  dirPill: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  dirText: { fontSize: 11, fontWeight: '700' },
  pnl: { fontSize: 20, fontWeight: '700', fontVariant: ['tabular-nums'] },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.lg },
  stat: { minWidth: 72 },
  statLabel: { color: colors.textMuted, fontSize: 11 },
  statValue: { color: colors.textPrimary, fontSize: 14, fontWeight: '500', fontVariant: ['tabular-nums'], marginTop: 2 },
  noteRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
  tag: {
    color: colors.textSecondary,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    fontSize: 11,
    overflow: 'hidden',
  },
  tapHint: { color: colors.textMuted, fontSize: 12 },
  meta: { color: colors.textMuted, fontSize: 12 },
  note: { color: colors.textSecondary, fontSize: 13, flexBasis: '100%' },
  empty: { alignItems: 'center', paddingVertical: 64, paddingHorizontal: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  emptyText: { color: colors.textMuted, fontSize: 13, textAlign: 'center' },
})
