import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useMemo, useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { createAlert, deleteAlert, getAlerts } from '../api/alerts'
import { Text, TextInput } from '../components/Text'
import { Button, Card, Chip, ChipRow, Empty, Loading, Notice, Pill, Rows, Seg, ui } from '../components/ui'
import { formatPrice, formatUpdated } from '../format'
import { colors, spacing, type } from '../theme'
import type { AlertCondition, AlertItem, AlertsResponse } from '../types/alerts'

const CONDITIONS: { key: AlertCondition; label: string }[] = [
  { key: 'ABOVE', label: 'Goes above' },
  { key: 'BELOW', label: 'Goes below' },
]

/** Price-target alerts: create, review and delete. Notification only — nothing here can place a trade. */
export function PriceAlertsScreen() {
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [symbol, setSymbol] = useState('')
  const [condition, setCondition] = useState<AlertCondition>('ABOVE')
  const [price, setPrice] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const load = useCallback((manual: boolean) => {
    if (manual) setRefreshing(true)
    return getAlerts()
      .then((r) => {
        setData(r)
        setError(null)
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not load alerts.'))
      .finally(() => {
        setLoading(false)
        setRefreshing(false)
      })
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load(false)
    }, [load]),
  )

  const suggestions = useMemo(() => {
    const q = symbol.trim().toUpperCase()
    if (!q || !data) return []
    const all = data.supported_symbols
    if (all.includes(q)) return []
    return all.filter((s) => s.toUpperCase().includes(q)).slice(0, 8)
  }, [symbol, data])

  async function submit() {
    const n = Number(price.replace(/,/g, ''))
    if (!symbol.trim()) return setFormError('Enter a symbol, for example XAUUSD.')
    if (!Number.isFinite(n) || n <= 0) return setFormError('Enter a target price above 0.')
    setSaving(true)
    setFormError(null)
    try {
      await createAlert({ symbol: symbol.trim(), target_price: n, condition, notes: notes.trim() || undefined })
      setSymbol('')
      setPrice('')
      setNotes('')
      await load(false)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not create the alert.')
    } finally {
      setSaving(false)
    }
  }

  function confirmDelete(a: AlertItem) {
    Alert.alert('Delete alert?', `${a.symbol} ${a.condition === 'ABOVE' ? 'above' : 'below'} ${formatPrice(a.target_price)}`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          deleteAlert(a.id)
            .then(() => load(false))
            .catch((err: unknown) => Alert.alert('Could not delete', err instanceof Error ? err.message : 'Try again.'))
        },
      },
    ])
  }

  const active = data?.alerts.filter((a) => a.status === 'ACTIVE') ?? []
  const triggered = data?.alerts.filter((a) => a.status !== 'ACTIVE') ?? []

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={ui.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} tintColor={colors.accent} colors={[colors.accent]} />}
        >
          <Card title="New alert">
            <View style={ui.cols}>
              <TextInput
                value={symbol}
                onChangeText={setSymbol}
                placeholder="Market, e.g. XAUUSD"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="characters"
                autoCorrect={false}
                accessibilityLabel="Market symbol"
                style={[ui.input, ui.flex]}
              />
              <TextInput
                value={price}
                onChangeText={setPrice}
                placeholder="Price"
                placeholderTextColor={colors.textMuted}
                keyboardType="decimal-pad"
                accessibilityLabel="Target price"
                style={[ui.input, styles.price]}
              />
            </View>
            {suggestions.length > 0 ? (
              <ChipRow wrap>
                {suggestions.map((s) => (
                  <Chip key={s} label={s} on={false} onPress={() => setSymbol(s)} />
                ))}
              </ChipRow>
            ) : null}
            <Seg options={CONDITIONS} value={condition} onChange={setCondition} />
            <TextInput value={notes} onChangeText={setNotes} placeholder="Note (optional)" placeholderTextColor={colors.textMuted} maxLength={500} style={ui.input} />
            {formError ? <Notice>{formError}</Notice> : null}
            <Button label="Add alert" icon="notifications-outline" busy={saving} onPress={() => void submit()} />
            <Text style={styles.note}>
              The server checks alerts about every 2 minutes against public market prices, which can differ slightly from your broker's. You get a notification when one is hit. It only tells you; it never places a trade.
            </Text>
          </Card>

          {loading && !data ? <Loading /> : null}
          {error ? <Notice>{error}</Notice> : null}

          {data && active.length === 0 && triggered.length === 0 ? <Empty icon="notifications-off-outline" title="No alerts yet" text="Add a market and a price above. You will get a notification when the price crosses it." /> : null}

          {active.length > 0 ? (
            <Card title="Waiting" right={String(active.length)} flush>
              <Rows>
                {active.map((a) => (
                  <AlertRow key={a.id} a={a} onDelete={() => confirmDelete(a)} />
                ))}
              </Rows>
            </Card>
          ) : null}
          {triggered.length > 0 ? (
            <Card title="Already hit" right={String(triggered.length)} flush>
              <Rows>
                {triggered.map((a) => (
                  <AlertRow key={a.id} a={a} onDelete={() => confirmDelete(a)} />
                ))}
              </Rows>
            </Card>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

function AlertRow({ a, onDelete }: { a: AlertItem; onDelete: () => void }) {
  const isActive = a.status === 'ACTIVE'
  const above = a.condition === 'ABOVE'
  return (
    <View style={styles.row}>
      <View style={styles.rowMain}>
        <View style={ui.rowWrap}>
          <Text style={ui.heading}>{a.symbol}</Text>
          <Ionicons name={above ? 'arrow-up' : 'arrow-down'} size={12} color={colors.textSecondary} />
          <Text style={styles.target}>
            {above ? 'above' : 'below'} {formatPrice(a.target_price)}
          </Text>
          {isActive ? null : <Pill text="Hit" color={colors.positive} />}
        </View>
        {a.notes ? <Text style={ui.sub}>{a.notes}</Text> : null}
        <Text style={styles.meta}>{a.triggered_at ? `Hit ${formatUpdated(a.triggered_at)}` : `Added ${formatUpdated(a.created_at)}`}</Text>
      </View>
      <Pressable onPress={onDelete} hitSlop={10} style={styles.del} accessibilityRole="button" accessibilityLabel={`Delete ${a.symbol} alert`}>
        <Ionicons name="trash-outline" size={18} color={colors.textMuted} />
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  price: { width: 120, fontVariant: ['tabular-nums'] },
  note: { ...type.small, fontSize: 11, lineHeight: 15 },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  rowMain: { flex: 1, gap: 3, minWidth: 0 },
  target: { ...type.num },
  meta: { ...type.small, fontSize: 11, fontVariant: ['tabular-nums'] },
  del: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
})
