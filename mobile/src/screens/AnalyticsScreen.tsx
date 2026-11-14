import AsyncStorage from '@react-native-async-storage/async-storage'
import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { saveInitialBalance } from '../api/analytics'
import { useAnalytics } from '../analytics/useAnalytics'
import { describeAccount } from '../accountLabel'
import { EquityChart } from '../components/analytics/EquityChart'
import { MonthCalendar } from '../components/analytics/MonthCalendar'
import { PnlBars } from '../components/analytics/PnlBars'
import { ConnectionBanner } from '../components/ConnectionBanner'
import { Text, TextInput } from '../components/Text'
import { Button, Card, Chip, ChipRow, Empty, Figures, Loading, MoreDetails, Notice, ScreenHeader, Seg, Stat, ui } from '../components/ui'
import { formatMoney } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, pnlColor, spacing, type } from '../theme'
import type { AnalyticsQuery } from '../types/analytics'

const ACCOUNT_KEY = 'tl.analytics.account'

type RangeKey = '7d' | '30d' | 'month' | '90d' | 'all'
const RANGES: { key: RangeKey; label: string }[] = [
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
  { key: 'month', label: 'Month' },
  { key: '90d', label: '90d' },
  { key: 'all', label: 'All' },
]

const pad = (n: number) => String(n).padStart(2, '0')
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

/** Start date (local, YYYY-MM-DD) for a range; undefined = from the first trade. */
function rangeStart(key: RangeKey): string | undefined {
  const now = new Date()
  if (key === 'all') return undefined
  if (key === 'month') return isoDay(new Date(now.getFullYear(), now.getMonth(), 1))
  const back = key === '7d' ? 6 : key === '30d' ? 29 : 89
  return isoDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - back))
}

const tone = (v: number) => pnlColor(v, colors.textPrimary)

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

export function AnalyticsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [account, setAccount] = useState<string | undefined>(undefined)
  const [range, setRange] = useState<RangeKey>('all')
  const [balance, setBalance] = useState(10000)
  const [balanceText, setBalanceText] = useState('10000')
  const [autoFilled, setAutoFilled] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [moreOpen, setMoreOpen] = useState(false)

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

  // Remembers the account you last picked here — same "sticks across visits" behaviour the web app's
  // Analytics page has. The very first time (nothing stored yet), prefer Capital.com over "All accounts";
  // failing that, a single linked account (so the starting balance can be saved, which is per account).
  // Once you've explicitly picked anything (including "All accounts" again later), that sticks instead.
  const appliedDefault = useRef(false)
  useEffect(() => {
    if (appliedDefault.current || !data || data.available.accounts.length === 0) return
    appliedDefault.current = true
    AsyncStorage.getItem(ACCOUNT_KEY)
      .then((stored) => {
        if (stored != null) {
          if (stored !== 'ALL' && data.available.accounts.includes(stored)) setAccount(stored)
          return
        }
        const capital = data.available.accounts.find((a) => describeAccount(a).platform === 'Capital.com')
        if (capital) setAccount(capital)
        else if (data.available.accounts.length === 1) setAccount(data.available.accounts[0])
      })
      .catch(() => {})
  }, [data])

  function pickAccount(a: string | undefined) {
    setAccount(a)
    AsyncStorage.setItem(ACCOUNT_KEY, a ?? 'ALL').catch(() => {
      /* the choice just won't stick */
    })
  }

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

  const balanceHint =
    noAccount && accounts.length > 1
      ? 'Pick one account above to save a balance for it.'
      : saveState === 'saving'
        ? 'Saving…'
        : saveState === 'saved'
          ? `Saved for ${describeAccount(account).label}.`
          : saveState === 'error'
            ? 'Couldn’t save. Check your connection and type it again.'
            : autoFilled
              ? 'Filled in for you from your first trades. Change it if it is wrong.'
              : 'What the account held before the first trade shown. Percentages are measured against it.'

  return (
    <SafeAreaView style={ui.screen} edges={['top']}>
      <ScreenHeader eyebrow="Review" title="Analytics" />
      <ScrollView
        contentContainerStyle={ui.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing && !!data} onRefresh={refresh} tintColor={colors.accent} colors={[colors.accent]} />}
      >
        <ConnectionBanner />
        <Seg options={RANGES} value={range} onChange={setRange} />

        {accounts.length > 1 ? (
          <ChipRow>
            <Chip label="All accounts" on={noAccount} onPress={() => pickAccount(undefined)} />
            {accounts.map((a) => (
              <Chip key={a} label={describeAccount(a).label} on={account === a} onPress={() => pickAccount(a)} />
            ))}
          </ChipRow>
        ) : null}

        {loading && !data ? (
          <Loading />
        ) : error && !data ? (
          <Empty icon="cloud-offline-outline" title="Couldn't load your numbers" text={error}>
            <Button label="Try again" kind="secondary" size="sm" onPress={refresh} />
          </Empty>
        ) : data && m && pr ? (
          <>
            {error ? <Notice tone="warn">Showing the last good numbers. The refresh failed.</Notice> : null}
            {data.matched_trades === 0 ? (
              <Empty icon="stats-chart-outline" title="No closed trades here" text="Nothing matches this account and range. Try another account or a longer range." />
            ) : (
              <>
                {/* results first: the answer, then the four numbers that explain it, expert detail behind a toggle */}
                <Card feature flush>
                  <View style={styles.heroBlock}>
                    <Text style={styles.heroLabel}>{data.official_balance != null ? 'Balance · from your broker' : 'Balance · estimated'}</Text>
                    <Text style={styles.hero} numberOfLines={1} adjustsFontSizeToFit>
                      {formatMoney(data.official_balance ?? m.final_balance, false)}
                    </Text>
                    <Text style={ui.muted}>
                      <Text style={[styles.heroDelta, { color: tone(m.total_net_pnl) }]}>
                        {formatMoney(m.total_net_pnl)} ({pct(m.gain_pct)})
                      </Text>
                      {'  '}over {m.total_trades} trades
                    </Text>
                  </View>
                  <Figures style={styles.topRule}>
                    <Stat label="Win rate" value={`${m.win_rate.toFixed(1)}%`} sub={`${m.winning_trades} won · ${m.losing_trades} lost`} />
                    <Stat label="Avg per trade" value={formatMoney(m.expectancy)} color={tone(m.expectancy)} sub={`win ${formatMoney(m.avg_win, false)} · loss ${formatMoney(Math.abs(m.avg_loss), false)}`} />
                    <Stat label="Profit factor" value={m.profit_factor.toFixed(2)} sub={m.profit_factor >= 1 ? 'wins outweigh losses' : 'losses outweigh wins'} />
                    <Stat
                      label="Biggest drop"
                      value={`${m.max_drawdown_pct.toFixed(1)}%`}
                      color={m.max_drawdown_pct >= 10 ? colors.negative : m.max_drawdown_pct >= 5 ? colors.warning : undefined}
                      sub={`${formatMoney(m.max_drawdown_usd, false)} from the peak`}
                    />
                  </Figures>
                  <MoreDetails open={moreOpen} onToggle={() => setMoreOpen((o) => !o)} hint="best & worst trade, holding time, SQN">
                    <Figures style={styles.topRule}>
                      <Stat small label="Best trade" value={formatMoney(m.best_trade)} color={tone(m.best_trade)} />
                      <Stat small label="Worst trade" value={formatMoney(m.worst_trade)} color={tone(m.worst_trade)} />
                      <Stat small label="Avg holding time" value={holdTime(m.avg_duration_minutes)} sub="per closed trade" />
                      <Stat small label="Win / loss size" value={m.win_loss_ratio.toFixed(2)} sub="avg win ÷ avg loss" />
                      <Stat small label="Won / lost in total" value={`${formatMoney(m.total_gross_profit, false)} / ${formatMoney(m.total_gross_loss, false)}`} />
                      <Stat small label="SQN" value={m.sqn.toFixed(2)} sub={m.sqn > 2.5 ? 'excellent' : m.sqn > 1.5 ? 'good' : m.sqn > 0 ? 'average' : 'losing so far'} />
                    </Figures>
                  </MoreDetails>
                </Card>

                <Card title="Calendar" right="tap a day">
                  <MonthCalendar key={`${account ?? 'ALL'}:${range}`} daily={data.daily_pnl} onDayPress={(date) => navigation.navigate('DayTrades', { date, account })} />
                </Card>

                <Card title="Balance over time" right={`${data.equity_curve.length} points${data.equity_curve_sampled ? ' · sampled' : ''}`}>
                  <EquityChart points={data.equity_curve} startingBalance={data.filters_applied.initial_balance} />
                </Card>

                <Card title="Returns" flush>
                  <Figures>
                    <Period label="This week" value={pr.weekly_pct} usd={pr.weekly_pnl} />
                    <Period label="This month" value={pr.monthly_pct} usd={pr.monthly_pnl} />
                    <Period label="Average day" value={pr.avg_daily_pct} />
                    <Period label="Yearly pace" value={pr.annualized_pct} />
                  </Figures>
                  <Text style={styles.cardNote}>Percentages are of the starting balance. Week and month count back from today.</Text>
                </Card>

                <Card title="By market">
                  <PnlBars
                    rows={data.symbol_breakdown.map((r) => ({
                      label: r.symbol,
                      value: r.net_profit,
                      sub: `${r.trades} trades · ${r.win_rate.toFixed(0)}% win`,
                    }))}
                  />
                </Card>

                <Card title="By label">
                  <PnlBars rows={data.tag_breakdown.map((r) => ({ label: r.setup_tag, value: r.net_profit, sub: `${r.trades} trades` }))} />
                </Card>

                <Card title="Buying vs selling" flush>
                  <Figures>
                    <Direction label="Long (buy)" s={m.long_stats} />
                    <Direction label="Short (sell)" s={m.short_stats} />
                  </Figures>
                </Card>
              </>
            )}
          </>
        ) : null}

        {/* settings after results */}
        <Card title="Starting balance" right={autoFilled ? 'auto' : undefined}>
          <View style={ui.rowBetween}>
            <Text style={[ui.muted, { flex: 1 }]}>{balanceHint}</Text>
            <TextInput
              value={balanceText}
              onChangeText={onBalanceChange}
              keyboardType="decimal-pad"
              style={[ui.input, styles.balanceInput]}
              placeholderTextColor={colors.textMuted}
              selectTextOnFocus
              accessibilityLabel="Starting balance in dollars"
            />
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  )
}

function Period({ label, value, usd }: { label: string; value: number; usd?: number }) {
  return <Stat small label={label} value={pct(value)} color={tone(value)} sub={usd != null ? formatMoney(usd) : undefined} />
}

function Direction({ label, s }: { label: string; s: { trades: number; win_rate: number; pnl: number } }) {
  return <Stat small label={label} value={formatMoney(s.pnl)} color={tone(s.pnl)} sub={`${s.trades} trades · ${s.win_rate.toFixed(1)}% win`} />
}

const styles = StyleSheet.create({
  heroBlock: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.md, gap: 2 },
  heroLabel: { ...type.label },
  hero: { ...type.hero },
  heroDelta: { ...type.num, fontSize: 13 },
  topRule: { borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  cardNote: { ...type.small, fontSize: 11, lineHeight: 15, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  balanceInput: { minWidth: 120, textAlign: 'right', fontVariant: ['tabular-nums'] },
})
