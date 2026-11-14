import AsyncStorage from '@react-native-async-storage/async-storage'
import { useRoute, type RouteProp } from '@react-navigation/native'
import { useEffect, useMemo, useState } from 'react'
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { postRiskPreview } from '../api/risk'
import { Text } from '../components/Text'
import { Button, Card, Chip, ChipRow, Field, Figures, Footnote, Notice, Seg, Stat, ui } from '../components/ui'
import { formatMoney, formatPrice } from '../format'
import { useJournal } from '../journal/JournalContext'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, spacing, type } from '../theme'
import type { RiskPreviewRequest, RiskPreviewResponse } from '../types/risk'

const PREFS_KEY = 'tl.risk.prefs'
const DEFAULT_SYMBOLS = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'US500']
const SIDES = [
  { key: 'BUY', label: 'Buy' },
  { key: 'SELL', label: 'Sell' },
] as const

const num = (s: string): number | null => {
  if (!s.trim()) return null
  const n = Number(s.replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

const lots = (v: number) => (Number.isFinite(v) ? v.toFixed(2) : '—')
const usd = (v: number) => formatMoney(v, false)

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
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={ui.content} keyboardShouldPersistTaps="handled">
          <Text style={ui.muted}>Works out how big the trade should be so that a hit stop costs only the share of your account you choose.</Text>

          <Card title="The trade">
            <Field label="Market" value={symbol} onChangeText={setSymbol} autoCapitalize="characters" error={show('symbol')} />
            <ChipRow wrap>
              {symbolChips.map((s) => (
                <Chip key={s} label={s} on={symbol.toUpperCase() === s} onPress={() => setSymbol(s)} />
              ))}
            </ChipRow>
            <Seg options={SIDES} value={side} onChange={setSide} />
            <View style={ui.cols}>
              <Field half label="Entry price" value={entry} onChangeText={setEntry} keyboardType="decimal-pad" error={show('entry')} />
              <Field half label="Stop loss" value={stop} onChangeText={setStop} keyboardType="decimal-pad" error={show('stop')} />
            </View>
            <View style={ui.cols}>
              <Field half label="Target 1 (optional)" value={tp1} onChangeText={setTp1} keyboardType="decimal-pad" error={show('tp1')} />
              <Field half label="Target 2 (optional)" value={tp2} onChangeText={setTp2} keyboardType="decimal-pad" error={show('tp2')} />
            </View>
          </Card>

          <Card title="Your risk">
            <View style={ui.cols}>
              <Field half label="Account balance ($)" value={balance} onChangeText={setBalance} keyboardType="decimal-pad" error={show('balance')} />
              <Field half label="Risk per trade (%)" value={riskPct} onChangeText={setRiskPct} keyboardType="decimal-pad" error={show('riskPct')} />
            </View>
          </Card>

          <Button label="Work out the size" icon="calculator-outline" busy={busy} onPress={() => void calculate()} />

          {error ? <Notice>Couldn't work it out: {error}</Notice> : null}

          {result ? (
            <View style={[styles.result, stale && { opacity: 0.55 }]}>
              {stale ? <Notice tone="warn">The numbers above changed. Work it out again for an updated size.</Notice> : null}

              {result.errors.length > 0 ? <Notice>This trade setup isn't valid: {result.errors.join(' ')}</Notice> : null}

              {result.is_valid ? (
                <Card feature flush>
                  <View style={styles.heroBlock}>
                    <Text style={styles.heroLabel}>Trade this size</Text>
                    <Text style={styles.lots}>
                      {lots(result.calculated_lot_size)} <Text style={styles.lotsUnit}>lots</Text>
                    </Text>
                    <Text style={ui.muted}>
                      {result.symbol} · {result.side === 'BUY' ? 'buy' : 'sell'}
                    </Text>
                  </View>
                  <Figures style={styles.topRule}>
                    <Stat small label="You risk" value={usd(result.actual_risk_usd)} sub={`${result.actual_risk_pct.toFixed(2)}% of the account`} />
                    <Stat small label="You asked for" value={usd(result.target_risk_usd)} sub="from your risk %" />
                    <Stat small label="Stop distance" value={formatPrice(Math.abs(result.entry_price - result.stop_loss))} sub="in price" />
                    <Stat small label="Margin needed" value={usd(result.estimated_margin_usd)} sub="estimate" />
                    {result.take_profit_1 > 0 ? <Stat small label="Target 1 pays" value={usd(result.reward_tp1_usd)} sub={`${result.reward_tp1_pct.toFixed(2)}%`} /> : null}
                    {result.take_profit_1 > 0 ? <Stat small label="Risk : reward" value={result.risk_reward_ratio} /> : null}
                    {result.take_profit_2 > 0 ? <Stat small label="Target 2 pays" value={usd(result.reward_tp2_usd)} sub={`${result.reward_tp2_pct.toFixed(2)}%`} /> : null}
                  </Figures>
                </Card>
              ) : result.errors.length > 0 ? (
                <Text style={ui.muted}>No size to suggest until the problems above are fixed.</Text>
              ) : null}

              {result.warnings.length > 0 ? <Notice tone="warn">{result.warnings.join(' ')}</Notice> : null}
            </View>
          ) : null}

          <Footnote>Planning only. Nothing is executed and no order is ever sent.</Footnote>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  result: { gap: spacing.md },
  heroBlock: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.md, gap: 2 },
  heroLabel: { ...type.label },
  lots: { ...type.hero },
  lotsUnit: { ...type.sub, fontSize: 16, fontWeight: '400', letterSpacing: 0 },
  topRule: { borderTopWidth: 1, borderTopColor: colors.borderSubtle },
})
