import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useMemo, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { createAlert, deleteAlert, getAlerts } from '../api/alerts'
import { formatPrice, formatUpdated } from '../format'
import { colors, radius, spacing } from '../theme'
import type { AlertCondition, AlertItem, AlertsResponse } from '../types/alerts'

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
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} tintColor={colors.accent} />}
        >
          <View style={styles.card}>
            <Text style={styles.cardTitle}>New alert</Text>
            <TextInput
              value={symbol}
              onChangeText={setSymbol}
              placeholder="Symbol, e.g. XAUUSD"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="characters"
              autoCorrect={false}
              style={styles.input}
            />
            {suggestions.length > 0 ? (
              <View style={styles.suggestRow}>
                {suggestions.map((s) => (
                  <Pressable key={s} onPress={() => setSymbol(s)} style={styles.suggest} accessibilityRole="button">
                    <Text style={styles.suggestText}>{s}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            <View style={styles.condRow}>
              {(['ABOVE', 'BELOW'] as const).map((c) => (
                <Pressable
                  key={c}
                  onPress={() => setCondition(c)}
                  style={[styles.cond, condition === c && styles.condOn]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: condition === c }}
                >
                  <Text style={[styles.condText, condition === c && styles.condTextOn]}>
                    {c === 'ABOVE' ? 'Price goes above ▲' : 'Price goes below ▼'}
                  </Text>
                </Pressable>
              ))}
            </View>
            <TextInput
              value={price}
              onChangeText={setPrice}
              placeholder="Target price"
              placeholderTextColor={colors.textMuted}
              keyboardType="decimal-pad"
              style={styles.input}
            />
            <TextInput
              value={notes}
              onChangeText={setNotes}
              placeholder="Note (optional)"
              placeholderTextColor={colors.textMuted}
              maxLength={500}
              style={styles.input}
            />
            {formError ? <Text style={styles.error}>{formError}</Text> : null}
            <Pressable onPress={() => void submit()} disabled={saving} style={[styles.primary, saving && { opacity: 0.6 }]} accessibilityRole="button">
              {saving ? <ActivityIndicator color="#000" /> : <Text style={styles.primaryText}>Add alert</Text>}
            </Pressable>
            <Text style={styles.note}>
              Alerts are checked by the background sync that watches live prices. This only notifies you — it never places a trade.
            </Text>
          </View>

          {loading && !data ? <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.lg }} /> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}

          {data ? (
            <>
              <Text style={styles.section}>Active · {active.length}</Text>
              {active.length === 0 ? <Text style={styles.muted}>No active alerts.</Text> : null}
              {active.map((a) => (
                <AlertRow key={a.id} a={a} onDelete={() => confirmDelete(a)} />
              ))}
              {triggered.length > 0 ? (
                <>
                  <Text style={styles.section}>Triggered · {triggered.length}</Text>
                  {triggered.map((a) => (
                    <AlertRow key={a.id} a={a} onDelete={() => confirmDelete(a)} />
                  ))}
                </>
              ) : null}
            </>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

function AlertRow({ a, onDelete }: { a: AlertItem; onDelete: () => void }) {
  const isActive = a.status === 'ACTIVE'
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <View style={styles.rowTop}>
          <Text style={styles.rowSymbol}>{a.symbol}</Text>
          <View style={[styles.pill, { borderColor: isActive ? colors.accent : colors.positive }]}>
            <Text style={[styles.pillText, { color: isActive ? colors.accent : colors.positive }]}>{isActive ? 'ACTIVE' : 'TRIGGERED'}</Text>
          </View>
        </View>
        <Text style={styles.rowTarget}>
          {a.condition === 'ABOVE' ? '▲ above' : '▼ below'} {formatPrice(a.target_price)}
        </Text>
        {a.notes ? <Text style={styles.rowNotes}>{a.notes}</Text> : null}
        <Text style={styles.rowMeta}>
          {a.triggered_at ? `Triggered ${formatUpdated(a.triggered_at)}` : `Created ${formatUpdated(a.created_at)}`}
        </Text>
      </View>
      <Pressable onPress={onDelete} hitSlop={10} style={styles.del} accessibilityRole="button" accessibilityLabel={`Delete ${a.symbol} alert`}>
        <Text style={styles.delText}>Delete</Text>
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.sm, paddingBottom: spacing.xl * 2 },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  cardTitle: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  input: {
    color: colors.textPrimary,
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
  },
  suggestRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  suggest: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  suggestText: { color: colors.textSecondary, fontSize: 13 },
  condRow: { flexDirection: 'row', gap: spacing.sm },
  cond: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  condOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  condText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  condTextOn: { color: colors.accent },
  primary: { backgroundColor: colors.accent, borderRadius: radius.md, alignItems: 'center', paddingVertical: spacing.md },
  primaryText: { color: '#000', fontWeight: '700', fontSize: 15 },
  note: { color: colors.textMuted, fontSize: 11 },
  error: { color: colors.negative, fontSize: 13 },
  section: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, marginTop: spacing.md },
  muted: { color: colors.textMuted, fontSize: 13 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  rowSymbol: { color: colors.textPrimary, fontSize: 17, fontWeight: '700' },
  pill: { borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 1 },
  pillText: { fontSize: 10, fontWeight: '700' },
  rowTarget: { color: colors.textPrimary, fontSize: 15, marginTop: 2, fontVariant: ['tabular-nums'] },
  rowNotes: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  rowMeta: { color: colors.textMuted, fontSize: 11, marginTop: 4 },
  del: { paddingHorizontal: spacing.sm, paddingVertical: spacing.sm },
  delText: { color: colors.negative, fontSize: 13, fontWeight: '600' },
})
