import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { advanceChallenge, deleteChallengeConfig, getChallengeStatus, resetChallenge, saveChallengeConfig } from '../api/challenge'
import { Bar, Button, Card, Field, parseNum } from '../components/ui'
import { useJournal } from '../journal/JournalContext'
import { colors, radius, spacing } from '../theme'
import type { ChallengeConfig, ChallengeDrawdownMode, ChallengeStatus } from '../types/challenge'

const money = (v: number | null | undefined) =>
  v == null ? '—' : `${v < 0 ? '-' : ''}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const PHASE_LABEL = { '1': 'Phase 1', '2': 'Phase 2', funded: 'Funded' } as const

interface Form {
  size: string
  firm: string
  p1: string
  p2: string
  dd: string
  daily: string
  days: string
  thresh: string
  mode: ChallengeDrawdownMode
}

const DEFAULT_FORM: Form = { size: '5000', firm: '5ers', p1: '10', p2: '5', dd: '10', daily: '5', days: '3', thresh: '0.5', mode: 'trailing' }

const formFrom = (c: ChallengeConfig): Form => ({
  size: String(c.account_size),
  firm: c.firm,
  p1: String(c.phase1_target_pct),
  p2: String(c.phase2_target_pct),
  dd: String(c.max_drawdown_pct),
  daily: String(c.daily_loss_pct),
  days: String(c.min_profit_days),
  thresh: String(c.profit_day_threshold_pct),
  mode: c.drawdown_mode,
})

/** Prop-firm challenge tracker: phase progress, drawdown budget, daily-loss budget and profit days for one account. */
export function ChallengeScreen() {
  const { data: journal } = useJournal()
  const accounts = journal?.accounts ?? []
  const [account, setAccount] = useState('')
  const [status, setStatus] = useState<ChallengeStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Form>(DEFAULT_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [acting, setActing] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!account && accounts.length > 0) setAccount(accounts[0])
  }, [accounts, account])

  const load = useCallback(
    async (acct: string) => {
      if (!acct) return
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      setLoading(true)
      try {
        const res = await getChallengeStatus(acct, controller.signal)
        if (controller.signal.aborted) return
        setStatus(res)
        setError(null)
        setForm(res.config ? formFrom(res.config) : DEFAULT_FORM)
        setEditing(!res.configured)
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load the tracker.')
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [],
  )

  useFocusEffect(
    useCallback(() => {
      void load(account)
      return () => inFlight.current?.abort()
    }, [load, account]),
  )

  const set = (k: keyof Form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function save() {
    setFormError(null)
    const size = parseNum(form.size)
    const p1 = parseNum(form.p1)
    const p2 = parseNum(form.p2)
    const dd = parseNum(form.dd)
    const daily = parseNum(form.daily)
    const days = parseNum(form.days)
    const thresh = parseNum(form.thresh)
    if (size == null || !(size > 0)) return setFormError('Account size must be a number above 0.')
    for (const [name, v] of [['Phase 1 target', p1], ['Phase 2 target', p2], ['Max drawdown', dd], ['Daily loss', daily], ['Profit-day threshold', thresh]] as const) {
      if (v == null || !(v > 0) || v > 100) return setFormError(`${name} must be a percentage between 0 and 100.`)
    }
    if (days == null || days < 0 || days > 30 || !Number.isInteger(days)) return setFormError('Minimum profit days must be a whole number from 0 to 30.')
    setSaving(true)
    try {
      const res = await saveChallengeConfig({
        account_id: account,
        firm: form.firm.trim() || '5ers',
        account_size: size,
        phase1_target_pct: p1 as number,
        phase2_target_pct: p2 as number,
        max_drawdown_pct: dd as number,
        daily_loss_pct: daily as number,
        min_profit_days: days,
        profit_day_threshold_pct: thresh as number,
        drawdown_mode: form.mode,
      })
      setStatus(res)
      setEditing(false)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not save the rules.')
    } finally {
      setSaving(false)
    }
  }

  function confirm(title: string, message: string, action: string, run: () => Promise<unknown>, destructive = false) {
    Alert.alert(title, message, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: action,
        style: destructive ? 'destructive' : 'default',
        onPress: async () => {
          setActing(true)
          setError(null)
          try {
            await run()
            await load(account)
          } catch (err) {
            setError(err instanceof Error ? err.message : 'That did not work.')
          } finally {
            setActing(false)
          }
        },
      },
    ])
  }

  const phase = status?.phase
  const cfg = status?.config

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(account) }} tintColor={colors.accent} />}
        >
          <Text style={styles.intro}>
            Track a prop-firm challenge: progress to the profit target, how much drawdown and daily loss you have used, and profit days. Numbers are estimated from your synced balance and closed trades — check your firm's own dashboard before any real risk decision.
          </Text>

          {accounts.length === 0 ? (
            <Text style={styles.muted}>No accounts yet. Sync a broker or log a trade first, then pick it here.</Text>
          ) : (
            <View style={styles.chips}>
              {accounts.map((a) => (
                <Pressable key={a} onPress={() => { if (a !== account) { setStatus(null); setEditing(false); setAccount(a) } }} style={[styles.chip, account === a && styles.chipOn]} accessibilityRole="button">
                  <Text style={[styles.chipText, account === a && styles.chipTextOn]}>{a}</Text>
                </Pressable>
              ))}
            </View>
          )}

          {error ? <Text style={styles.error}>{error}</Text> : null}
          {loading && !status ? <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.lg }} /> : null}

          {status && status.configured && cfg && !editing ? (
            <>
              <Card title={`${cfg.firm} · ${money(cfg.account_size)}`} right={`since ${cfg.phase_start_date}`}>
                <View style={styles.rowBetween}>
                  <Text style={styles.big}>{phase ? PHASE_LABEL[phase] : '—'}</Text>
                  <Text style={styles.big}>{money(status.current_balance)}</Text>
                </View>
                {status.phase_target_pct != null ? (
                  <>
                    <Bar ratio={status.phase_progress_ratio} warnAt={2} />
                    <Text style={styles.body}>
                      {status.phase_progress_pct?.toFixed(2)}% of the {status.phase_target_pct}% target · {money(status.phase_gain_amount)} of {money(status.phase_target_amount)}
                    </Text>
                  </>
                ) : (
                  <Text style={styles.body}>Funded — no profit target. Keep inside the drawdown and daily-loss rules.</Text>
                )}
              </Card>

              <Card title={`Drawdown · ${status.drawdown_mode}`}>
                <Bar ratio={status.drawdown_budget_used_ratio} />
                <Text style={styles.body}>
                  {status.drawdown_used_pct?.toFixed(2)}% used of {cfg.max_drawdown_pct}% allowed
                </Text>
                <Text style={styles.muted}>
                  Peak {money(status.peak_balance)} · your floor is {money(status.drawdown_floor_balance)}
                </Text>
              </Card>

              <Card title="Daily loss today">
                <Bar ratio={status.daily_loss_budget_used_ratio} />
                <Text style={styles.body}>
                  {status.daily_loss_used_pct?.toFixed(2)}% used of {cfg.daily_loss_pct}% allowed · today {money(status.daily_loss_today_amount)}
                </Text>
              </Card>

              <Card title="Profit days">
                <Text style={styles.body}>
                  {status.profit_days_count} of {status.min_profit_days} needed
                </Text>
                <Bar ratio={status.min_profit_days ? (status.profit_days_count ?? 0) / status.min_profit_days : 1} warnAt={2} />
                <Text style={styles.muted}>
                  A profit day is a day up by at least {cfg.profit_day_threshold_pct}% of the account size.
                  {status.profit_day_dates.length > 0 ? ` So far: ${status.profit_day_dates.join(', ')}.` : ''}
                </Text>
              </Card>

              <Text style={styles.disclaimer}>{status.disclaimer}</Text>

              <Card title="Manage">
                <Button label="Edit the rules" kind="secondary" disabled={acting} onPress={() => setEditing(true)} />
                {phase === '1' ? (
                  <Button
                    label="Mark Phase 1 passed"
                    disabled={acting}
                    onPress={() => confirm('Phase 1 passed?', 'Moves you to Phase 2. Your current balance becomes its starting point.', 'Move to Phase 2', () => advanceChallenge(account, '2'))}
                  />
                ) : null}
                {phase === '2' ? (
                  <Button
                    label="Mark Phase 2 passed"
                    disabled={acting}
                    onPress={() => confirm('Phase 2 passed?', 'Moves you to Funded. Your current balance becomes its starting point.', 'Move to Funded', () => advanceChallenge(account, 'funded'))}
                  />
                ) : null}
                <Button
                  label="Restart from Phase 1"
                  kind="secondary"
                  disabled={acting}
                  onPress={() => confirm('Restart the challenge?', 'Goes back to Phase 1 at the configured account size, as after buying a new evaluation. Your trades are not touched.', 'Restart', () => resetChallenge(account), true)}
                />
                <Button
                  label="Stop tracking this account"
                  kind="danger"
                  disabled={acting}
                  onPress={() => confirm('Stop tracking?', 'Removes the challenge rules and progress for this account. Your trades are not touched.', 'Remove', () => deleteChallengeConfig(account), true)}
                />
              </Card>
            </>
          ) : null}

          {status && editing ? (
            <Card title={status.configured ? 'Edit the rules' : `Start tracking ${account}`}>
              <Text style={styles.muted}>Defaults match a 5ers $5K High Stakes challenge. Change any number to fit your firm.</Text>
              <View style={styles.row}>
                <Field half label="Account size ($)" value={form.size} onChangeText={set('size')} keyboardType="decimal-pad" />
                <Field half label="Firm" value={form.firm} onChangeText={set('firm')} autoCapitalize="sentences" />
              </View>
              <View style={styles.row}>
                <Field half label="Phase 1 target (%)" value={form.p1} onChangeText={set('p1')} keyboardType="decimal-pad" />
                <Field half label="Phase 2 target (%)" value={form.p2} onChangeText={set('p2')} keyboardType="decimal-pad" />
              </View>
              <View style={styles.row}>
                <Field half label="Max drawdown (%)" value={form.dd} onChangeText={set('dd')} keyboardType="decimal-pad" />
                <Field half label="Daily loss (%)" value={form.daily} onChangeText={set('daily')} keyboardType="decimal-pad" />
              </View>
              <View style={styles.row}>
                <Field half label="Min profit days" value={form.days} onChangeText={set('days')} keyboardType="number-pad" />
                <Field half label="Profit-day threshold (%)" value={form.thresh} onChangeText={set('thresh')} keyboardType="decimal-pad" />
              </View>
              <Text style={styles.label}>Drawdown counted from</Text>
              <View style={styles.row}>
                {(['trailing', 'static'] as const).map((m) => (
                  <Pressable key={m} onPress={() => setForm((f) => ({ ...f, mode: m }))} style={[styles.mode, form.mode === m && styles.modeOn]} accessibilityRole="button" accessibilityState={{ selected: form.mode === m }}>
                    <Text style={[styles.modeText, form.mode === m && { color: colors.accent }]}>{m === 'trailing' ? 'Trailing (from the peak)' : 'Static (from the start)'}</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={styles.muted}>Firms don't always say which one they use — trailing is the cautious choice.</Text>
              {formError ? <Text style={styles.error}>{formError}</Text> : null}
              <Button label={status.configured ? 'Save rules' : 'Start tracking'} busy={saving} onPress={() => void save()} />
              {status.configured ? <Button label="Cancel" kind="secondary" disabled={saving} onPress={() => { setEditing(false); setFormError(null); if (status.config) setForm(formFrom(status.config)) }} /> : null}
            </Card>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  intro: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  muted: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  big: { color: colors.textPrimary, fontSize: 20, fontWeight: '700', fontVariant: ['tabular-nums'] },
  error: { color: colors.negative, fontSize: 13 },
  disclaimer: { color: colors.textMuted, fontSize: 11, lineHeight: 16, textAlign: 'center' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  row: { flexDirection: 'row', gap: spacing.md },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  chipOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  chipText: { color: colors.textSecondary, fontSize: 12 },
  chipTextOn: { color: colors.accent },
  label: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6 },
  mode: { flex: 1, alignItems: 'center', paddingVertical: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.sm },
  modeOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  modeText: { color: colors.textSecondary, fontSize: 12, fontWeight: '600', textAlign: 'center' },
})
