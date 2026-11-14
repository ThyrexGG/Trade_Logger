import { Ionicons } from '@expo/vector-icons'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { AccountTag } from '../components/AccountTag'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { Text } from '../components/Text'
import { Button, DirTag, Empty, Figures, LiveDot, Loading, Notice, ScreenHeader, Stat, Tag, ui } from '../components/ui'
import { formatMoney, formatPrice, formatUpdated, formatWhen } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, pnlColor, radius, spacing, type } from '../theme'
import type { PositionItem } from '../types/positions'

/** One open trade: what and how it is doing on the first line, the numbers as one divided panel, your note under it. */
function PositionCard({ p, onPress, showAccount }: { p: PositionItem; onPress: () => void; showAccount: boolean }) {
  const opened = formatWhen(p.open_time)
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.card, pressed && { backgroundColor: colors.surfaceHover }]}>
      <View style={styles.cardTop}>
        <View style={styles.symbolRow}>
          <LiveDot />
          <Text style={styles.symbol}>{p.symbol}</Text>
          <DirTag direction={p.direction} />
          {showAccount ? <AccountTag accountId={p.account_id} /> : null}
        </View>
        <Text style={[styles.pnl, { color: pnlColor(p.floating_pnl) }]}>{formatMoney(p.floating_pnl)}</Text>
      </View>

      <Figures columns={3} style={styles.figures}>
        <Stat small label="Entry" value={formatPrice(p.entry_price)} />
        <Stat small label="Now" value={formatPrice(p.current_price)} />
        <Stat small label="Size" value={String(p.volume)} />
        <Stat small label="Stop" value={p.sl ? formatPrice(p.sl) : 'None'} color={p.sl ? undefined : colors.warning} />
        <Stat small label="Target" value={p.tp ? formatPrice(p.tp) : '—'} />
        <Stat small label="Opened" value={opened.main} sub={opened.sub} />
      </Figures>

      <View style={styles.foot}>
        <View style={styles.footLeft}>
          {p.setup_tag ? <Tag text={p.setup_tag} /> : null}
          {p.screenshot_count ? (
            <View style={styles.shots}>
              <Ionicons name="image-outline" size={12} color={colors.textMuted} />
              <Text style={ui.muted}>{p.screenshot_count}</Text>
            </View>
          ) : null}
          <Text style={styles.note} numberOfLines={1}>
            {p.notes || (p.setup_tag ? '' : 'Add a note while it runs')}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={15} color={colors.textMuted} />
      </View>
    </Pressable>
  )
}

export function PositionsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { data, loading, refreshing, error, refresh, syncing, syncError, syncNow } = usePositionsContext()
  const positions = data?.positions ?? []
  const total = data?.total_floating_pnl ?? 0
  const multiAccount = new Set(positions.map((p) => p.account_id)).size > 1

  return (
    <SafeAreaView style={ui.screen} edges={['top']}>
      <ScreenHeader
        eyebrow="Open now"
        title="Positions"
        sub={data ? `Updated ${formatUpdated(data.timestamp)}` : undefined}
        right={<Button label="Sync" icon="sync-outline" size="sm" kind="secondary" busy={syncing} onPress={() => void syncNow()} />}
      />

      {loading && !data ? (
        <Loading fill />
      ) : (
        <FlatList
          data={positions}
          keyExtractor={(p) => p.position_id}
          renderItem={({ item }) => (
            <PositionCard p={item} showAccount={multiAccount} onPress={() => navigation.navigate('PositionDetail', { positionId: item.position_id })} />
          )}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.accent} colors={[colors.accent]} />}
          ListHeaderComponent={
            <View style={styles.head}>
              <ConnectionBanner />
              {syncError ? <Notice tone="warn">Sync: {syncError}</Notice> : null}
              {error ? <Notice>{data ? `Showing the last loaded data. Refresh failed: ${error}` : error}</Notice> : null}
              {data && positions.length > 0 ? (
                <View style={styles.total}>
                  <View>
                    <Text style={styles.totalLabel}>Floating P&L</Text>
                    <Text style={ui.muted}>
                      {positions.length} open trade{positions.length === 1 ? '' : 's'}
                    </Text>
                  </View>
                  <Text style={[styles.totalValue, { color: pnlColor(total) }]} numberOfLines={1} adjustsFontSizeToFit>
                    {formatMoney(total)}
                  </Text>
                </View>
              ) : null}
            </View>
          }
          ListEmptyComponent={
            data ? (
              <Empty icon="pulse-outline" title="No open trades" text="When you open a trade with your broker it shows up here. Tap Sync or pull down to check now." />
            ) : null
          }
        />
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md, flexGrow: 1 },
  head: { gap: spacing.md },
  total: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md, paddingVertical: spacing.xs },
  totalLabel: { ...type.label },
  totalValue: { ...type.hero, fontSize: 30, lineHeight: 36, flexShrink: 1 },
  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, overflow: 'hidden' },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.md, padding: spacing.lg },
  // the badges wrap onto a second line instead of running under the P&L
  symbolRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', columnGap: spacing.sm, rowGap: 4, flex: 1 },
  symbol: { ...type.heading, fontSize: 17, lineHeight: 22 },
  pnl: { ...type.figure, flexShrink: 0 },
  figures: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: colors.borderSubtle },
  foot: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: 11 },
  footLeft: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
  shots: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  note: { ...type.small, flex: 1 },
})
