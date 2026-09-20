import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { saveInitialBalance } from '../api/analytics'
import { useAnalytics } from '../analytics/useAnalytics'
import { EquityChart } from '../components/analytics/EquityChart'
import { MonthCalendar } from '../components/analytics/MonthCalendar'
import { PnlBars } from '../components/analytics/PnlBars'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { formatMoney } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { AnalyticsQuery } from '../types/analytics'

type RangeKey = '7d' | '30d' | 'month' | '90d' | 'all'
const RANGES: { key: RangeKey; label: string }[] = [
  { key: '7d', label: '7 days' },
  { key: '30d', label: '30 days' },
  { key: 'month', label: 'This month' },
  { key: '90d', label: '90 days' },
  { key: 'all', label: 'All time' },
]

const pad = (n: number) => String(n).padStart(2, '0')
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

/** Start date (local, YYYY-MM-DD) for a range chip; undefined = from the first trade. */
function rangeStart(key: RangeKey): string | undefined {
  const now = new Date()
  if (key === 'all') return undefined
  if (key === 'month') return isoDay(new Date(now.getFullYear(), now.getMonth(), 1))
  const back = key === '7d' ? 6 : key === '30d' ? 29 : 89
  return isoDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - back))
}

function tone(v: number): string {
  return v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textPrimary
}

function pct(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function holdTime(mins: number): string {
  if (!Number.isFinite(mins) || mins <= 0) return '—'
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = Math.floor(mins % 60)
  return d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${m}m` : `${m}m`
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      {children}
    </View>
  )
}

function Tile({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.tileValue, color ? { color } : null]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
      {sub ? (
        <Text style={styles.tileSub} numberOfLines={2}>
          {sub}
        </Text>
      ) : null}
    </View>
  )
}

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, on && styles.chipOn]} accessibilityRole="button" accessibilityState={{ selected: on }}>
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  )
}

export function AnalyticsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [account, setAccount] = useState<string | undefined>(undefined)
  const [range, setRange] = useState<RangeKey>('all')
  const [balance, setBalance] = useState(10000)
  const [balanceText, setBalanceText] = useState('10000')
  const [autoFilled, setAutoFilled] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const query: AnalyticsQuery = { account, start: rangeStart(range), initial_balance: balance }
  const { data, loading, refreshing, error, refresh } = useAnalytics(query)

  // The tab stays mounted, so a trade logged / fixed / deleted elsewhere is picked up when you come back to it.
  const refreshRef = useRef(refresh)
  refreshRef.current = refresh
  const seenOnce = useRef(false)
  useFocusEffect(
    useCallback(() => {
      if (seenOnce.current) refreshRef.current()
      seenOnce.current = true
    }, []),
  )
  const accounts = data?.available.accounts ?? []
  const noAccount = !account || account === 'ALL'

  // One account: start on it, so the starting balance can be saved (a saved balance is per account).
  const autoPicked = useRef(false)
  useEffect(() => {
    if (autoPicked.current || !data) return
    autoPicked.current = true
    if (noAccount && data.available.accounts.length === 1) setAccount(data.available.accounts[0])
  }, [data, noAccount])

  // Picking an account prefills its starting balance once: the user's saved value wins over the server's guess.
  const appliedFor = useRef<string | null>(null)
  useEffect(() => {
    if (!data || noAccount || appliedFor.current === account) return
    if (data.filters_applied.account !== account) return // response is for the previous filter
    const saved = data.available.saved_initial_balance
    const suggested = data.available.suggested_initial_balance
    const next = saved ?? suggested
    if (next == null) return
    appliedFor.current = account ?? null
    setAutoFilled(saved == null)
    setBalance(next)
    setBalanceText(String(next))
  }, [data, account, noAccount])

  // Typing a balance: use it immediately, save it 0.8 s after the last keystroke (and on leaving the screen).
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pending = useRef<{ acct: string; n: number } | null>(null)
  function flushSave() {
    if (saveTimer.current) {
      clearTimeout(saveTimer.current)
      saveTimer.current = null
    }
    const p = pending.current
    if (!p) return
    pending.current = null
    setSaveState('saving')
    saveInitialBalance(p.acct, p.n)
      .then(() => setSaveState('saved'))
      .catch(() => setSaveState('error'))
  }
  useEffect(() => flushSave, []) // eslint-disable-line react-hooks/exhaustive-deps

  function onBalanceChange(text: string) {
    setBalanceText(text)
    setAutoFilled(false)
    const n = Number(text.replace(/[, $]/g, ''))
    if (!Number.isFinite(n) || n <= 0) return
    setBalance(n)
    if (!account) return
    pending.current = { acct: account, n }
    setSaveState('idle')
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(flushSave, 800)
  }

  const m = data?.metrics
  const pr = data?.period_returns

  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <ConnectionBanner />
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing && !!data} onRefresh={refresh} tintColor={colors.accent} />}
      >
        <Text style={styles.title}>Analytics</Text>

        {accounts.length > 1 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            <Chip label="All accounts" on={noAccount} onPress={() => setAccount(undefined)} />
            {accounts.map((a) => (
              <Chip key={a} label={a} on={account === a} onPress={() => setAccount(a)} />
            ))}
          </ScrollView>
        ) : null}

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {RANGES.map((r) => (
            <Chip key={r.key} label={r.label} on={range === r.key} onPress={() => setRange(r.key)} />
          ))}
        </ScrollView>

        <View style={styles.balanceRow}>
          <View style={styles.balanceLabelWrap}>
            <Text style={styles.balanceLabel}>Starting balance ($)</Text>
            {autoFilled ? <Text style={styles.autoTag}>AUTO</Text> : null}
          </View>
          <TextInput
            value={balanceText}
            onChangeText={onBalanceChange}
            keyboardType="decimal-pad"
            style={styles.balanceInput}
            placeholderTextColor={colors.textMuted}
            selectTextOnFocus
          />
        </View>
        <Text style={styles.balanceHint}>
          {noAccount && accounts.length > 1
            ? 'Pick an account above to save this balance.'
            : saveState === 'saving'
              ? 'Saving…'
              : saveState === 'saved'
                ? `✓ Saved for ${account}`
                : saveState === 'error'
                  ? 'Couldn’t save — check your connection and retype it.'
                  : ' '}
        </Text>

        {loading && !data ? (
          <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} />
        ) : error && !data ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={refresh} style={styles.retry} accessibilityRole="button">
              <Text style={styles.retryText}>Try again</Text>
            </Pressable>
          </View>
        ) : data && m && pr ? (
          <>
            {error ? <Text style={styles.stale}>Showing the last good numbers — refresh failed.</Text> : null}
            {data.matched_trades === 0 ? (
              <Card title="Performance">
                <Text style={styles.muted}>No closed trades match these filters. Try another account or a longer range.</Text>
              </Card>
            ) : (
              <>
                <View style={styles.tiles}>
                  <Tile
                    label={data.official_balance != null ? 'Balance (broker)' : 'Balance (derived)'}
                    value={formatMoney(data.official_balance ?? m.final_balance, false)}
                    sub={`${pct(m.gain_pct)} · ${formatMoney(m.total_net_pnl)}`}
                    color={tone(m.total_net_pnl)}
                  />
                  <Tile
                    label="Win rate"
                    value={`${m.win_rate.toFixed(1)}%`}
                    sub={`${m.winning_trades}W / ${m.losing_trades}L · ${m.total_trades} trades`}
                    color={m.win_rate >= 50 ? colors.positive : undefined}
                  />
                  <Tile
                    label="Profit factor"
                    value={m.profit_factor.toFixed(2)}
                    sub={`won ${formatMoney(m.total_gross_profit, false)} · lost ${formatMoney(m.total_gross_loss, false)}`}
                  />
                  <Tile
                    label="Max drawdown"
                    value={`${m.max_drawdown_pct.toFixed(2)}%`}
                    sub={`${formatMoney(m.max_drawdown_usd, false)} from peak ${formatMoney(m.peak_balance, false)}`}
                    color={m.max_drawdown_pct >= 10 ? colors.negative : m.max_drawdown_pct >= 5 ? colors.warning : undefined}
                  />
                  <Tile
                    label="Expectancy / trade"
                    value={formatMoney(m.expectancy)}
                    sub={`avg win ${formatMoney(m.avg_win, false)} · avg loss ${formatMoney(Math.abs(m.avg_loss), false)}`}
                    color={tone(m.expectancy)}
                  />
                  <Tile
                    label="SQN"
                    value={m.sqn.toFixed(2)}
                    sub={m.sqn > 2.5 ? 'excellent' : m.sqn > 1.5 ? 'good' : m.sqn > 0 ? 'average' : 'negative edge'}
                    color={tone(m.sqn)}
                  />
                  <Tile label="Avg holding time" value={holdTime(m.avg_duration_minutes)} sub="per closed trade" />
                  <Tile
                    label="Best / worst trade"
                    value={`${formatMoney(m.best_trade)} / ${formatMoney(m.worst_trade)}`}
                    sub={`win/loss ratio ${m.win_loss_ratio.toFixed(2)}`}
                  />
                </View>

                <Card title="Calendar">
                  <MonthCalendar
                    key={`${account ?? 'ALL'}:${range}`}
                    daily={data.daily_pnl}
                    onDayPress={(date) => navigation.navigate('DayTrades', { date, account })}
                  />
                </Card>

                <Card title={`Account balance curve · ${data.equity_curve.length} points${data.equity_curve_sampled ? ' (sampled)' : ''}`}>
                  <EquityChart points={data.equity_curve} startingBalance={data.filters_applied.initial_balance} />
                  <View style={styles.split}>
                    <Text style={styles.splitText}>
                      Long <Text style={styles.splitNum}>{m.long_stats.trades}</Text> · Short <Text style={styles.splitNum}>{m.short_stats.trades}</Text>
                    </Text>
                  </View>
                </Card>

                <Card title="Period returns">
                  <View style={styles.periodGrid}>
                    <Period label="Avg daily" value={pr.avg_daily_pct} />
                    <Period label="This week" value={pr.weekly_pct} usd={pr.weekly_pnl} />
                    <Period label="This month" value={pr.monthly_pct} usd={pr.monthly_pnl} />
                    <Period label="Annualized" value={pr.annualized_pct} />
                  </View>
                  <Text style={styles.footnote}>Percentages are of the starting balance. Week and month are relative to today.</Text>
                </Card>

                <Card title="Net P&L by symbol">
                  <PnlBars
                    rows={data.symbol_breakdown.map((r) => ({
                      label: r.symbol,
                      value: r.net_profit,
                      sub: `${r.trades} trades · ${r.win_rate.toFixed(0)}% win`,
                    }))}
                  />
                </Card>

                <Card title="Net P&L by strategy tag">
                  <PnlBars
                    rows={data.tag_breakdown.map((r) => ({ label: r.setup_tag, value: r.net_profit, sub: `${r.trades} trades` }))}
                  />
                </Card>

                <Card title="Long vs short">
                  <View style={styles.periodGrid}>
                    <Direction label="Long" s={m.long_stats} />
                    <Direction label="Short" s={m.short_stats} />
                  </View>
                </Card>
              </>
            )}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

function Period({ label, value, usd }: { label: string; value: number; usd?: number }) {
  return (
    <View style={styles.periodCell}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.periodValue, { color: tone(value) }]}>{pct(value)}</Text>
      {usd != null ? <Text style={styles.tileSub}>{formatMoney(usd)}</Text> : null}
    </View>
  )
}

function Direction({ label, s }: { label: string; s: { trades: number; win_rate: number; pnl: number } }) {
  return (
    <View style={styles.periodCell}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.periodValue, { color: tone(s.pnl) }]}>{formatMoney(s.pnl)}</Text>
      <Text style={styles.tileSub}>
        {s.trades} trades · {s.win_rate.toFixed(1)}% win
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 2, gap: spacing.md },
  title: { color: colors.textPrimary, fontSize: 22, fontWeight: '700' },
  chipRow: { gap: spacing.sm, paddingRight: spacing.lg },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  chipTextOn: { color: colors.accent },
  balanceRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  balanceLabelWrap: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  balanceLabel: { color: colors.textSecondary, fontSize: 13 },
  autoTag: {
    color: colors.accent,
    fontSize: 9,
    fontWeight: '700',
    backgroundColor: 'rgba(240,185,11,0.12)',
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 3,
    overflow: 'hidden',
  },
  balanceInput: {
    minWidth: 120,
    textAlign: 'right',
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: 15,
    fontVariant: ['tabular-nums'],
  },
  balanceHint: { color: colors.textMuted, fontSize: 11, marginTop: -spacing.sm, textAlign: 'right', minHeight: 14 },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  tile: {
    width: '48.5%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  tileLabel: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6 },
  tileValue: { color: colors.textPrimary, fontSize: 20, fontWeight: '700', marginTop: 4, fontVariant: ['tabular-nums'] },
  tileSub: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  cardTitle: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  muted: { color: colors.textMuted, fontSize: 13 },
  split: { marginTop: spacing.xs },
  splitText: { color: colors.textMuted, fontSize: 12 },
  splitNum: { color: colors.textPrimary, fontWeight: '700' },
  periodGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  periodCell: {
    width: '48.5%',
    flexGrow: 1,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  periodValue: { fontSize: 17, fontWeight: '700', marginTop: 2, fontVariant: ['tabular-nums'] },
  footnote: { color: colors.textMuted, fontSize: 11 },
  errorBox: { alignItems: 'center', gap: spacing.md, marginTop: spacing.xl },
  errorText: { color: colors.negative, textAlign: 'center' },
  retry: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  retryText: { color: colors.accent, fontWeight: '600' },
  stale: { color: colors.warning, fontSize: 12 },
})
