import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useRef, useState } from 'react'
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, RefreshControl, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { clearAnalyticsCache } from '../analytics/useAnalytics'
import { createConnection, deleteConnection, listConnections, syncConnection, testConnection } from '../api/connections'
import { Button, Card, Field, Pill } from '../components/ui'
import { formatUpdated } from '../format'
import { useJournal } from '../journal/JournalContext'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, spacing } from '../theme'
import type { BrokerConnection } from '../types/connections'

/**
 * Your Capital.com connection(s). The credentials are encrypted on the server and never sent back to the app.
 * Read-only ingestion: "Sync now" pulls history, balance and open positions — nothing here places an order.
 */
export function ConnectionsScreen() {
  const journal = useJournal()
  const positions = usePositionsContext()
  const [rows, setRows] = useState<BrokerConnection[]>([])
  const [encOn, setEncOn] = useState(true)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [label, setLabel] = useState('')
  const [accountId, setAccountId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isDemo, setIsDemo] = useState(false)
  const [adding, setAdding] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const res = await listConnections(controller.signal)
      if (controller.signal.aborted) return
      setEncOn(res.encryption_configured)
      setRows(res.connections ?? [])
      setError(null)
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load your connections.')
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      void load()
      return () => inFlight.current?.abort()
    }, [load]),
  )

  async function act(id: string, verb: string, fn: () => Promise<{ ok?: boolean; detail?: string }>) {
    setBusy(id)
    setNotice(null)
    setError(null)
    try {
      const r = await fn()
      const ok = r.ok !== false
      setNotice(`${verb}: ${ok ? (r.detail && r.detail !== 'synced' ? r.detail : 'OK') : (r.detail ?? 'failed')}`)
      if (verb === 'Sync' && ok) {
        clearAnalyticsCache()
        void journal.refresh()
        positions.refresh()
      }
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : `${verb} failed.`)
    } finally {
      setBusy(null)
    }
  }

  function confirmDelete(c: BrokerConnection) {
    Alert.alert('Delete this connection?', 'The stored credentials are erased from the server. Trades already synced stay in your journal.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => void act(c.id, 'Delete', () => deleteConnection(c.id).then(() => ({ ok: true }))) },
    ])
  }

  async function add() {
    setFormError(null)
    if (!accountId.trim()) return setFormError('Account ID is required.')
    if (!apiKey.trim()) return setFormError('API key is required.')
    if (!email.trim()) return setFormError('Login email is required.')
    if (!password) return setFormError('API password is required.')
    setAdding(true)
    try {
      await createConnection({ label: label.trim(), account_id: accountId.trim(), is_demo: isDemo, secret: { api_key: apiKey.trim(), email: email.trim(), password } })
      setApiKey('')
      setEmail('')
      setPassword('')
      setAccountId('')
      setLabel('')
      setNotice('Connection added. Tap Test to check the login, then Sync now.')
      await load()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not add the connection.')
    } finally {
      setAdding(false)
    }
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} />}
        >
          <Text style={styles.intro}>
            Connect your Capital.com account so your trades, balance and open positions sync in automatically. Read-only — the app can never place or change an order.
          </Text>

          {error ? <Text style={styles.error}>{error}</Text> : null}
          {notice ? <Text style={styles.notice}>{notice}</Text> : null}

          {loading ? (
            <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} />
          ) : !encOn ? (
            <Card title="Not available">
              <Text style={styles.body}>Broker connections are not switched on for this server (it has no encryption key). The person who runs the server turns this on.</Text>
            </Card>
          ) : (
            <>
              <Card title={`Your connections · ${rows.length}`}>
                {rows.length === 0 ? <Text style={styles.muted}>No connection yet — add one below.</Text> : null}
                {rows.map((c) => (
                  <View key={c.id} style={styles.conn}>
                    <View style={styles.connTop}>
                      <Text style={styles.connName} numberOfLines={1}>
                        {c.label || c.account_id || 'Capital.com'}
                      </Text>
                      <Pill text={c.is_demo ? 'DEMO' : 'LIVE'} color={c.is_demo ? colors.textSecondary : colors.accent} />
                      {c.is_active ? null : <Pill text="PAUSED" color={colors.warning} />}
                    </View>
                    <Text style={[styles.muted, c.last_sync_ok === false && { color: colors.negative }]}>
                      {c.last_sync_at ? `Last sync ${formatUpdated(c.last_sync_at)} · ${c.last_sync_ok ? 'ok' : 'failed'}` : 'Never synced'}
                      {c.last_error ? ` — ${c.last_error}` : ''}
                    </Text>
                    <View style={styles.actions}>
                      <View style={{ flex: 1 }}>
                        <Button label="Test" kind="secondary" busy={busy === c.id} disabled={busy !== null} onPress={() => void act(c.id, 'Test', () => testConnection(c.id))} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Button label="Sync now" busy={busy === c.id} disabled={busy !== null} onPress={() => void act(c.id, 'Sync', () => syncConnection(c.id))} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Button label="Delete" kind="danger" disabled={busy !== null} onPress={() => confirmDelete(c)} />
                      </View>
                    </View>
                  </View>
                ))}
              </Card>

              <Card title="Add a Capital.com connection">
                <Text style={styles.muted}>
                  In Capital.com open Settings → API, create a key, then copy the key, your login email and the API password you chose. They are encrypted before they are stored.
                </Text>
                <Field label="Label (optional)" value={label} onChangeText={setLabel} placeholder="e.g. Capital live" autoCapitalize="sentences" />
                <Field label="Account ID" value={accountId} onChangeText={setAccountId} />
                <Field label="API key" value={apiKey} onChangeText={setApiKey} secure />
                <Field label="Login email" value={email} onChangeText={setEmail} keyboardType="email-address" />
                <Field label="API password" value={password} onChangeText={setPassword} secure />
                <View style={styles.switchRow}>
                  <Text style={styles.body}>Demo account</Text>
                  <Switch value={isDemo} onValueChange={setIsDemo} trackColor={{ true: 'rgba(240,185,11,0.5)', false: colors.border }} thumbColor={isDemo ? colors.accent : colors.textMuted} />
                </View>
                {formError ? <Text style={styles.error}>{formError}</Text> : null}
                <Button label="Add connection" busy={adding} onPress={() => void add()} />
              </Card>
            </>
          )}
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
  error: { color: colors.negative, fontSize: 13 },
  notice: { color: colors.textSecondary, fontSize: 13 },
  conn: { gap: spacing.sm, paddingVertical: spacing.sm, borderTopColor: colors.borderSubtle, borderTopWidth: 1 },
  connTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  connName: { color: colors.textPrimary, fontSize: 16, fontWeight: '600', flexShrink: 1 },
  actions: { flexDirection: 'row', gap: spacing.sm },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
})
