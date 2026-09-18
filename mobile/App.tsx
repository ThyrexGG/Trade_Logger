import { StatusBar } from 'expo-status-bar'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { API_BASE_URL } from './src/config'
import { colors, radius, spacing } from './src/theme'
import { useApiHealth, type HealthState } from './src/useApiHealth'

const PILL: Record<HealthState, { label: string; color: string }> = {
  checking: { label: 'Checking…', color: colors.warning },
  connected: { label: 'API connected', color: colors.positive },
  unreachable: { label: 'API unreachable', color: colors.negative },
}

export default function App() {
  const { state, health, latencyMs, recheck } = useApiHealth()
  const pill = PILL[state]

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      <View style={styles.center}>
        <Text style={styles.brand}>TradeLogger</Text>
        <Text style={styles.tagline}>Your trades, in your pocket.</Text>

        <Pressable onPress={recheck} accessibilityRole="button" accessibilityLabel="Recheck API connection">
          <View style={[styles.pill, { borderColor: pill.color }]}>
            <View style={[styles.dot, { backgroundColor: pill.color }]} />
            <Text style={[styles.pillText, { color: pill.color }]}>{pill.label}</Text>
          </View>
        </Pressable>

        <View style={styles.card}>
          <Row label="Server" value={API_BASE_URL.replace('https://', '')} />
          <Row label="Version" value={health?.version ?? '—'} />
          <Row label="Status" value={health?.status ?? '—'} />
          <Row label="Live orders" value={health?.live_broker_transmission ?? '—'} />
          <Row label="Response" value={latencyMs != null ? `${latencyMs} ms` : '—'} last />
        </View>
        <Text style={styles.hint}>Tap the pill to recheck. Mobile plan · step M1.</Text>
      </View>
    </SafeAreaView>
  )
}

function Row({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.row, !last && styles.rowBorder]}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue} numberOfLines={1}>
        {value}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    gap: spacing.lg,
  },
  brand: { color: colors.accent, fontSize: 34, fontWeight: '700', letterSpacing: 0.5 },
  tagline: { color: colors.textSecondary, fontSize: 15, marginTop: -spacing.md },
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
  card: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.md,
    gap: spacing.lg,
  },
  rowBorder: { borderBottomColor: colors.borderSubtle, borderBottomWidth: 1 },
  rowLabel: { color: colors.textMuted, fontSize: 13 },
  rowValue: { color: colors.textPrimary, fontSize: 13, flexShrink: 1, fontVariant: ['tabular-nums'] },
  hint: { color: colors.textMuted, fontSize: 12 },
})
