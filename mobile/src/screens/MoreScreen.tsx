import { Ionicons } from '@expo/vector-icons'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useAuth } from '../auth/AuthContext'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'

type Row = {
  route: keyof RootStackParamList
  icon: keyof typeof Ionicons.glyphMap
  title: string
  sub: string
}

/** Everything that doesn't get its own tab. New phone features are added here as they're built. */
const ROWS: Row[] = [
  { route: 'PriceAlerts', icon: 'notifications-outline', title: 'Price alerts', sub: 'Get told when a price crosses your level' },
  { route: 'Killzone', icon: 'radio-outline', title: 'Killzone scanner', sub: 'Liquidity sweeps + structure shifts, by session' },
  { route: 'Assistant', icon: 'sparkles-outline', title: 'AI assistant', sub: 'Ask questions about your trading (read-only)' },
  { route: 'RiskGateway', icon: 'shield-checkmark-outline', title: 'Risk gateway', sub: 'Position size from entry, stop and risk %' },
  { route: 'ManualTrade', icon: 'add-circle-outline', title: 'Log a trade', sub: 'Record a trade taken outside a synced broker' },
  { route: 'Account', icon: 'person-circle-outline', title: 'Account & alerts', sub: 'Auto-sync, trade alerts, app lock, log out' },
]

export function MoreScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { user } = useAuth()
  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>More</Text>
        {user?.email ? <Text style={styles.email}>{user.email}</Text> : null}
        <View style={styles.list}>
          {ROWS.map((r) => (
            <Pressable
              key={r.route}
              onPress={() => navigation.navigate(r.route as never)}
              style={({ pressed }) => [styles.row, pressed && { opacity: 0.75 }]}
              accessibilityRole="button"
            >
              <Ionicons name={r.icon} size={24} color={colors.accent} />
              <View style={styles.rowText}>
                <Text style={styles.rowTitle}>{r.title}</Text>
                <Text style={styles.rowSub}>{r.sub}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.sm },
  title: { color: colors.textPrimary, fontSize: 22, fontWeight: '700' },
  email: { color: colors.textMuted, fontSize: 13 },
  list: { gap: spacing.sm, marginTop: spacing.md },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  rowText: { flex: 1 },
  rowTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  rowSub: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
})
