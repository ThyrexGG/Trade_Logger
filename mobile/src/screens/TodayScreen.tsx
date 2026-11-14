import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useMemo, useRef, useState } from 'react'
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getOverview } from '../api/commandCenter'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { Text } from '../components/Text'
import { ClosedTradeRow, OpenTradeRow } from '../components/TradeRows'
import { Button, Card, Fact, Figures, Footnote, Notice, Row, Rows, ScreenHeader, Stat, ui } from '../components/ui'
import { formatMoney, formatPrice, formatUpdated } from '../format'
import { useJournal } from '../journal/JournalContext'
import { filterEntries, summarize } from '../journal/filters'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, pnlColor, spacing, type } from '../theme'
import type { CommandCenterOverviewResponse } from '../types/commandCenter'

const REFRESH_MS = 60 * 1000

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/**
 * Today: the answer first — what you made or lost today — then what is open right now, what closed,
 * and the market around it. Your own numbers come from the trades already on the phone, so they show at once;
 * the market section fills in when the server answers.
 */
export function TodayScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const journal = useJournal()
  const positions = usePositionsContext()
  const [overview, setOverview] = useState<CommandCenterOverviewResponse | null>(null)
  const [overviewError, setOverviewError] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const loadOverview = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    getOverview(controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return
        setOverview(res)
        setOverviewError(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) setOverviewError(true)
      })
  }, [])

  // load whenever the tab is showing, and every minute while it is
  useFocusEffect(
    useCallback(() => {
      loadOverview()
      const timer = setInterval(loadOverview, REFRESH_MS)
      return () => {
        clearInterval(timer)
        inFlight.current?.abort()
      }
    }, [loadOverview]),
  )

  const entries = journal.data?.entries
  const today = useMemo(() => (entries ? filterEntries(entries, 'ALL', 'today') : []), [entries])
  const todaySum = useMemo(() => summarize(today), [today])
  const weekSum = useMemo(() => summarize(entries ? filterEntries(entries, 'ALL', 'week') : []), [entries])

  const open = positions.data?.positions ?? []
  const floating = positions.data?.total_floating_pnl ?? 0
  const multiAccount = (journal.data?.accounts.length ?? 0) > 1

  const degraded = new Set(overview?.sections_degraded ?? [])
  const acct = overview && !degraded.has('account_summary') ? overview.account_summary : null
  const alerts = overview && !degraded.has('alerts') ? overview.alerts : null
  const mkt = overview && !degraded.has('market_context') ? overview.market_context : null
  const balance = acct ? (acct.official_balance ?? acct.derived_balance) : null

  function refreshAll() {
    positions.refresh()
    void journal.refresh()
    loadOverview()
  }
  async function syncAll() {
    await positions.syncNow()
    await journal.refresh()
    loadOverview()
  }

  const dateLine = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })

  return (
    <SafeAreaView style={ui.screen} edges={['top']}>
      <ScreenHeader
        eyebrow={dateLine}
        title="Today"
        right={<Button label="Sync" icon="sync-outline" size="sm" kind="secondary" busy={positions.syncing} onPress={() => void syncAll()} />}
      />
      <ScrollView
        contentContainerStyle={ui.content}
        refreshControl={<RefreshControl refreshing={journal.refreshing || positions.refreshing} onRefresh={refreshAll} tintColor={colors.accent} colors={[colors.accent]} />}
      >
        <ConnectionBanner />
        {positions.syncError ? <Notice tone="warn">Sync: {positions.syncError}</Notice> : null}
        {journal.error && !journal.data ? <Notice>{journal.error}</Notice> : null}

        <Card feature flush>
          <View style={styles.heroBlock}>
            <Text style={styles.heroLabel}>Closed today</Text>
            <Text style={[styles.hero, { color: pnlColor(todaySum.net, colors.textPrimary) }]} numberOfLines={1} adjustsFontSizeToFit>
              {journal.data ? formatMoney(todaySum.net) : '—'}
            </Text>
            <Text style={ui.muted}>
              {!journal.data
                ? 'Loading your trades…'
                : todaySum.total === 0
                  ? 'No trades closed today yet.'
                  : `${count(todaySum.total, 'trade')} · ${count(todaySum.wins, 'win')} · ${count(todaySum.losses, 'loss', 'losses')}`}
              {multiAccount && todaySum.total > 0 ? ' · all accounts' : ''}
            </Text>
          </View>
          <Figures columns={3} style={styles.heroFigures}>
            <Stat small label="Open now" value={open.length ? formatMoney(floating) : '—'} color={open.length ? pnlColor(floating) : undefined} sub={open.length ? count(open.length, 'trade') : 'nothing open'} />
            <Stat small label="This week" value={journal.data ? formatMoney(weekSum.net) : '—'} color={pnlColor(weekSum.net, colors.textPrimary)} sub={count(weekSum.total, 'trade')} />
            <Stat small label="Balance" value={balance != null ? formatMoney(balance, false) : '—'} sub={acct ? (acct.official_balance != null ? 'from broker' : 'estimated') : undefined} />
          </Figures>
        </Card>

        <Card title="Open trades" right={open.length ? String(open.length) : undefined} flush>
          {open.length === 0 ? (
            <Text style={styles.quiet}>{positions.data ? 'Nothing open right now.' : 'Loading…'}</Text>
          ) : (
            <Rows>
              {open.map((p) => (
                <OpenTradeRow key={p.position_id} p={p} showAccount={multiAccount} onPress={() => navigation.navigate('PositionDetail', { positionId: p.position_id })} />
              ))}
            </Rows>
          )}
        </Card>

        {today.length > 0 ? (
          <Card title="Closed today" right={String(today.length)} flush>
            <Rows>
              {today.map((t) => (
                <ClosedTradeRow key={t.trade_id} t={t} showAccount={multiAccount} onPress={() => navigation.navigate('TradeDetail', { tradeId: t.trade_id })} />
              ))}
            </Rows>
          </Card>
        ) : null}

        {overview ? (
          <Card title="Market now" right={formatUpdated(overview.timestamp)} flush>
            <Rows inset={0}>
              <Fact label="Session" value={overview.session.current_session} />
              <Fact
                label="Next"
                value={`${overview.session.next_session}${overview.session.next_session_in_min != null ? ` in ${overview.session.next_session_in_min} min` : ''}`}
              />
              {mkt ? <Fact label="Market mood" value={`${mkt.primary_regime} · ${Math.round(mkt.regime_confidence_pct)}% sure`} /> : null}
              {mkt ? <Fact label="US dollar" value={mkt.usd_strength_state} /> : null}
              {mkt ? <Fact label="Strongest / weakest" value={`${mkt.strongest_asset} / ${mkt.weakest_asset}`} /> : null}
            </Rows>
          </Card>
        ) : overviewError ? (
          <Notice tone="warn" onPress={loadOverview}>
            The market summary didn't load. Your trades above are up to date. Tap to try again.
          </Notice>
        ) : null}

        <Card flush>
          <Row
            icon="notifications-outline"
            title="Price alerts"
            sub={alerts ? `${alerts.active} active · ${alerts.triggered} triggered` : 'Get told when a price crosses your level'}
            chevron
            onPress={() => navigation.navigate('PriceAlerts')}
          />
          {alerts && alerts.triggered_recent.length > 0 ? (
            <View style={styles.alertList}>
              {alerts.triggered_recent.map((a) => (
                <View key={a.id} style={ui.rowBetween}>
                  <Text style={ui.sub}>
                    {a.symbol} {a.condition === 'ABOVE' ? 'above' : 'below'} <Text style={ui.num}>{formatPrice(a.target_price)}</Text>
                  </Text>
                  <Text style={styles.time}>{formatUpdated(a.triggered_at)}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </Card>

        {overview && overview.watchlist_highlights.length > 0 ? (
          <Card title="Watchlist" flush>
            <Rows inset={0}>
              {overview.watchlist_highlights.map((w) => (
                <Fact key={w.symbol} label={w.bias ? `${w.symbol} · ${w.bias}` : w.symbol} value={w.last_price != null ? formatPrice(w.last_price) : '—'} />
              ))}
            </Rows>
          </Card>
        ) : null}

        <Footnote>Read-only. Nothing here places a trade.</Footnote>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  heroBlock: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.md, gap: 2 },
  heroLabel: { ...type.label },
  hero: { ...type.hero },
  heroFigures: { borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  quiet: { ...type.small, fontSize: 13, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  alertList: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md, gap: 6, borderTopWidth: 1, borderTopColor: colors.borderSubtle, paddingTop: spacing.md },
  time: { ...type.small, fontVariant: ['tabular-nums'] },
})
