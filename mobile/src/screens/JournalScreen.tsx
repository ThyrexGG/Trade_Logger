import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useEffect, useMemo, useState } from 'react'
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { describeAccount, groupByAccount } from '../accountLabel'
import { AccountTag } from '../components/AccountTag'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { Text } from '../components/Text'
import { ClosedTradeRow, OpenTradeRow } from '../components/TradeRows'
import { Button, Card, Chip, ChipRow, Divider, Empty, Figures, Loading, Notice, Rows, ScreenHeader, SectionLabel, Seg, Stat, ui } from '../components/ui'
import { formatMoney } from '../format'
import { useJournal } from '../journal/JournalContext'
import { filterEntries, summarize, type DateFilter } from '../journal/filters'
import { loadPrefs, savePref } from '../journal/prefs'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, pnlColor, radius, spacing } from '../theme'

type Nav = NativeStackNavigationProp<RootStackParamList>

// short labels so all four fit one segmented control on a phone
const RANGES: { key: DateFilter; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
  { key: 'all', label: 'All' },
]

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
  const openMultiAccount = new Set(openPositions.map((p) => p.account_id)).size > 1

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

  const winRate = summary.total > 0 ? `${Math.round((summary.wins / summary.total) * 100)}%` : '—'

  const header = (
    <View style={styles.headerBlock}>
      <Seg options={RANGES} value={dateFilter} onChange={pickDate} />

      {accounts.length > 1 ? (
        <ChipRow>
          <Chip label="All accounts" on={effectiveAccount === 'ALL'} onPress={() => pickAccount('ALL')} />
          {accounts.map((a) => (
            <Chip key={a} label={describeAccount(a).label} on={effectiveAccount === a} onPress={() => pickAccount(a)} />
          ))}
        </ChipRow>
      ) : null}

      <Figures columns={4} boxed>
        <Stat small tight flex={1.7} label="Net" value={formatMoney(summary.net)} color={pnlColor(summary.net, colors.textPrimary)} />
        <Stat small tight label="Trades" value={String(summary.total)} />
        <Stat small tight label="Won" value={String(summary.wins)} />
        <Stat small tight label="Win %" value={winRate} />
      </Figures>

      <ConnectionBanner />
      {positions.syncError ? <Notice tone="warn">Sync: {positions.syncError}</Notice> : null}
      {journal.error ? <Notice>{journal.data ? `Showing the last loaded journal. Refresh failed: ${journal.error}` : journal.error}</Notice> : null}

      {openPositions.length > 0 ? (
        <>
          <SectionLabel right={String(openPositions.length)}>Open now</SectionLabel>
          <Card flush>
            {openMultiAccount ? (
              groupByAccount(openPositions).map((g, gi) => (
                <View key={g.account}>
                  {gi > 0 ? <Divider /> : null}
                  <View style={styles.accountHead}>
                    <AccountTag accountId={g.account} />
                    <Text style={ui.muted}>{g.items.length}</Text>
                  </View>
                  <Rows>
                    {g.items.map((p) => (
                      <OpenTradeRow key={p.position_id} p={p} onPress={() => navigation.navigate('PositionDetail', { positionId: p.position_id })} />
                    ))}
                  </Rows>
                </View>
              ))
            ) : (
              <Rows>
                {openPositions.map((p) => (
                  <OpenTradeRow key={p.position_id} p={p} onPress={() => navigation.navigate('PositionDetail', { positionId: p.position_id })} />
                ))}
              </Rows>
            )}
          </Card>
        </>
      ) : null}

      {entries.length > 0 ? <SectionLabel right={String(entries.length)}>Closed trades</SectionLabel> : null}
    </View>
  )

  const last = entries.length - 1

  return (
    <SafeAreaView style={ui.screen} edges={['top']}>
      <ScreenHeader
        eyebrow="Review"
        title="Journal"
        right={
          <>
            <Button label="Notes" icon="document-text-outline" size="sm" kind="secondary" onPress={() => navigation.navigate('Entries')} />
            <Button label="Sync" icon="sync-outline" size="sm" kind="secondary" busy={positions.syncing} onPress={() => void syncAndRefresh()} />
          </>
        }
      />

      {journal.loading && !journal.data ? (
        <Loading fill />
      ) : (
        <FlatList
          data={entries}
          keyExtractor={(t) => t.trade_id}
          // the closed trades read as one card: the first and last rows carry its rounded edge
          renderItem={({ item, index }) => (
            <View style={[styles.rowWrap, index === 0 && styles.rowFirst, index === last && styles.rowLast]}>
              {index > 0 ? <Divider inset={spacing.lg} /> : null}
              <ClosedTradeRow t={item} onPress={() => navigation.navigate('TradeDetail', { tradeId: item.trade_id })} showAccount={accounts.length > 1 && effectiveAccount === 'ALL'} />
            </View>
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
            journal.data ? <Empty icon="book-outline" title="No closed trades in this range" text="Try “All”, or tap Sync if you just closed a trade." /> : null
          }
        />
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xxl, flexGrow: 1 },
  headerBlock: { gap: spacing.md, paddingBottom: spacing.md },
  accountHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  rowWrap: { backgroundColor: colors.surface, borderColor: colors.border, borderLeftWidth: 1, borderRightWidth: 1, overflow: 'hidden' },
  rowFirst: { borderTopWidth: 1, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg },
  rowLast: { borderBottomWidth: 1, borderBottomLeftRadius: radius.lg, borderBottomRightRadius: radius.lg },
})
