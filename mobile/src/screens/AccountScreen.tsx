import { useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { sendTestPush } from '../api/push'
import { getSyncStatus, setSyncAuto } from '../api/system'
import { API_BASE_URL } from '../config'
import { useAuth } from '../auth/AuthContext'
import { useHealth } from '../HealthContext'
import { useLock } from '../lock/LockContext'
import { disablePush, enablePush, isPushEnabled, unregisterStoredToken } from '../push/push'
import { colors, radius, spacing } from '../theme'
import type { HealthState } from '../useApiHealth'

const PILL: Record<HealthState, { label: string; color: string }> = {
  checking: { label: 'Checking…', color: colors.warning },
  connected: { label: 'API connected', color: colors.positive },
  unreachable: { label: 'API unreachable', color: colors.negative },
}

export function AccountScreen() {
  const { user, signOut } = useAuth()
  const { state, health, latencyMs, recheck } = useHealth()
  const lock = useLock()
  const [lockError, setLockError] = useState<string | null>(null)
  const pill = PILL[state]

  const [pushOn, setPushOn] = useState(false)
  const [pushBusy, setPushBusy] = useState(false)
  const [pushMsg, setPushMsg] = useState<{ text: string; ok: boolean } | null>(null)

  useEffect(() => {
    void isPushEnabled().then(setPushOn)
  }, [])

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
      setPushMsg(
        r.sent > 0
          ? { text: 'Sent — it should arrive in a few seconds.', ok: true }
          : { text: r.error ?? 'Nothing was delivered.', ok: false },
      )
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
    <SafeAreaView style={styles.screen} edges={['top']}>
      <ScrollView contentContainerStyle={styles.center} showsVerticalScrollIndicator={false}>
        <Text style={styles.brand}>TradeLogger</Text>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Signed in as</Text>
          <Text style={styles.email}>{user?.email ?? 'Unknown'}</Text>
          {user?.role === 'owner' ? <Text style={styles.role}>Owner</Text> : null}
        </View>

        <View style={styles.lockCard}>
          <View style={styles.lockText}>
            <Text style={styles.lockTitle}>Lock the app</Text>
            <Text style={styles.lockSub}>
              {lock.available
                ? 'Ask for Face ID / fingerprint / passcode when you open TradeLogger.'
                : 'Set up a screen lock or biometrics on your phone to use this.'}
            </Text>
          </View>
          <Switch
            value={lock.enabled}
            onValueChange={(v) => void toggleLock(v)}
            disabled={!lock.available}
            trackColor={{ true: colors.accent, false: colors.surfaceElevated }}
            thumbColor="#ffffff"
          />
        </View>
        {lockError ? <Text style={styles.lockError}>{lockError}</Text> : null}

        <View style={styles.lockCard}>
          <View style={styles.lockText}>
            <Text style={styles.lockTitle}>Trade alerts</Text>
            <Text style={styles.lockSub}>A notification when a trade opens or closes, with the P&L.</Text>
          </View>
          {pushBusy ? (
            <ActivityIndicator color={colors.accent} />
          ) : (
            <Switch
              value={pushOn}
              onValueChange={(v) => void togglePush(v)}
              trackColor={{ true: colors.accent, false: colors.surfaceElevated }}
              thumbColor="#ffffff"
            />
          )}
        </View>
        {pushOn ? (
          <Pressable onPress={() => void testPush()} disabled={pushBusy} accessibilityRole="button" style={styles.testBtn}>
            <Text style={styles.testText}>Send a test notification</Text>
          </Pressable>
        ) : null}
        {pushMsg ? <Text style={[styles.lockError, pushMsg.ok && { color: colors.positive }]}>{pushMsg.text}</Text> : null}

        <Pressable onPress={recheck} accessibilityRole="button" accessibilityLabel="Recheck API connection">
          <View style={[styles.pill, { borderColor: pill.color }]}>
            <View style={[styles.dot, { backgroundColor: pill.color }]} />
            <Text style={[styles.pillText, { color: pill.color }]}>
              {pill.label}
              {latencyMs != null && state === 'connected' ? ` · ${latencyMs} ms` : ''}
            </Text>
          </View>
        </Pressable>
        <Text style={styles.hint}>
          {API_BASE_URL.replace('https://', '')} · v{health?.version ?? '—'}
        </Text>

        <Pressable
          onPress={() => void unregisterStoredToken().finally(() => signOut())}
          accessibilityRole="button"
          style={({ pressed }) => [styles.logout, pressed && { opacity: 0.7 }]}
        >
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  center: { flexGrow: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.lg },
  brand: { color: colors.accent, fontSize: 34, fontWeight: '700' },
  card: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.xs,
    alignItems: 'center',
  },
  cardLabel: { color: colors.textMuted, fontSize: 12 },
  email: { color: colors.textPrimary, fontSize: 18, fontWeight: '600' },
  role: { color: colors.accent, fontSize: 12, fontWeight: '600' },
  lockCard: {
    alignSelf: 'stretch',
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  lockText: { flex: 1, gap: 2 },
  lockTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  lockSub: { color: colors.textMuted, fontSize: 12 },
  testBtn: { borderColor: 'rgba(240,185,11,0.4)', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm + 2 },
  testText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  lockError: { color: colors.negative, fontSize: 12, marginTop: -spacing.sm },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  pillText: { fontSize: 14, fontWeight: '600' },
  hint: { color: colors.textMuted, fontSize: 12 },
  logout: {
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    marginTop: spacing.lg,
  },
  logoutText: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
})
