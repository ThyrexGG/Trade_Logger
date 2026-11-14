import { Ionicons } from '@expo/vector-icons'
import { useEffect } from 'react'
import { StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Text } from '../components/Text'
import { Button } from '../components/ui'
import { colors, radius, spacing, type } from '../theme'
import { useLock } from './LockContext'

/** Covers the app while locked; prompts for Face ID / fingerprint / passcode as soon as it appears. */
export function LockScreen() {
  const { unlock } = useLock()

  useEffect(() => {
    void unlock()
  }, [unlock])

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.center}>
        <View style={styles.icon}>
          <Ionicons name="lock-closed-outline" size={22} color={colors.textSecondary} />
        </View>
        <Text style={styles.brand}>TradeLogger is locked</Text>
        <Text style={styles.sub}>Unlock to see your trades.</Text>
        <Button label="Unlock" icon="finger-print-outline" onPress={() => void unlock()} style={styles.btn} />
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: colors.background, zIndex: 100 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.sm, padding: spacing.xl },
  icon: { width: 52, height: 52, borderRadius: radius.lg, backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.sm },
  brand: { ...type.title, fontSize: 20, lineHeight: 26 },
  sub: { ...type.sub },
  btn: { marginTop: spacing.lg, minWidth: 180 },
})
