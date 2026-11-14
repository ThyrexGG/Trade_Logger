import { DateTimePickerAndroid } from '@react-native-community/datetimepicker'
import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Alert, KeyboardAvoidingView, Platform, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { advanceChallenge, deleteChallengeConfig, getChallengeStatus, resetChallenge, saveChallengeConfig } from '../api/challenge'
import { describeAccount } from '../accountLabel'
import { Text, TextInput } from '../components/Text'
import { Bar, Button, Card, Chip, ChipRow, Empty, Field, Footnote, Loading, Notice, parseNum, Pill, Seg, ui } from '../components/ui'
import { useJournal } from '../journal/JournalContext'
import { colors, radius, spacing, type } from '../theme'
import type { ChallengeConfig, ChallengeDrawdownMode, ChallengeStatus } from '../types/challenge'

const money = (v: number | null | undefined) =>
  v == null ? '—' : `${v < 0 ? '-' : ''}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const PHASE_LABEL = { '1': 'Phase 1', '2': 'Phase 2', funded: 'Funded' } as const
const MODES: { key: ChallengeDrawdownMode; label: string }[] = [
  { key: 'trailing', label: 'From the peak' },
  { key: 'static', label: 'From the start' },
]
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/
const pad = (n: number) => String(n).padStart(2, '0')
/** the phone's own calendar day, never the UTC one (days are local days) */
const localIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
/** "2026-10-27" -> "Oct 27, 2026" */
const shortDay = (iso: string | null | undefined) =>
  iso && ISO_DAY.test(iso.slice(0, 10)) ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

interface Form {
  size: string
  firm: string
  p1: string
  p2: string
  dd: string
  daily: string
  days: string
  thresh: string
  consistency: string
  /** YYYY-MM-DD, or '' to leave the start where it is */
  start: string
  mode: ChallengeDrawdownMode
}

const DEFAULT_FORM: Form = { size: '5000', firm: '5ers', p1: '10', p2: '5', dd: '10', daily: '5', days: '3', thresh: '0.5', consistency: '40', start: '', mode: 'trailing' }

const formFrom = (c: ChallengeConfig): Form => ({
  size: String(c.account_size),
  firm: c.firm,
  p1: String(c.phase1_target_pct),
  p2: String(c.phase2_target_pct),
  dd: String(c.max_drawdown_pct),
  daily: String(c.daily_loss_pct),
  days: String(c.min_profit_days),
  thresh: String(c.profit_day_threshold_pct),
  consistency: String(c.consistency_pct ?? 40),
  start: (c.phase_start_date ?? '').slice(0, 10),
  mode: c.drawdown_mode,
})

/** One budget: a label, how much is used in words, the bar, and one plain line. */
function Budget({ title, used, ratio, warnAt, children }: { title: string; used: string; ratio: number | null | undefined; warnAt?: number; children?: ReactNode }) {
  return (
    <View style={styles.budget}>
      <View style={ui.rowBetween}>
        <Text style={styles.budgetTitle}>{title}</Text>
        <Text style={ui.num}>{used}</Text>
      </View>
      <Bar ratio={ratio} warnAt={warnAt} />
      {children ? <Text style={ui.muted}>{children}</Text> : null}
    </View>
  )
}

/** Would you pass a "your best day may be at most N% of your profit" rule? Same wording as the web app's meter. */
function Consistency({ s, onSetLimit }: { s: ChallengeStatus; onSetLimit: () => void }) {
  const status = s.consistency_status
  if (!status) return null // an older server that does not send it
  const share = s.consistency_best_day_pct
  const limit = s.consistency_limit_pct
  const fill = Math.min(100, Math.max(0, share ?? 0))
  const since = shortDay(s.config?.phase_start_date)
  const verdict =
    status === 'pass'
      ? { text: 'Would pass', color: colors.positive }
      : status === 'fail'
        ? { text: 'Would fail', color: colors.negative }
        : { text: status === 'no_profit' ? 'No profit yet' : 'No limit set', color: colors.textSecondary }
  const best = s.consistency_best_day_amount
  const cap = s.consistency_cap_at_target
  return (
    <Card title="Consistency rule" action={<Pill text={verdict.text} color={verdict.color} />}>
      <Text style={ui.muted}>Your best single day compared with your total profit.</Text>
      <View style={styles.meter}>
        <View style={[styles.meterFill, { width: `${fill}%`, backgroundColor: status === 'pass' ? colors.positive : status === 'fail' ? colors.negative : colors.textMuted }]} />
        {limit != null ? <View style={[styles.meterTick, { left: `${Math.min(100, limit)}%` }]} /> : null}
      </View>
      <Text style={ui.sub}>
        {status === 'no_profit'
          ? `You are ${money(s.consistency_total_profit)} net since ${since}. The rule compares your best day with your total profit, so it starts once you are net up.`
          : share == null
            ? 'No winning day yet.'
            : `Best day ${money(best)} (${shortDay(s.consistency_best_day_date)}) is ${share.toFixed(1)}% of your ${money(s.consistency_total_profit)} profit since ${since}${limit != null ? `. Limit ${limit}%` : ''}.`}
      </Text>
      {status === 'fail' && s.consistency_extra_needed != null ? (
        <Text style={ui.sub}>
          To pass you need about {money(s.consistency_extra_needed)} more profit from other days, without a new day bigger than {money(best)}.
        </Text>
      ) : null}
      {status === 'pass' && s.consistency_next_day_max != null ? <Text style={ui.sub}>Your next day can make up to {money(s.consistency_next_day_max)} and you would still pass.</Text> : null}
      {cap != null ? (
        <Text style={[ui.sub, (best ?? 0) > cap && { color: colors.negative }]}>
          At your {money(s.phase_target_amount)} target, one day can make at most {money(cap)}.{' '}
          {best != null ? `Your best day so far is ${money(best)}${best > cap ? ', already over, so you would need more profit than the target to pass.' : ', inside it.'}` : 'You have no winning day yet.'}
        </Text>
      ) : null}
      {status === 'off' ? (
        <>
          <Text style={ui.muted}>Many prop firms cap how much of your profit one day can make. Set your firm's limit to see if you would pass.</Text>
          <Button label="Set the limit" kind="secondary" size="sm" onPress={onSetLimit} style={styles.selfStart} />
        </>
      ) : null}
    </Card>
  )
}

/** Prop-firm challenge tracker: phase progress, drawdown budget, daily-loss budget, profit days and the consistency rule for one account. */
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

  const load = useCallback(async (acct: string) => {
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
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load(account)
      return () => inFlight.current?.abort()
    }, [load, account]),
  )

  const set = (k: keyof Form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  function pickStart() {
    if (Platform.OS !== 'android') return // elsewhere the date is typed into the field
    const current = ISO_DAY.test(form.start) ? new Date(`${form.start}T00:00:00`) : new Date()
    DateTimePickerAndroid.open({ value: current, mode: 'date', maximumDate: new Date(), onValueChange: (_e, picked) => setForm((f) => ({ ...f, start: localIso(picked) })) })
  }

  async function save() {
    setFormError(null)
    const size = parseNum(form.size)
    const p1 = parseNum(form.p1)
    const p2 = parseNum(form.p2)
    const dd = parseNum(form.dd)
    const daily = parseNum(form.daily)
    const days = parseNum(form.days)
    const thresh = parseNum(form.thresh)
    const consistency = parseNum(form.consistency)
    if (size == null || !(size > 0)) return setFormError('Account size must be a number above 0.')
    for (const [name, v] of [['Phase 1 target', p1], ['Phase 2 target', p2], ['Max drawdown', dd], ['Daily loss', daily], ['Profit-day threshold', thresh]] as const) {
      if (v == null || !(v > 0) || v > 100) return setFormError(`${name} must be a percentage between 0 and 100.`)
    }
    if (days == null || days < 0 || days > 30 || !Number.isInteger(days)) return setFormError('Minimum profit days must be a whole number from 0 to 30.')
    if (consistency != null && (Number.isNaN(consistency) || consistency < 0 || consistency > 100)) return setFormError('The consistency limit must be between 0 and 100. Use 0 if your firm has no such rule.')
    const start = form.start.trim()
    if (start && (!ISO_DAY.test(start) || Number.isNaN(new Date(`${start}T00:00:00`).getTime()))) return setFormError('The start date must look like 2026-10-27.')
    if (start && start > localIso(new Date())) return setFormError('The start date cannot be in the future.')
    // only send the start date when it was changed, so saving other rules never moves it
    const savedStart = (status?.config?.phase_start_date ?? '').slice(0, 10)
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
        ...(consistency != null ? { consistency_pct: consistency } : {}),
        ...(start && start !== savedStart ? { start_date: start } : {}),
      })
      setStatus(res)
      if (res.config) setForm(formFrom(res.config))
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
  const firstTrade = status?.first_trade_date ? status.first_trade_date.slice(0, 10) : null

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={ui.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(account) }} tintColor={colors.accent} colors={[colors.accent]} />}
        >
          {accounts.length === 0 ? (
            <Empty icon="trophy-outline" title="No accounts yet" text="Sync a broker or log a trade first, then pick the account here." />
          ) : accounts.length > 1 ? (
            <ChipRow>
              {accounts.map((a) => (
                <Chip
                  key={a}
                  label={describeAccount(a).label}
                  on={account === a}
                  onPress={() => {
                    if (a !== account) {
                      setStatus(null)
                      setEditing(false)
                      setAccount(a)
                    }
                  }}
                />
              ))}
            </ChipRow>
          ) : null}

          {error ? <Notice>{error}</Notice> : null}
          {loading && !status ? <Loading /> : null}

          {status && status.configured && cfg && !editing ? (
            <>
              <Card feature title={`${cfg.firm} · ${money(cfg.account_size)}`} right={`since ${shortDay(cfg.phase_start_date)}`}>
                <View style={ui.rowBetween}>
                  <View>
                    <Text style={styles.label}>{phase ? PHASE_LABEL[phase] : '—'}</Text>
                    <Text style={styles.big} numberOfLines={1} adjustsFontSizeToFit>
                      {money(status.current_balance)}
                    </Text>
                  </View>
                  {status.phase_target_pct != null ? (
                    <View style={styles.right}>
                      <Text style={styles.label}>To the target</Text>
                      <Text style={styles.mid}>{status.phase_progress_pct?.toFixed(1)}%</Text>
                    </View>
                  ) : null}
                </View>
                {status.phase_target_pct != null ? (
                  <>
                    <Bar ratio={status.phase_progress_ratio} warnAt={2} />
                    <Text style={ui.muted}>
                      {money(status.phase_gain_amount)} of the {money(status.phase_target_amount)} you need ({status.phase_target_pct}% of the account).
                    </Text>
                  </>
                ) : (
                  <Text style={ui.muted}>Funded: there is no profit target. Stay inside the drawdown and daily-loss rules.</Text>
                )}
              </Card>

              <Card title="Your limits">
                <Budget title="Daily loss today" used={`${status.daily_loss_used_pct?.toFixed(2)}% of ${cfg.daily_loss_pct}%`} ratio={status.daily_loss_budget_used_ratio}>
                  Today so far: {money(status.daily_loss_today_amount)}.
                </Budget>
                <View style={styles.rule} />
                <Budget title="Max drawdown" used={`${status.drawdown_used_pct?.toFixed(2)}% of ${cfg.max_drawdown_pct}%`} ratio={status.drawdown_budget_used_ratio}>
                  Counted {status.drawdown_mode === 'static' ? 'from the start' : 'from your peak'} ({money(status.peak_balance)}). Do not let the balance fall below {money(status.drawdown_floor_balance)}.
                </Budget>
                <View style={styles.rule} />
                <Budget
                  title="Profit days"
                  used={`${status.profit_days_count} of ${status.min_profit_days}`}
                  ratio={status.min_profit_days ? (status.profit_days_count ?? 0) / status.min_profit_days : 1}
                  warnAt={2}
                >
                  A profit day is a day up by at least {cfg.profit_day_threshold_pct}% of the account size.
                  {status.profit_day_dates.length > 0 ? ` So far: ${status.profit_day_dates.map(shortDay).join(', ')}.` : ''}
                </Budget>
              </Card>

              <Consistency s={status} onSetLimit={() => setEditing(true)} />

              <Card title="Manage">
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
                <Button label="Edit the rules" kind="secondary" disabled={acting} onPress={() => setEditing(true)} />
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

              <Footnote>{status.disclaimer}</Footnote>
            </>
          ) : null}

          {status && editing ? (
            <Card title={status.configured ? 'Edit the rules' : `Start tracking ${describeAccount(account).label}`}>
              <Text style={ui.muted}>These start as a 5ers $5K High Stakes challenge. Change any number to match your firm.</Text>
              <View style={ui.cols}>
                <Field half label="Account size ($)" value={form.size} onChangeText={set('size')} keyboardType="decimal-pad" />
                <Field half label="Firm" value={form.firm} onChangeText={set('firm')} autoCapitalize="sentences" />
              </View>
              <View style={ui.cols}>
                <Field half label="Phase 1 target (%)" value={form.p1} onChangeText={set('p1')} keyboardType="decimal-pad" />
                <Field half label="Phase 2 target (%)" value={form.p2} onChangeText={set('p2')} keyboardType="decimal-pad" />
              </View>
              <View style={ui.cols}>
                <Field half label="Max drawdown (%)" value={form.dd} onChangeText={set('dd')} keyboardType="decimal-pad" />
                <Field half label="Daily loss (%)" value={form.daily} onChangeText={set('daily')} keyboardType="decimal-pad" />
              </View>
              <View style={ui.cols}>
                <Field half label="Min profit days" value={form.days} onChangeText={set('days')} keyboardType="number-pad" />
                <Field half label="Profit day is (%)" value={form.thresh} onChangeText={set('thresh')} keyboardType="decimal-pad" />
              </View>
              <Field
                label="Consistency limit (%)"
                value={form.consistency}
                onChangeText={set('consistency')}
                keyboardType="decimal-pad"
                hint="The most of your total profit one day may make. Many firms use 40. Enter 0 if your firm has no such rule."
              />

              <View style={styles.field}>
                <Text style={ui.fieldLabel}>Count my trades from</Text>
                {Platform.OS === 'android' ? (
                  <Pressable onPress={pickStart} style={ui.input} accessibilityRole="button" accessibilityLabel={`Count my trades from ${form.start ? shortDay(form.start) : 'today'}`}>
                    <Text style={styles.dateText}>{form.start ? shortDay(form.start) : 'Today'}</Text>
                  </Pressable>
                ) : (
                  <TextInput value={form.start} onChangeText={set('start')} placeholder="2026-10-27" placeholderTextColor={colors.textMuted} autoCapitalize="none" autoCorrect={false} style={ui.input} />
                )}
                <Text style={styles.hint}>The day this account, or its current phase, started. Progress, profit days and the consistency rule count from here.</Text>
                {firstTrade && firstTrade !== form.start ? (
                  <Button label={`Use my first trade on this account (${shortDay(firstTrade)})`} kind="ghost" size="sm" onPress={() => setForm((f) => ({ ...f, start: firstTrade }))} style={styles.selfStart} />
                ) : null}
              </View>

              <View style={styles.field}>
                <Text style={ui.fieldLabel}>Drawdown is counted</Text>
                <Seg options={MODES} value={form.mode} onChange={(m) => setForm((f) => ({ ...f, mode: m }))} />
                <Text style={styles.hint}>Firms don't always say which one they use. From the peak is the cautious choice.</Text>
              </View>

              {formError ? <Notice>{formError}</Notice> : null}
              <Button label={status.configured ? 'Save rules' : 'Start tracking'} busy={saving} onPress={() => void save()} />
              {status.configured ? (
                <Button
                  label="Cancel"
                  kind="ghost"
                  disabled={saving}
                  onPress={() => {
                    setEditing(false)
                    setFormError(null)
                    if (status.config) setForm(formFrom(status.config))
                  }}
                />
              ) : null}
            </Card>
          ) : null}

          {!status || !status.configured ? (
            <Footnote>Numbers are estimated from your synced balance and closed trades. Check your firm's own dashboard before any real risk decision.</Footnote>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  label: { ...type.label },
  big: { ...type.hero, fontSize: 28, lineHeight: 34 },
  mid: { ...type.figure, textAlign: 'right' },
  right: { alignItems: 'flex-end' },
  budget: { gap: spacing.sm },
  budgetTitle: { ...type.heading, fontSize: 14, fontWeight: '500' },
  rule: { height: 1, backgroundColor: colors.borderSubtle, marginVertical: spacing.xs },
  meter: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceElevated, marginVertical: 5 },
  meterFill: { height: 6, borderRadius: radius.pill },
  // the firm's limit: a tick across the bar
  meterTick: { position: 'absolute', top: -4, width: 2, height: 14, marginLeft: -1, borderRadius: 1, backgroundColor: colors.textPrimary },
  field: { gap: 6 },
  hint: { ...type.small, fontSize: 11, lineHeight: 15 },
  dateText: { ...type.num, fontSize: 15, fontWeight: '400' },
  selfStart: { alignSelf: 'flex-start' },
})
