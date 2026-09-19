import { Pressable, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { API_BASE_URL } from '../config'
import { useAuth } from '../auth/AuthContext'
import { colors, radius, spacing } from '../theme'
import { useApiHealth, type HealthState } from '../useApiHealth'

const PILL: Record<HealthState, { label: string; color: string }> = {
  checking: { label: 'Checking…', color: colors.warning },
  connected: { label: 'API connected', color: colors.positive },
  unreachable: { label: 'API unreachable', color: colors.negative },
}

/** Temporary signed-in landing screen; M3 replaces it with the Positions / Journal tabs. */
export function HomeScreen() {
  const { user, signOut } = useAuth()
  const { state, health, latencyMs, recheck } = useApiHealth()
  const pill = PILL[state]

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.center}>
        <Text style={styles.brand}>TradeLogger</Text>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Signed in as</Text>
          <Text style={styles.email}>{user?.email ?? 'Unknown'}</Text>
          {user?.role === 'owner' ? <Text style={styles.role}>Owner</Text> : null}
        </View>

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
          onPress={() => void signOut()}
          accessibilityRole="button"
          style={({ pressed }) => [styles.logout, pressed && { opacity: 0.7 }]}
        >
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
        <Text style={styles.hint}>Mobile plan · step M2</Text>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.lg, gap: spacing.lg },
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
