import AsyncStorage from '@react-native-async-storage/async-storage'
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useEffect, useMemo, useState } from 'react'
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { describeAccount } from '../accountLabel'
import { clearAnalyticsCache } from '../analytics/useAnalytics'
import { createManualTrade, updateManualTrade } from '../api/journal'
import { Text } from '../components/Text'
import { Button, Card, Chip, ChipRow, Field, Notice, Seg, ui } from '../components/ui'
import { formatMoney } from '../format'
import { useJournal } from '../journal/JournalContext'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, pnlColor, type } from '../theme'

const ACCOUNT_KEY = 'tl.manualtrade.account'
const SIDES = [
  { key: 'BUY', label: 'Buy' },
  { key: 'SELL', label: 'Sell' },
] as const

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
      <Text style={ui.fieldLabel}>{label}</Text>
      {Platform.OS === 'ios' ? (
        <DateTimePicker value={value} mode="datetime" onValueChange={(_e, d) => onChange(d)} themeVariant="dark" />
      ) : (
        <Pressable onPress={openAndroid} style={ui.input} accessibilityRole="button" accessibilityLabel={`${label}: ${fmtDateTime(value)}`}>
          <Text style={styles.inputText}>{fmtDateTime(value)}</Text>
        </Pressable>
      )}
    </View>
  )
}

/** Server timestamps are UTC; one without a zone marker would otherwise be read as the phone's local time. */
const parseServerTime = (iso: string) => {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso.replace(' ', 'T')}Z`)
  return Number.isNaN(d.getTime()) ? new Date() : d
}
const numText = (n: number | null | undefined) => (n ? String(n) : '')

const num = (s: string) => {
  if (!s.trim()) return NaN // Number('') is 0, which would pass as a real profit
  const n = Number(s.replace(/,/g, ''))
  return Number.isFinite(n) ? n : NaN
}

/**
 * Record a trade you took outside any synced broker — or, when opened from a hand-logged trade, correct it.
 * It lands in the Journal, Analytics and the calendar like any other closed trade.
 */
export function ManualTradeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const editing = useRoute<RouteProp<RootStackParamList, 'ManualTrade'>>().params?.trade
  const { data: journal, refresh, applyEntry } = useJournal()
  const { data: positions } = usePositionsContext()
  const tagSuggestions = useTagSuggestions()

  const knownAccounts = useMemo(() => {
    const set = new Set<string>()
    journal?.entries.forEach((e) => e.account_id && set.add(e.account_id))
    positions?.positions.forEach((p) => p.account_id && set.add(p.account_id))
    return [...set]
  }, [journal, positions])

  const [account, setAccount] = useState(editing?.account_id ?? '')
  const [symbol, setSymbol] = useState(editing?.symbol ?? '')
  const [direction, setDirection] = useState<'BUY' | 'SELL'>(editing && editing.direction.toUpperCase().includes('SELL') ? 'SELL' : 'BUY')
  const [volume, setVolume] = useState(numText(editing?.volume))
  const [entryPrice, setEntryPrice] = useState(numText(editing?.entry_price))
  const [exitPrice, setExitPrice] = useState(numText(editing?.exit_price))
  const [grossProfit, setGrossProfit] = useState(editing ? String(editing.gross_profit) : '')
  const [commission, setCommission] = useState(numText(editing?.commission))
  const [swap, setSwap] = useState(numText(editing?.swap))
  const [exitTime, setExitTime] = useState(() => (editing ? parseServerTime(editing.exit_time) : new Date()))
  const [entryTime, setEntryTime] = useState(() => (editing ? parseServerTime(editing.entry_time) : new Date(Date.now() - 60 * 60 * 1000)))
  const [tag, setTag] = useState(editing?.setup_tag ?? '')
  const [notes, setNotes] = useState(editing?.notes ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    navigation.setOptions({ title: editing ? 'Edit trade' : 'Log a trade' })
  }, [navigation, editing])

  useEffect(() => {
    if (editing) return // fixing an old trade keeps its own account
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
    if (!acc) return setError('Account is required. Use a name like OWN_MONEY if this is not a synced account.')
    if (!sym) return setError('Market is required.')
    if (!Number.isFinite(g)) return setError('Profit is required. Enter 0 for a trade that broke even.')
    if (exitTime < entryTime) return setError('The close time is before the open time.')
    setBusy(true)
    try {
      const body = {
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
        // an edit sends the notes as they now are (empty clears them); a new trade sends none when blank
        notes: editing ? notes.trim() : notes.trim() || undefined,
      }
      if (editing) applyEntry(await updateManualTrade(editing.trade_id, body))
      else await createManualTrade(body)
      if (!editing) AsyncStorage.setItem(ACCOUNT_KEY, acc).catch(() => {})
      clearAnalyticsCache()
      void refresh()
      navigation.goBack()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the trade.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={ui.content} keyboardShouldPersistTaps="handled">
          <Text style={ui.muted}>
            {editing
              ? 'Fix a mistake in this trade. Analytics and the calendar update to match.'
              : 'For a trade that never went through a synced broker. It shows in your Journal, Analytics and calendar like any other closed trade. Enter profit and fees as your platform reported them.'}
          </Text>

          <Card title="The trade">
            <Field label="Account" value={account} onChangeText={setAccount} placeholder="e.g. OWN_MONEY" />
            {knownAccounts.length > 0 ? (
              <ChipRow wrap>
                {knownAccounts.map((a) => (
                  <Chip key={a} label={describeAccount(a).label} on={account === a} onPress={() => setAccount(a)} />
                ))}
              </ChipRow>
            ) : null}
            <Field label="Market" value={symbol} onChangeText={setSymbol} placeholder="EURUSD" autoCapitalize="characters" />
            <Seg options={SIDES} value={direction} onChange={setDirection} />
            <View style={ui.cols}>
              <Field half label="Size (lots)" value={volume} onChangeText={setVolume} keyboardType="decimal-pad" />
              <Field half label="Entry price" value={entryPrice} onChangeText={setEntryPrice} keyboardType="decimal-pad" />
            </View>
            <Field label="Exit price" value={exitPrice} onChangeText={setExitPrice} keyboardType="decimal-pad" />
            <DateTimeField label="Opened" value={entryTime} onChange={setEntryTime} />
            <DateTimeField label="Closed" value={exitTime} onChange={setExitTime} />
          </Card>

          <Card title="The result">
            <Field label="Profit ($), required" value={grossProfit} onChangeText={setGrossProfit} keyboardType="numbers-and-punctuation" hint="Use a minus sign for a loss, 0 for break-even." />
            <View style={ui.cols}>
              <Field half label="Commission ($)" value={commission} onChangeText={setCommission} keyboardType="numbers-and-punctuation" />
              <Field half label="Swap ($)" value={swap} onChangeText={setSwap} keyboardType="numbers-and-punctuation" />
            </View>
            {net !== null ? (
              <View style={[ui.rowBetween, styles.netRow]}>
                <Text style={ui.sub}>Net result</Text>
                <Text style={[styles.net, { color: pnlColor(net) }]}>{formatMoney(net)}</Text>
              </View>
            ) : null}
          </Card>

          <Card title="Your journal">
            <Field label="Label (optional)" value={tag} onChangeText={setTag} placeholder="e.g. By my rules" autoCapitalize="sentences" />
            {tagSuggestions.length > 0 ? (
              <ChipRow wrap>
                {tagSuggestions.slice(0, 8).map((t) => (
                  <Chip key={t} label={t} on={tag === t} onPress={() => setTag(t)} />
                ))}
              </ChipRow>
            ) : null}
            <Field label="Note (optional)" value={notes} onChangeText={setNotes} placeholder="What happened, why you took it, what you'd do differently" multiline autoCapitalize="sentences" />
          </Card>

          {error ? <Notice>{error}</Notice> : null}
          <Button label={editing ? 'Save changes' : 'Save trade'} busy={busy} onPress={() => void submit()} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  field: { gap: 6 },
  inputText: { ...type.num, fontSize: 15, fontWeight: '400' },
  netRow: { borderTopWidth: 1, borderTopColor: colors.borderSubtle, paddingTop: 12, marginTop: 4 },
  net: { ...type.figure },
})
