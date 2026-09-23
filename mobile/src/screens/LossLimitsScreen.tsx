import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useRef, useState } from 'react'
import { ActivityIndicator, KeyboardAvoidingView, Platform, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { clearLossLimits, getLossLimits, saveLossLimits } from '../api/lossLimits'
import { Bar, Button, Card, Field, Pill, parseNum } from '../components/ui'
import { formatMoney } from '../format'
import { describeAccount } from '../accountLabel'
import { colors, spacing } from '../theme'
import type { LossLimitStatus } from '../types/lossLimits'

const money = (v: number) => formatMoney(v, false)

function stateOf(ratio: number | null, warnPct: number): { text: string; color: string } | null {
  if (ratio == null) return null
  if (ratio >= 1) return { text: 'LIMIT REACHED', color: colors.negative }
  if (ratio >= warnPct / 100) return { text: 'CLOSE TO LIMIT', color: colors.warning }
  return { text: 'OK', color: colors.positive }
}

function AccountCard({ s, warnPct, onChanged }: { s: LossLimitStatus; warnPct: number; onChanged: () => void }) {
  const [daily, setDaily] = useState(s.daily_loss_limit != null ? String(s.daily_loss_limit) : '')
  const [dd, setDd] = useState(s.drawdown_limit_pct != null ? String(s.drawdown_limit_pct) : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const hasLimits = s.daily_loss_limit != null || s.drawdown_limit_pct != null

  async function save() {
    setError(null)
    setSaved(false)
    const d = parseNum(daily)
    const p = parseNum(dd)
    if (Number.isNaN(d) || (d != null && d <= 0)) return setError('Daily loss limit must be a positive amount, or empty for none.')
    if (Number.isNaN(p) || (p != null && (p <= 0 || p >= 100))) return setError('Drawdown limit must be a percentage between 0 and 100, or empty for none.')
    setBusy(true)
    try {
      await saveLossLimits(s.account_id, { daily_loss: d, drawdown_pct: p })
      setSaved(true)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the limits.')
    } finally {
      setBusy(false)
    }
  }

  async function clear() {
    setBusy(true)
    setError(null)
    try {
      await clearLossLimits(s.account_id)
      setDaily('')
      setDd('')
      setSaved(false)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not clear the limits.')
    } finally {
      setBusy(false)
    }
  }

  const dailyState = stateOf(s.daily_ratio, warnPct)
  const ddState = stateOf(s.drawdown_ratio, warnPct)

  return (
    <Card title={describeAccount(s.account_id).label}>
      {s.daily_loss_limit != null ? (
        <View style={styles.block}>
          <View style={styles.blockHead}>
            <Text style={styles.body}>
              Today {s.today_loss > 0 ? `down ${money(s.today_loss)}` : s.today_net_pnl > 0 ? `up ${money(s.today_net_pnl)}` : 'flat'} of {money(s.daily_loss_limit)}
            </Text>
            {dailyState ? <Pill text={dailyState.text} color={dailyState.color} /> : null}
          </View>
          <Bar ratio={s.daily_ratio} warnAt={warnPct / 100} />
        </View>
      ) : null}
      {s.drawdown_limit_pct != null ? (
        <View style={styles.block}>
          {s.drawdown_pct != null ? (
            <>
              <View style={styles.blockHead}>
                <Text style={styles.body}>
                  {s.drawdown_pct.toFixed(1)}% below peak of {s.drawdown_limit_pct}% limit
                </Text>
                {ddState ? <Pill text={ddState.text} color={ddState.color} /> : null}
              </View>
              <Bar ratio={s.drawdown_ratio} warnAt={warnPct / 100} />
              <Text style={styles.muted}>
                Peak {money(s.peak_balance ?? 0)} · now {money(s.current_balance ?? 0)}
                {s.starting_balance_source === 'broker' ? ' · start worked out from your broker balance' : ''}
              </Text>
            </>
          ) : (
            <Text style={styles.warn}>
              Drawdown needs a starting balance for this account. Open Analytics, pick {s.account_id} and enter its starting balance, then it works.
            </Text>
          )}
        </View>
      ) : null}
      {!hasLimits ? <Text style={styles.muted}>No limits set for this account. Today: {formatMoney(s.today_net_pnl)}.</Text> : null}

      <View style={styles.row}>
        <Field half label="Daily loss limit ($)" value={daily} onChangeText={setDaily} keyboardType="decimal-pad" placeholder="none" />
        <Field half label="Drawdown limit (%)" value={dd} onChangeText={setDd} keyboardType="decimal-pad" placeholder="none" />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {saved ? <Text style={styles.ok}>Saved. You'll be notified at {warnPct}% and at 100% of each limit.</Text> : null}
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Button label="Save limits" busy={busy} onPress={() => void save()} />
        </View>
        {hasLimits ? (
          <View style={{ flex: 1 }}>
            <Button label="Clear" kind="secondary" disabled={busy} onPress={() => void clear()} />
          </View>
        ) : null}
      </View>
    </Card>
  )
}

/** Loss limits: a daily-loss limit and a drawdown limit per account, with a notification when you get close or hit them. */
export function LossLimitsScreen() {
  const [accounts, setAccounts] = useState<LossLimitStatus[] | null>(null)
  const [warnPct, setWarnPct] = useState(80)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const res = await getLossLimits(controller.signal)
      if (controller.signal.aborted) return
      setAccounts(res.accounts)
      setWarnPct(res.warn_at_pct)
      setNote(res.note)
      setError(null)
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load your limits.')
    } finally {
      if (!controller.signal.aborted) setRefreshing(false)
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load()
      return () => inFlight.current?.abort()
    }, [load]),
  )

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} />}
        >
          <Text style={styles.intro}>
            Set how much you are willing to lose in a day, and how far an account may fall from its peak. You get a notification on this phone and your desktop when a closed trade takes you to {warnPct}% of a limit, and again when you reach it. It only tells you — it never closes or blocks a trade.
          </Text>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {accounts == null && !error ? <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} /> : null}
          {accounts && accounts.length === 0 ? <Text style={styles.muted}>No accounts yet. Once you have trades (synced or logged by hand) they appear here.</Text> : null}
          {accounts?.map((a) => (
            <AccountCard key={a.account_id} s={a} warnPct={warnPct} onChanged={() => void load()} />
          ))}
          {note ? <Text style={styles.muted}>{note}</Text> : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  intro: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 20, flexShrink: 1 },
  muted: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  warn: { color: colors.warning, fontSize: 12, lineHeight: 17 },
  error: { color: colors.negative, fontSize: 13 },
  ok: { color: colors.positive, fontSize: 13 },
  block: { gap: 6 },
  blockHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.md },
})
