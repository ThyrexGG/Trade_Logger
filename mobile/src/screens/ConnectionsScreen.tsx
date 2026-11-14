import { useFocusEffect } from '@react-navigation/native'
import { useCallback, useRef, useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { clearAnalyticsCache } from '../analytics/useAnalytics'
import { createConnection, deleteConnection, listConnections, syncConnection, testConnection } from '../api/connections'
import { Text } from '../components/Text'
import { Button, Card, Divider, Empty, Field, Loading, Notice, Pill, ToggleRow, ui } from '../components/ui'
import { formatUpdated } from '../format'
import { useJournal } from '../journal/JournalContext'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, spacing, type } from '../theme'
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
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={ui.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} tintColor={colors.accent} colors={[colors.accent]} />}
        >
          <Text style={ui.muted}>Connect your Capital.com account so your trades, balance and open positions come in on their own. Read-only: the app can never place or change an order.</Text>

          {error ? <Notice>{error}</Notice> : null}
          {notice ? <Notice tone="info">{notice}</Notice> : null}

          {loading ? (
            <Loading />
          ) : !encOn ? (
            <Empty icon="lock-closed-outline" title="Not available on this server" text="Broker connections are switched off here (the server has no encryption key). The person who runs the server turns this on." />
          ) : (
            <>
              <Card title="Your connections" right={String(rows.length)} flush>
                {rows.length === 0 ? <Text style={styles.quiet}>No connection yet. Add one below.</Text> : null}
                {rows.map((c, i) => (
                  <View key={c.id}>
                    {i > 0 ? <Divider /> : null}
                    <View style={styles.conn}>
                      <View style={ui.rowWrap}>
                        <Text style={styles.connName} numberOfLines={1}>
                          {c.label || c.account_id || 'Capital.com'}
                        </Text>
                        <Pill text={c.is_demo ? 'Demo' : 'Live'} color={c.is_demo ? colors.textSecondary : colors.accent} />
                        {c.is_active ? null : <Pill text="Paused" color={colors.warning} />}
                      </View>
                      <Text style={[ui.muted, c.last_sync_ok === false && { color: colors.negative }]}>
                        {c.last_sync_at ? `Last sync ${formatUpdated(c.last_sync_at)} · ${c.last_sync_ok ? 'ok' : 'failed'}` : 'Never synced'}
                        {c.last_error ? `. ${c.last_error}` : ''}
                      </Text>
                      <View style={styles.actions}>
                        <Button label="Sync now" size="sm" busy={busy === c.id} disabled={busy !== null} onPress={() => void act(c.id, 'Sync', () => syncConnection(c.id))} style={ui.flex} />
                        <Button label="Test" size="sm" kind="secondary" disabled={busy !== null} onPress={() => void act(c.id, 'Test', () => testConnection(c.id))} style={ui.flex} />
                        <Button label="Delete" size="sm" kind="danger" disabled={busy !== null} onPress={() => confirmDelete(c)} style={ui.flex} />
                      </View>
                    </View>
                  </View>
                ))}
              </Card>

              <Card title="Add a Capital.com connection">
                <Text style={ui.muted}>In Capital.com open Settings, then API, and create a key. Copy the key, your login email and the API password you chose. They are encrypted before they are stored.</Text>
                <Field label="Label (optional)" value={label} onChangeText={setLabel} placeholder="e.g. Capital live" autoCapitalize="sentences" />
                <Field label="Account ID" value={accountId} onChangeText={setAccountId} />
                <Field label="API key" value={apiKey} onChangeText={setApiKey} secure />
                <Field label="Login email" value={email} onChangeText={setEmail} keyboardType="email-address" />
                <Field label="API password" value={password} onChangeText={setPassword} secure />
                <View style={styles.demo}>
                  <ToggleRow title="Demo account" sub="Turn on if this key is for a practice account" value={isDemo} onChange={setIsDemo} />
                </View>
                {formError ? <Notice>{formError}</Notice> : null}
                <Button label="Add connection" kind={rows.length === 0 ? 'primary' : 'secondary'} busy={adding} onPress={() => void add()} />
              </Card>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  quiet: { ...type.small, fontSize: 13, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  conn: { gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  connName: { ...type.heading, flexShrink: 1 },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  // the switch row brings its own side padding; pull it back to the card's edge
  demo: { marginHorizontal: -spacing.lg },
})
