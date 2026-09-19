import AsyncStorage from '@react-native-async-storage/async-storage'
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
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
  type KeyboardTypeOptions,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { createManualTrade } from '../api/journal'
import { formatMoney } from '../format'
import { useJournal } from '../journal/JournalContext'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, radius, spacing } from '../theme'

const ACCOUNT_KEY = 'tl.manualtrade.account'

const fmtDateTime = (d: Date) =>
  `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}, ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`

/** Android shows a date dialog then a time dialog; iOS renders the compact picker inline. */
function DateTimeField({ label, value, onChange }: { label: string; value: Date; onChange: (d: Date) => void }) {
  function openAndroid() {
    DateTimePickerAndroid.open({
      value,
      mode: 'date',
      onValueChange: (_e, picked) => {
        DateTimePickerAndroid.open({
          value: picked,
          mode: 'time',
          is24Hour: false,
          onValueChange: (_e2, time) => onChange(time),
        })
      },
    })
  }
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      {Platform.OS === 'android' ? (
        <Pressable onPress={openAndroid} style={styles.input} accessibilityRole="button">
          <Text style={styles.inputText}>{fmtDateTime(value)}</Text>
        </Pressable>
      ) : (
        <DateTimePicker value={value} mode="datetime" onValueChange={(_e, d) => onChange(d)} themeVariant="dark" />
      )}
    </View>
  )
}

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  autoCapitalize,
  half,
  multiline,
}: {
  label: string
  value: string
  onChangeText: (t: string) => void
  placeholder?: string
  keyboardType?: KeyboardTypeOptions
  autoCapitalize?: 'none' | 'characters'
  half?: boolean
  multiline?: boolean
}) {
  return (
    <View style={[styles.field, half && styles.half]}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize ?? 'none'}
        autoCorrect={false}
        multiline={multiline}
        style={[styles.input, styles.inputText, multiline && { minHeight: 90, textAlignVertical: 'top' }]}
      />
    </View>
  )
}

const num = (s: string) => {
  if (!s.trim()) return NaN // Number('') is 0, which would pass as a real profit
  const n = Number(s.replace(/,/g, ''))
  return Number.isFinite(n) ? n : NaN
}

/** Record a trade you took outside any synced broker. It lands in the Journal, Analytics and the calendar like any other closed trade. */
export function ManualTradeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { data: journal, refresh } = useJournal()
  const { data: positions } = usePositionsContext()
  const tagSuggestions = useTagSuggestions()

  const knownAccounts = useMemo(() => {
    const set = new Set<string>()
    journal?.entries.forEach((e) => e.account_id && set.add(e.account_id))
    positions?.positions.forEach((p) => p.account_id && set.add(p.account_id))
    return [...set]
  }, [journal, positions])

  const [account, setAccount] = useState('')
  const [symbol, setSymbol] = useState('')
  const [direction, setDirection] = useState<'BUY' | 'SELL'>('BUY')
  const [volume, setVolume] = useState('')
  const [entryPrice, setEntryPrice] = useState('')
  const [exitPrice, setExitPrice] = useState('')
  const [grossProfit, setGrossProfit] = useState('')
  const [commission, setCommission] = useState('')
  const [swap, setSwap] = useState('')
  const [exitTime, setExitTime] = useState(() => new Date())
  const [entryTime, setEntryTime] = useState(() => new Date(Date.now() - 60 * 60 * 1000))
  const [tag, setTag] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    AsyncStorage.getItem(ACCOUNT_KEY)
      .then((v) => v && setAccount((cur) => cur || v))
      .catch(() => {})
  }, [])

  const net = useMemo(() => {
    const g = num(grossProfit)
    if (!Number.isFinite(g)) return null
    return g + (num(commission) || 0) + (num(swap) || 0)
  }, [grossProfit, commission, swap])

  async function submit() {
    setError(null)
    const acc = account.trim()
    const sym = symbol.trim().toUpperCase()
    const g = num(grossProfit)
    if (!acc) return setError('Account is required — use a name like OWN_MONEY if this is not a synced account.')
    if (!sym) return setError('Symbol is required.')
    if (!Number.isFinite(g)) return setError('Profit is required — enter 0 for a scratch trade.')
    if (exitTime < entryTime) return setError('Exit time is before entry time.')
    setBusy(true)
    try {
      await createManualTrade({
        account_id: acc,
        symbol: sym,
        direction,
        volume: num(volume) || 0,
        entry_price: num(entryPrice) || 0,
        exit_price: num(exitPrice) || 0,
        commission: num(commission) || 0,
        swap: num(swap) || 0,
        gross_profit: g,
        entry_time: entryTime.toISOString(),
        exit_time: exitTime.toISOString(),
        setup_tag: tag.trim() || undefined,
        notes: notes.trim() || undefined,
      })
      AsyncStorage.setItem(ACCOUNT_KEY, acc).catch(() => {})
      void refresh()
      navigation.goBack()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the trade.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.intro}>
            For a trade that never went through a synced broker. It appears in your Journal, Analytics and calendar like any other closed trade. Enter profit and fees as your platform reported them.
          </Text>

          <Field label="Account" value={account} onChangeText={setAccount} placeholder="e.g. OWN_MONEY" />
          {knownAccounts.length > 0 ? (
            <View style={styles.chips}>
              {knownAccounts.map((a) => (
                <Pressable key={a} onPress={() => setAccount(a)} style={[styles.chip, account === a && styles.chipOn]} accessibilityRole="button">
                  <Text style={[styles.chipText, account === a && styles.chipTextOn]}>{a}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}

          <Field label="Symbol" value={symbol} onChangeText={setSymbol} placeholder="EURUSD" autoCapitalize="characters" />

          <View style={styles.dirRow}>
            {(['BUY', 'SELL'] as const).map((d) => {
              const on = direction === d
              const c = d === 'BUY' ? colors.positive : colors.negative
              return (
                <Pressable
                  key={d}
                  onPress={() => setDirection(d)}
                  style={[styles.dir, { borderColor: on ? c : colors.border, backgroundColor: on ? `${c}22` : 'transparent' }]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: on }}
                >
                  <Text style={[styles.dirText, { color: on ? c : colors.textSecondary }]}>{d}</Text>
                </Pressable>
              )
            })}
          </View>

          <View style={styles.row}>
            <Field half label="Volume (lots)" value={volume} onChangeText={setVolume} keyboardType="decimal-pad" />
            <Field half label="Entry price" value={entryPrice} onChangeText={setEntryPrice} keyboardType="decimal-pad" />
          </View>
          <View style={styles.row}>
            <Field half label="Exit price" value={exitPrice} onChangeText={setExitPrice} keyboardType="decimal-pad" />
            <Field half label="Profit ($) — required" value={grossProfit} onChangeText={setGrossProfit} keyboardType="numbers-and-punctuation" />
          </View>
          <View style={styles.row}>
            <Field half label="Commission ($)" value={commission} onChangeText={setCommission} keyboardType="numbers-and-punctuation" />
            <Field half label="Swap ($)" value={swap} onChangeText={setSwap} keyboardType="numbers-and-punctuation" />
          </View>
          {net !== null ? (
            <Text style={[styles.net, { color: net > 0 ? colors.positive : net < 0 ? colors.negative : colors.textSecondary }]}>
              Net result {formatMoney(net)}
            </Text>
          ) : null}

          <DateTimeField label="Entered" value={entryTime} onChange={setEntryTime} />
          <DateTimeField label="Closed" value={exitTime} onChange={setExitTime} />

          <Field label="Setup tag (optional)" value={tag} onChangeText={setTag} placeholder="e.g. BREAKOUT" autoCapitalize="characters" />
          {tagSuggestions.length > 0 ? (
            <View style={styles.chips}>
              {tagSuggestions.slice(0, 8).map((t) => (
                <Pressable key={t} onPress={() => setTag(t)} style={[styles.chip, tag === t && styles.chipOn]} accessibilityRole="button">
                  <Text style={[styles.chipText, tag === t && styles.chipTextOn]}>{t}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
          <Field label="Notes (optional)" value={notes} onChangeText={setNotes} placeholder="What happened, why you took it, what you'd do differently" multiline />

          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable onPress={() => void submit()} disabled={busy} style={[styles.primary, busy && { opacity: 0.6 }]} accessibilityRole="button">
            {busy ? <ActivityIndicator color="#000" /> : <Text style={styles.primaryText}>Save trade</Text>}
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  intro: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  field: { gap: 4 },
  half: { flex: 1 },
  row: { flexDirection: 'row', gap: spacing.md },
  label: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6 },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  inputText: { color: colors.textPrimary, fontSize: 15 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  chipOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  chipText: { color: colors.textSecondary, fontSize: 12 },
  chipTextOn: { color: colors.accent },
  dirRow: { flexDirection: 'row', gap: spacing.sm },
  dir: { flex: 1, alignItems: 'center', paddingVertical: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  dirText: { fontWeight: '700', fontSize: 14 },
  net: { fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  error: { color: colors.negative, fontSize: 13 },
  primary: { backgroundColor: colors.accent, borderRadius: radius.md, alignItems: 'center', paddingVertical: spacing.md + 2 },
  primaryText: { color: '#000', fontWeight: '700', fontSize: 16 },
})
