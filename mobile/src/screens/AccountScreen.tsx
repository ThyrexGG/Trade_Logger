import { useEffect, useState, type ReactNode } from 'react'
import { ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { sendTestPush } from '../api/push'
import { getSyncStatus, setSyncAuto } from '../api/system'
import { API_BASE_URL } from '../config'
import { useAuth } from '../auth/AuthContext'
import { Text } from '../components/Text'
import { Button, Card, Divider, Fact, Footnote, Notice, Row, Rows, SectionLabel, ToggleRow, ui } from '../components/ui'
import { useHealth } from '../HealthContext'
import { useLock } from '../lock/LockContext'
import { disablePush, enablePush, isPushEnabled, unregisterStoredToken } from '../push/push'
import { colors, spacing, type } from '../theme'
import type { HealthState } from '../useApiHealth'

const HEALTH: Record<HealthState, { label: string; color: string }> = {
  checking: { label: 'Checking…', color: colors.warning },
  connected: { label: 'Connected', color: colors.positive },
  unreachable: { label: 'Can’t reach the server', color: colors.negative },
}

function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <SectionLabel>{label}</SectionLabel>
      {children}
    </>
  )
}

export function AccountScreen() {
  const { user, signOut } = useAuth()
  const { state, health, latencyMs, recheck } = useHealth()
  const lock = useLock()
  const [lockError, setLockError] = useState<string | null>(null)
  const status = HEALTH[state]

  const [pushOn, setPushOn] = useState(false)
  const [pushBusy, setPushBusy] = useState(false)
  const [pushMsg, setPushMsg] = useState<{ text: string; ok: boolean } | null>(null)

  // The server's background sync is what notices a new trade, so alerts need it on.
  const [autoOn, setAutoOn] = useState<boolean | null>(null)
  const [autoBusy, setAutoBusy] = useState(false)
  const [autoError, setAutoError] = useState<string | null>(null)

  useEffect(() => {
    void isPushEnabled().then(setPushOn)
    getSyncStatus()
      .then((st) => setAutoOn(!!st.auto_enabled))
      .catch(() => setAutoOn(null))
  }, [])

  async function toggleAuto(on: boolean) {
    setAutoBusy(true)
    setAutoError(null)
    try {
      const st = await setSyncAuto(on)
      setAutoOn(!!st.auto_enabled)
    } catch (err) {
      setAutoError(err instanceof Error ? err.message : 'Could not change auto-sync.')
    }
    setAutoBusy(false)
  }

  async function togglePush(on: boolean) {
    setPushBusy(true)
    setPushMsg(null)
    if (on) {
      const r = await enablePush()
      setPushOn(r.ok)
      setPushMsg(r.ok ? { text: 'Trade alerts are on for this phone.', ok: true } : { text: r.message ?? 'Could not turn on alerts.', ok: false })
    } else {
      await disablePush()
      setPushOn(false)
    }
    setPushBusy(false)
  }

  async function testPush() {
    setPushBusy(true)
    setPushMsg(null)
    try {
      const r = await sendTestPush()
      setPushMsg(r.sent > 0 ? { text: 'Sent. It should arrive in a few seconds.', ok: true } : { text: r.error ?? 'Nothing was delivered.', ok: false })
    } catch (err) {
      setPushMsg({ text: err instanceof Error ? err.message : 'Test failed.', ok: false })
    }
    setPushBusy(false)
  }

  async function toggleLock(on: boolean) {
    setLockError(null)
    setLockError(await lock.setEnabled(on))
  }

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <ScrollView contentContainerStyle={ui.content} showsVerticalScrollIndicator={false}>
        <Card>
          <Text style={styles.label}>Signed in as</Text>
          <Text style={styles.email} numberOfLines={1}>
            {user?.email ?? 'Unknown'}
          </Text>
          {user?.role === 'owner' ? <Text style={ui.muted}>Owner account</Text> : null}
        </Card>

        <Group label="Trades">
          <Card flush>
            <ToggleRow
              title="Auto-sync trades"
              sub={autoOn === null ? 'Checking the server…' : 'The server checks your broker every couple of minutes, so new trades show up on their own.'}
              value={autoOn === true}
              onChange={(v) => void toggleAuto(v)}
              disabled={autoOn === null}
              busy={autoBusy}
            />
            <Divider inset={spacing.lg} />
            <ToggleRow title="Trade alerts" sub="A notification when a trade opens or closes, with the P&L." value={pushOn} onChange={(v) => void togglePush(v)} busy={pushBusy} />
            {pushOn ? (
              <View style={styles.inlineAction}>
                <Button label="Send a test notification" kind="secondary" size="sm" disabled={pushBusy} onPress={() => void testPush()} />
              </View>
            ) : null}
          </Card>
          {autoError ? <Notice>{autoError}</Notice> : null}
          {pushOn && autoOn === false ? <Notice tone="warn">Auto-sync is off, so alerts only fire after you tap Sync. Turn on Auto-sync trades above.</Notice> : null}
          {pushMsg ? <Notice tone={pushMsg.ok ? 'ok' : 'error'}>{pushMsg.text}</Notice> : null}
        </Group>

        <Group label="Privacy">
          <Card flush>
            <ToggleRow
              title="Lock the app"
              sub={lock.available ? 'Ask for Face ID, fingerprint or passcode when you open TradeLogger.' : 'Set up a screen lock or biometrics on your phone to use this.'}
              value={lock.enabled}
              onChange={(v) => void toggleLock(v)}
              disabled={!lock.available}
            />
          </Card>
          {lockError ? <Notice>{lockError}</Notice> : null}
        </Group>

        <Group label="Connection">
          <Card flush>
            <Rows inset={0}>
              <Row onPress={recheck} right={<Text style={ui.muted}>Check again</Text>}>
                <View style={ui.row}>
                  <View style={[styles.dot, { backgroundColor: status.color }]} />
                  <Text style={styles.toggleTitle}>{status.label}</Text>
                </View>
              </Row>
              {latencyMs != null && state === 'connected' ? <Fact label="Response time" value={`${latencyMs} ms`} /> : null}
              <Fact label="Server" value={API_BASE_URL.replace('https://', '')} />
              <Fact label="Version" value={health?.version ?? '—'} />
            </Rows>
          </Card>
        </Group>

        <Button label="Log out" kind="secondary" icon="log-out-outline" onPress={() => void unregisterStoredToken().finally(() => signOut())} style={styles.logout} />
        <Footnote>Read-only toward your broker. The app never places, changes or closes a trade.</Footnote>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  label: { ...type.label },
  email: { ...type.heading, fontSize: 17, lineHeight: 22 },
  toggleTitle: { ...type.heading, fontWeight: '500' },
  inlineAction: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md, alignItems: 'flex-start' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  logout: { marginTop: spacing.md },
})
