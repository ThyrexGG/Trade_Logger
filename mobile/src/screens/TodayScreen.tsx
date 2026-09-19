import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useRef, useState, type ReactNode } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getOverview } from '../api/commandCenter'
import { formatMoney, formatPrice, formatUpdated } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { CommandCenterOverviewResponse } from '../types/commandCenter'

const REFRESH_MS = 60 * 1000

const tone = (v: number) => (v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textPrimary)
const pct = (v: number) => `${v.toFixed(1)}%`

function Card({ title, right, children }: { title: string; right?: string; children: ReactNode }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHead}>
        <Text style={styles.cardTitle}>{title}</Text>
        {right ? <Text style={styles.cardRight}>{right}</Text> : null}
      </View>
      {children}
    </View>
  )
}

function Metric({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, color ? { color } : null]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
      {sub ? <Text style={styles.metricSub}>{sub}</Text> : null}
    </View>
  )
}

function Unavailable({ name }: { name: string }) {
  return <Text style={styles.muted}>{name} is temporarily unavailable — pull down to try again.</Text>
}

/** Today: what matters right now — today's P&L, account, open risk, alerts and market context in one glance. */
export function TodayScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [data, setData] = useState<CommandCenterOverviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setLoading(true)
    getOverview(controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return
        setData(res)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load today.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [])

  // load whenever the screen is showing, and every minute while it is
  useFocusEffect(
    useCallback(() => {
      load()
      const timer = setInterval(load, REFRESH_MS)
      return () => {
        clearInterval(timer)
        inFlight.current?.abort()
      }
    }, [load]),
  )

  const degraded = new Set(data?.sections_degraded ?? [])
  const daily = data?.daily_performance ?? null
  const acct = data?.account_summary ?? null
  const pos = data?.positions ?? null
  const alerts = data?.alerts ?? null
  const mkt = data?.market_context ?? null

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={load} tintColor={colors.accent} />}
      >
        {error ? (
          <View style={styles.errBox}>
            <Text style={styles.errText}>{data ? `Showing the last good overview — refresh failed: ${error}` : error}</Text>
          </View>
        ) : null}

        {data ? (
          <>
            <Card title="Right now" right={formatUpdated(data.timestamp)}>
              <Text style={styles.big}>{data.session.current_session}</Text>
              <Text style={styles.muted}>
                Next: {data.session.next_session}
                {data.session.next_session_in_min != null ? ` in ${data.session.next_session_in_min} min` : ''} · {data.session.utc_time}
              </Text>
            </Card>

            <Card title={`Today · ${daily?.date ?? '—'}`}>
              {degraded.has('daily_performance') || !daily ? (
                <Unavailable name="Today's performance" />
              ) : (
                <View style={styles.grid}>
                  <Metric label="Net P&L" value={formatMoney(daily.net_pnl)} color={tone(daily.net_pnl)} />
                  <Metric label="Trades" value={String(daily.trades)} sub={`${daily.wins}W / ${daily.losses}L`} />
                  <Metric label="Win rate" value={daily.trades > 0 ? pct(daily.win_rate) : '—'} />
                  <Metric label="Gross win / loss" value={`${formatMoney(daily.gross_profit, false)} / ${formatMoney(Math.abs(daily.gross_loss), false)}`} />
                </View>
              )}
            </Card>

            <Card title="Account">
              {degraded.has('account_summary') || !acct ? (
                <Unavailable name="Account summary" />
              ) : (
                <View style={styles.grid}>
                  <Metric
                    label={acct.official_balance != null ? 'Balance (broker)' : 'Balance (derived)'}
                    value={formatMoney(acct.official_balance ?? acct.derived_balance, false)}
                  />
                  <Metric label="All-time net P&L" value={formatMoney(acct.all_time_net_pnl)} color={tone(acct.all_time_net_pnl)} />
                  <Metric label="Profit factor" value={acct.profit_factor.toFixed(2)} sub={`${acct.all_time_trades} trades · ${pct(acct.all_time_win_rate)} win`} />
                  <Metric
                    label="Max drawdown"
                    value={pct(acct.max_drawdown_pct)}
                    color={acct.max_drawdown_pct >= 10 ? colors.negative : acct.max_drawdown_pct >= 5 ? colors.warning : undefined}
                  />
                </View>
              )}
            </Card>

            <Card title="Open positions">
              {degraded.has('positions') || !pos ? (
                <Unavailable name="Positions" />
              ) : pos.total_open === 0 ? (
                <Text style={styles.muted}>No open positions.</Text>
              ) : (
                <>
                  <View style={styles.grid}>
                    <Metric label="Open" value={String(pos.total_open)} sub={`${pos.long_count} long / ${pos.short_count} short`} />
                    <Metric label="Floating P&L" value={formatMoney(pos.total_floating_pnl)} color={tone(pos.total_floating_pnl)} />
                  </View>
                  {pos.by_symbol.map((s) => (
                    <View key={s.symbol} style={styles.line}>
                      <Text style={styles.lineLabel}>
                        {s.symbol} <Text style={styles.muted}>× {s.count}</Text>
                      </Text>
                      <Text style={[styles.lineValue, { color: tone(s.floating_pnl) }]}>{formatMoney(s.floating_pnl)}</Text>
                    </View>
                  ))}
                </>
              )}
            </Card>

            <Card title="Price alerts">
              {degraded.has('alerts') || !alerts ? (
                <Unavailable name="Alerts" />
              ) : (
                <>
                  <Text style={styles.body}>
                    {alerts.active} active · {alerts.triggered} triggered
                  </Text>
                  {alerts.triggered_recent.map((a) => (
                    <View key={a.id} style={styles.line}>
                      <Text style={styles.lineLabel}>
                        {a.symbol} {a.condition === 'ABOVE' ? 'above' : 'below'} {formatPrice(a.target_price)}
                      </Text>
                      <Text style={styles.muted}>{formatUpdated(a.triggered_at)}</Text>
                    </View>
                  ))}
                  <Pressable onPress={() => navigation.navigate('PriceAlerts')} style={styles.linkBtn} accessibilityRole="button">
                    <Text style={styles.linkText}>Manage alerts</Text>
                  </Pressable>
                </>
              )}
            </Card>

            <Card title="Market context">
              {degraded.has('market_context') || !mkt ? (
                <Text style={styles.muted}>Market context is not available right now.</Text>
              ) : (
                <>
                  <Text style={styles.body}>
                    {mkt.primary_regime} <Text style={styles.muted}>· {Math.round(mkt.regime_confidence_pct)}% confidence</Text>
                  </Text>
                  <Text style={styles.muted}>
                    Breadth {pct(mkt.breadth_bullish_pct)} bullish / {pct(mkt.breadth_bearish_pct)} bearish · strongest {mkt.strongest_asset} · weakest {mkt.weakest_asset} · USD {mkt.usd_strength_state}
                  </Text>
                </>
              )}
            </Card>

            {data.watchlist_highlights.length > 0 ? (
              <Card title="Watchlist">
                {data.watchlist_highlights.map((w) => (
                  <View key={w.symbol} style={styles.line}>
                    <Text style={styles.lineLabel}>{w.symbol}</Text>
                    <Text style={styles.lineValue}>
                      {w.last_price != null ? formatPrice(w.last_price) : '—'}
                      {w.bias ? <Text style={styles.muted}>  {w.bias}</Text> : null}
                    </Text>
                  </View>
                ))}
              </Card>
            ) : null}

            <Text style={styles.disclaimer}>Read-only summary. Refreshes every minute while this screen is open. Nothing here places a trade.</Text>
          </>
        ) : loading ? (
          <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  cardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  cardRight: { color: colors.textMuted, fontSize: 11 },
  big: { color: colors.accent, fontSize: 22, fontWeight: '700' },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  muted: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  metric: { flexBasis: '47%', flexGrow: 1, backgroundColor: colors.surfaceElevated, borderRadius: radius.md, padding: spacing.md, gap: 2 },
  metricLabel: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 },
  metricValue: { color: colors.textPrimary, fontSize: 18, fontWeight: '700', fontVariant: ['tabular-nums'] },
  metricSub: { color: colors.textMuted, fontSize: 11 },
  line: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.md },
  lineLabel: { color: colors.textPrimary, fontSize: 14, flexShrink: 1 },
  lineValue: { color: colors.textPrimary, fontSize: 14, fontVariant: ['tabular-nums'] },
  linkBtn: { alignSelf: 'flex-start', borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.1)', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  linkText: { color: colors.accent, fontWeight: '700', fontSize: 13 },
  errBox: { backgroundColor: 'rgba(239,68,68,0.1)', borderColor: 'rgba(239,68,68,0.4)', borderWidth: 1, borderRadius: radius.md, padding: spacing.md },
  errText: { color: colors.negative, fontSize: 13 },
  disclaimer: { color: colors.textMuted, fontSize: 11, lineHeight: 16, textAlign: 'center' },
})
