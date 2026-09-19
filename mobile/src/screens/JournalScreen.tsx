import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { formatMoney, formatUpdated, isBuy } from '../format'
import { useJournal } from '../journal/JournalContext'
import { DATE_FILTERS, filterEntries, summarize, type DateFilter } from '../journal/filters'
import { loadPrefs, savePref } from '../journal/prefs'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, radius, spacing } from '../theme'
import type { JournalTradeItem } from '../types/journal'
import type { PositionItem } from '../types/positions'

type Nav = NativeStackNavigationProp<RootStackParamList>

function pnlColor(v: number): string {
  return v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textSecondary
}

export function Stars({ n }: { n: number | null | undefined }) {
  if (!n || n <= 0) return null
  return <Text style={styles.stars}>{'★'.repeat(Math.min(5, n))}</Text>
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={[styles.chip, active && styles.chipActive]}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  )
}

function OpenRow({ p, onPress }: { p: PositionItem; onPress: () => void }) {
  const dirColor = isBuy(p.direction) ? colors.positive : colors.negative
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.openRow, pressed && { opacity: 0.7 }]}>
      <View style={styles.openLeft}>
        <View style={styles.liveDot} />
        <Text style={styles.openSymbol}>{p.symbol}</Text>
        <Text style={[styles.openDir, { color: dirColor }]}>{p.direction.toUpperCase()}</Text>
        <Text style={styles.openVol}>{p.volume}</Text>
      </View>
      <Text style={[styles.openPnl, { color: pnlColor(p.floating_pnl) }]}>{formatMoney(p.floating_pnl)}</Text>
    </Pressable>
  )
}

function TradeRow({ t, onPress }: { t: JournalTradeItem; onPress: () => void }) {
  const dirColor = isBuy(t.direction) ? colors.positive : colors.negative
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.tradeRow, pressed && { opacity: 0.7 }]}>
      <View style={styles.tradeTop}>
        <View style={styles.tradeLeft}>
          <Text style={styles.symbol}>{t.symbol}</Text>
          <Text style={[styles.dir, { color: dirColor }]}>{t.direction.toUpperCase()}</Text>
          <Text style={styles.vol}>{t.volume}</Text>
        </View>
        <Text style={[styles.net, { color: pnlColor(t.net_profit) }]}>{formatMoney(t.net_profit)}</Text>
      </View>
      <View style={styles.tradeMeta}>
        <Text style={styles.metaText}>{formatUpdated(t.exit_time)}</Text>
        {t.setup_tag ? <Text style={styles.tag}>{t.setup_tag}</Text> : null}
        <Stars n={t.rating} />
        {t.screenshot_count ? <Text style={styles.metaText}>📷 {t.screenshot_count}</Text> : null}
      </View>
      {t.notes ? (
        <Text style={styles.notes} numberOfLines={2}>
          {t.notes}
        </Text>
      ) : null}
    </Pressable>
  )
}

export function JournalScreen() {
  const navigation = useNavigation<Nav>()
  const journal = useJournal()
  const positions = usePositionsContext()
  const [dateFilter, setDateFilter] = useState<DateFilter>('week')
  const [account, setAccount] = useState('ALL')

  useEffect(() => {
    let cancelled = false
    void loadPrefs().then((p) => {
      if (cancelled) return
      setDateFilter(p.dateFilter)
      setAccount(p.account)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const accounts = journal.data?.accounts ?? []
  // A remembered account that no longer exists would silently hide everything.
  const effectiveAccount = account === 'ALL' || accounts.includes(account) ? account : 'ALL'

  const entries = useMemo(
    () => (journal.data ? filterEntries(journal.data.entries, effectiveAccount, dateFilter) : []),
    [journal.data, effectiveAccount, dateFilter],
  )
  const summary = useMemo(() => summarize(entries), [entries])
  const openPositions = useMemo(() => {
    const all = positions.data?.positions ?? []
    return effectiveAccount === 'ALL' ? all : all.filter((p) => p.account_id === effectiveAccount)
  }, [positions.data, effectiveAccount])

  function pickDate(f: DateFilter) {
    setDateFilter(f)
    savePref('dateFilter', f)
  }
  function pickAccount(a: string) {
    setAccount(a)
    savePref('account', a)
  }

  async function syncAndRefresh() {
    await positions.syncNow()
    await journal.refresh()
  }

  const header = (
    <View style={styles.headerBlock}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
        {DATE_FILTERS.map((f) => (
          <Chip key={f.key} label={f.label} active={dateFilter === f.key} onPress={() => pickDate(f.key)} />
        ))}
      </ScrollView>

      {accounts.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          <Chip label="All accounts" active={effectiveAccount === 'ALL'} onPress={() => pickAccount('ALL')} />
          {accounts.map((a) => (
            <Chip key={a} label={a} active={effectiveAccount === a} onPress={() => pickAccount(a)} />
          ))}
        </ScrollView>
      ) : null}

      <View style={styles.summary}>
        <SummaryCell label="Trades" value={String(summary.total)} />
        <SummaryCell label="Wins" value={String(summary.wins)} color={colors.positive} />
        <SummaryCell label="Losses" value={String(summary.losses)} color={colors.negative} />
        <SummaryCell label="Net P&L" value={formatMoney(summary.net)} color={pnlColor(summary.net)} />
      </View>

      <ConnectionBanner />
      {positions.syncError ? <Text style={styles.warn}>Sync: {positions.syncError}</Text> : null}
      {journal.error ? (
        <Text style={styles.err}>
          {journal.data ? `Showing last loaded journal — refresh failed: ${journal.error}` : journal.error}
        </Text>
      ) : null}

      {openPositions.length > 0 ? (
        <View style={styles.openBlock}>
          <Text style={styles.sectionTitle}>Open now ({openPositions.length})</Text>
          {openPositions.map((p) => (
            <OpenRow key={p.position_id} p={p} onPress={() => navigation.navigate('PositionDetail', { positionId: p.position_id })} />
          ))}
        </View>
      ) : null}

      {entries.length > 0 ? <Text style={styles.sectionTitle}>Closed trades</Text> : null}
    </View>
  )

  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <View style={styles.titleRow}>
        <Text style={styles.title}>Journal</Text>
        <Pressable
          onPress={() => void syncAndRefresh()}
          disabled={positions.syncing}
          accessibilityRole="button"
          style={({ pressed }) => [styles.syncBtn, (positions.syncing || pressed) && { opacity: 0.6 }]}
        >
          {positions.syncing ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={styles.syncText}>Sync now</Text>}
        </Pressable>
      </View>

      {journal.loading && !journal.data ? (
        <View style={styles.centerFill}>
          <ActivityIndicator color={colors.accent} size="large" />
        </View>
      ) : (
        <FlatList
          data={entries}
          keyExtractor={(t) => t.trade_id}
          renderItem={({ item }) => (
            <TradeRow t={item} onPress={() => navigation.navigate('TradeDetail', { tradeId: item.trade_id })} />
          )}
          ListHeaderComponent={header}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={journal.refreshing}
              onRefresh={() => {
                positions.refresh()
                void journal.refresh()
              }}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          }
          ListEmptyComponent={
            journal.data ? (
              <View style={styles.empty}>
                <Text style={styles.emptyTitle}>No closed trades in this range</Text>
                <Text style={styles.emptyText}>Try “All time”, or tap Sync now if you just closed a trade.</Text>
              </View>
            ) : null
          }
        />
      )}
    </SafeAreaView>
  )
}

function SummaryCell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.cell}>
      <Text style={styles.cellLabel}>{label}</Text>
      <Text style={[styles.cellValue, color ? { color } : null]}>{value}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  title: { color: colors.textPrimary, fontSize: 22, fontWeight: '700' },
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
  centerFill: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { paddingBottom: spacing.xl, flexGrow: 1 },
  headerBlock: { gap: spacing.md, paddingBottom: spacing.sm },
  chipRow: { paddingHorizontal: spacing.lg, gap: spacing.sm },
  chip: {
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md + 2,
    paddingVertical: spacing.sm,
  },
  chipActive: { backgroundColor: 'rgba(240,185,11,0.12)', borderColor: 'rgba(240,185,11,0.5)' },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: '500' },
  chipTextActive: { color: colors.accent, fontWeight: '600' },
  summary: {
    flexDirection: 'row',
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingVertical: spacing.md,
  },
  cell: { flex: 1, alignItems: 'center', gap: 2 },
  cellLabel: { color: colors.textMuted, fontSize: 11 },
  cellValue: { color: colors.textPrimary, fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  warn: {
    color: colors.warning,
    backgroundColor: 'rgba(245,158,11,0.1)',
    borderColor: 'rgba(245,158,11,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    marginHorizontal: spacing.lg,
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
    padding: spacing.md,
    fontSize: 12,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    paddingHorizontal: spacing.lg,
  },
  openBlock: { gap: spacing.sm },
  openRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderColor: 'rgba(240,185,11,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    marginHorizontal: spacing.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  openLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexShrink: 1 },
  liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.accent },
  openSymbol: { color: colors.textPrimary, fontSize: 15, fontWeight: '700' },
  openDir: { fontSize: 11, fontWeight: '700' },
  openVol: { color: colors.textMuted, fontSize: 12 },
  openPnl: { fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  tradeRow: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    backgroundColor: colors.surface,
    borderColor: colors.borderSubtle,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  tradeTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  tradeLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexShrink: 1 },
  symbol: { color: colors.textPrimary, fontSize: 16, fontWeight: '700' },
  dir: { fontSize: 11, fontWeight: '700' },
  vol: { color: colors.textMuted, fontSize: 12 },
  net: { fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  tradeMeta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
  metaText: { color: colors.textMuted, fontSize: 12 },
  tag: {
    color: colors.textSecondary,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    fontSize: 11,
    overflow: 'hidden',
  },
  stars: { color: colors.warning, fontSize: 12 },
  notes: { color: colors.textSecondary, fontSize: 13 },
  empty: { alignItems: 'center', paddingVertical: 48, paddingHorizontal: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  emptyText: { color: colors.textMuted, fontSize: 13, textAlign: 'center' },
})
