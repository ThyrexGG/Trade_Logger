import AsyncStorage from '@react-native-async-storage/async-storage'
import { useRoute, type RouteProp } from '@react-navigation/native'
import { useEffect, useMemo, useState } from 'react'
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { postRiskPreview } from '../api/risk'
import { formatMoney, formatPrice } from '../format'
import { useJournal } from '../journal/JournalContext'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { RiskPreviewRequest, RiskPreviewResponse } from '../types/risk'

const PREFS_KEY = 'tl.risk.prefs'
const DEFAULT_SYMBOLS = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'US500']

const num = (s: string): number | null => {
  if (!s.trim()) return null
  const n = Number(s.replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

const lots = (v: number) => (Number.isFinite(v) ? v.toFixed(2) : '—')
const usd = (v: number) => formatMoney(v, false)

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  error,
  half,
  caps,
}: {
  label: string
  value: string
  onChangeText: (t: string) => void
  placeholder?: string
  error?: string
  half?: boolean
  caps?: boolean
}) {
  return (
    <View style={[styles.field, half && { flex: 1 }]}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        keyboardType={caps ? 'default' : 'decimal-pad'}
        autoCapitalize={caps ? 'characters' : 'none'}
        autoCorrect={false}
        style={[styles.input, error ? { borderColor: colors.negative } : null]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  )
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
      {sub ? <Text style={styles.metricSub}>{sub}</Text> : null}
    </View>
  )
}

/** Pre-trade position sizing — the server's risk gateway does the maths. Planning only; nothing is ever placed. */
export function RiskGatewayScreen() {
  const { data: journal } = useJournal()
  // opened from the chart analyzer: start from the levels it read (balance and risk % still come from your saved choices)
  const prefill = useRoute<RouteProp<RootStackParamList, 'RiskGateway'>>().params?.prefill
  const [symbol, setSymbol] = useState(prefill?.symbol?.toUpperCase() ?? 'XAUUSD')
  const [side, setSide] = useState<'BUY' | 'SELL'>(prefill?.side ?? 'BUY')
  const [balance, setBalance] = useState('10000')
  const [riskPct, setRiskPct] = useState('1.0')
  const [entry, setEntry] = useState(prefill?.entry != null ? String(prefill.entry) : '')
  const [stop, setStop] = useState(prefill?.stop != null ? String(prefill.stop) : '')
  const [tp1, setTp1] = useState(prefill?.tp1 != null ? String(prefill.tp1) : '')
  const [tp2, setTp2] = useState(prefill?.tp2 != null ? String(prefill.tp2) : '')
  const [showErrors, setShowErrors] = useState(false)

  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<RiskPreviewResponse | null>(null)
  const [resultKey, setResultKey] = useState('')
  const [error, setError] = useState<string | null>(null)

  // remember the balance / risk % / symbol between visits
  useEffect(() => {
    AsyncStorage.getItem(PREFS_KEY)
      .then((raw) => {
        if (!raw) return
        const p = JSON.parse(raw) as { symbol?: string; balance?: string; riskPct?: string }
        if (p.symbol && !prefill?.symbol) setSymbol(p.symbol)
        if (p.balance) setBalance(p.balance)
        if (p.riskPct) setRiskPct(p.riskPct)
      })
      .catch(() => {})
  }, [])

  const symbolChips = useMemo(() => {
    const counts = new Map<string, number>()
    journal?.entries.forEach((e) => counts.set(e.symbol.toUpperCase(), (counts.get(e.symbol.toUpperCase()) ?? 0) + 1))
    const mine = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s)
    return [...new Set([...mine, ...DEFAULT_SYMBOLS])].slice(0, 8)
  }, [journal])

  const b = num(balance)
  const r = num(riskPct)
  const en = num(entry)
  const sl = num(stop)
  const t1 = num(tp1)
  const t2 = num(tp2)

  const errors = {
    symbol: symbol.trim() ? undefined : 'Required',
    balance: b === null ? 'Enter a number' : b <= 0 ? 'Must be above 0' : undefined,
    riskPct: r === null ? 'Enter a number' : r <= 0 ? 'Must be above 0' : undefined,
    entry: en === null ? 'Required' : en <= 0 ? 'Must be above 0' : undefined,
    stop: sl === null ? 'Required' : sl <= 0 ? 'Must be above 0' : en !== null && sl === en ? 'Cannot equal entry' : undefined,
    tp1: tp1.trim() && (t1 === null || t1 <= 0) ? 'Must be a positive number' : undefined,
    tp2: tp2.trim() && (t2 === null || t2 <= 0) ? 'Must be a positive number' : undefined,
  }
  const valid = Object.values(errors).every((e) => !e)
  const show = (k: keyof typeof errors) => (showErrors ? errors[k] : undefined)

  const currentKey = JSON.stringify([symbol.trim().toUpperCase(), side, b, r, en, sl, t1, t2])
  const stale = result !== null && currentKey !== resultKey

  async function calculate() {
    if (!valid || b === null || r === null || en === null || sl === null) {
      setShowErrors(true)
      return
    }
    setShowErrors(false)
    setBusy(true)
    setError(null)
    const req: RiskPreviewRequest = {
      symbol: symbol.trim().toUpperCase(),
      side,
      entry_price: en,
      stop_loss: sl,
      take_profit_1: t1,
      take_profit_2: t2,
      requested_risk_pct: r,
      account_balance: b,
    }
    try {
      const res = await postRiskPreview(req)
      setResult(res)
      setResultKey(currentKey)
      AsyncStorage.setItem(PREFS_KEY, JSON.stringify({ symbol: req.symbol, balance, riskPct })).catch(() => {})
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Risk preview unavailable.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.lock}>
            <Text style={styles.lockText}>🔒 Planning only — nothing is executed and no order is ever sent.</Text>
          </View>

          <Field label="Symbol" value={symbol} onChangeText={setSymbol} caps error={show('symbol')} />
          <View style={styles.chips}>
            {symbolChips.map((s) => (
              <Pressable key={s} onPress={() => setSymbol(s)} style={[styles.chip, symbol.toUpperCase() === s && styles.chipOn]} accessibilityRole="button">
                <Text style={[styles.chipText, symbol.toUpperCase() === s && styles.chipTextOn]}>{s}</Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.sideRow}>
            {(['BUY', 'SELL'] as const).map((d) => {
              const on = side === d
              const c = d === 'BUY' ? colors.positive : colors.negative
              return (
                <Pressable
                  key={d}
                  onPress={() => setSide(d)}
                  style={[styles.side, { borderColor: on ? c : colors.border, backgroundColor: on ? `${c}22` : 'transparent' }]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: on }}
                >
                  <Text style={[styles.sideText, { color: on ? c : colors.textSecondary }]}>{d}</Text>
                </Pressable>
              )
            })}
          </View>

          <View style={styles.row}>
            <Field half label="Account balance ($)" value={balance} onChangeText={setBalance} error={show('balance')} />
            <Field half label="Risk per trade (%)" value={riskPct} onChangeText={setRiskPct} error={show('riskPct')} />
          </View>
          <View style={styles.row}>
            <Field half label="Entry price" value={entry} onChangeText={setEntry} error={show('entry')} />
            <Field half label="Stop loss" value={stop} onChangeText={setStop} error={show('stop')} />
          </View>
          <View style={styles.row}>
            <Field half label="Take profit 1 (optional)" value={tp1} onChangeText={setTp1} error={show('tp1')} />
            <Field half label="Take profit 2 (optional)" value={tp2} onChangeText={setTp2} error={show('tp2')} />
          </View>

          <Pressable onPress={() => void calculate()} disabled={busy} style={[styles.primary, busy && { opacity: 0.6 }]} accessibilityRole="button">
            {busy ? <ActivityIndicator color="#000" /> : <Text style={styles.primaryText}>Calculate risk</Text>}
          </Pressable>

          {error ? (
            <View style={styles.box}>
              <Text style={styles.errorTitle}>Risk preview unavailable</Text>
              <Text style={styles.muted}>{error}</Text>
            </View>
          ) : null}

          {result ? (
            <View style={[styles.box, stale && { opacity: 0.55 }]}>
              {stale ? <Text style={styles.stale}>Inputs changed — calculate again for an updated size.</Text> : null}

              {result.errors.length > 0 ? (
                <View style={styles.errBox}>
                  <Text style={styles.errorTitle}>Invalid trade setup</Text>
                  {result.errors.map((e, i) => (
                    <Text key={i} style={styles.errorLine}>
                      • {e}
                    </Text>
                  ))}
                </View>
              ) : null}

              {result.is_valid ? (
                <>
                  <Text style={styles.label}>Recommended position</Text>
                  <Text style={styles.lots}>
                    {lots(result.calculated_lot_size)} <Text style={styles.lotsUnit}>lots</Text>
                  </Text>
                  <Text style={styles.metricSub}>
                    {result.symbol} · {result.side}
                  </Text>
                  <View style={styles.metrics}>
                    <Metric label="Estimated risk" value={usd(result.actual_risk_usd)} />
                    <Metric label="Risk %" value={`${result.actual_risk_pct.toFixed(2)}%`} />
                    <Metric label="Stop distance" value={formatPrice(Math.abs(result.entry_price - result.stop_loss))} sub="price units" />
                    <Metric label="Est. margin" value={usd(result.estimated_margin_usd)} />
                    <Metric label="Target risk" value={usd(result.target_risk_usd)} sub="from risk %" />
                    {result.take_profit_1 > 0 ? <Metric label="Reward TP1" value={usd(result.reward_tp1_usd)} sub={`${result.reward_tp1_pct.toFixed(2)}%`} /> : null}
                    {result.take_profit_1 > 0 ? <Metric label="Risk : reward" value={result.risk_reward_ratio} /> : null}
                    {result.take_profit_2 > 0 ? <Metric label="Reward TP2" value={usd(result.reward_tp2_usd)} sub={`${result.reward_tp2_pct.toFixed(2)}%`} /> : null}
                  </View>
                </>
              ) : result.errors.length > 0 ? (
                <Text style={styles.muted}>No valid position size — fix the problems above.</Text>
              ) : null}

              {result.warnings.length > 0 ? (
                <View style={styles.warnBox}>
                  <Text style={styles.warnTitle}>Warnings</Text>
                  {result.warnings.map((w, i) => (
                    <Text key={i} style={styles.warnLine}>
                      • {w}
                    </Text>
                  ))}
                </View>
              ) : null}
            </View>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  lock: { borderColor: 'rgba(239,68,68,0.3)', borderWidth: 1, backgroundColor: 'rgba(239,68,68,0.08)', borderRadius: radius.md, padding: spacing.md },
  lockText: { color: colors.negative, fontSize: 12 },
  field: { gap: 4 },
  row: { flexDirection: 'row', gap: spacing.md },
  label: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6 },
  input: {
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
  },
  fieldError: { color: colors.negative, fontSize: 11 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  chipOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  chipText: { color: colors.textSecondary, fontSize: 12 },
  chipTextOn: { color: colors.accent },
  sideRow: { flexDirection: 'row', gap: spacing.sm },
  side: { flex: 1, alignItems: 'center', paddingVertical: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  sideText: { fontWeight: '700', fontSize: 14 },
  primary: { backgroundColor: colors.accent, borderRadius: radius.md, alignItems: 'center', paddingVertical: spacing.md + 2 },
  primaryText: { color: '#000', fontWeight: '700', fontSize: 16 },
  box: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  muted: { color: colors.textMuted, fontSize: 13 },
  stale: { color: colors.warning, fontSize: 12 },
  errBox: { backgroundColor: 'rgba(239,68,68,0.1)', borderColor: 'rgba(239,68,68,0.4)', borderWidth: 1, borderRadius: radius.md, padding: spacing.md, gap: 2 },
  errorTitle: { color: colors.negative, fontWeight: '700', fontSize: 13 },
  errorLine: { color: colors.negative, fontSize: 13 },
  lots: { color: colors.textPrimary, fontSize: 34, fontWeight: '800', fontVariant: ['tabular-nums'] },
  lotsUnit: { color: colors.textMuted, fontSize: 16, fontWeight: '400' },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md, marginTop: spacing.sm },
  metric: { width: '47%' },
  metricValue: { color: colors.textPrimary, fontSize: 16, fontWeight: '600', fontVariant: ['tabular-nums'], marginTop: 2 },
  metricSub: { color: colors.textMuted, fontSize: 11 },
  warnBox: { backgroundColor: 'rgba(245,158,11,0.1)', borderColor: 'rgba(245,158,11,0.3)', borderWidth: 1, borderRadius: radius.md, padding: spacing.md, gap: 2 },
  warnTitle: { color: colors.warning, fontWeight: '700', fontSize: 12 },
  warnLine: { color: colors.warning, fontSize: 13 },
})
