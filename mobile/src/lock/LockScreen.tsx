import { useEffect } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { colors, radius, spacing } from '../theme'
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
        <Text style={styles.brand}>TradeLogger</Text>
        <Text style={styles.sub}>Locked</Text>
        <Pressable onPress={() => void unlock()} accessibilityRole="button" style={({ pressed }) => [styles.btn, pressed && { opacity: 0.8 }]}>
          <Text style={styles.btnText}>Unlock</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: colors.background, zIndex: 100 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.lg },
  brand: { color: colors.accent, fontSize: 34, fontWeight: '700' },
  sub: { color: colors.textMuted, fontSize: 15 },
  btn: { backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: spacing.xl * 2, paddingVertical: spacing.md + 2, marginTop: spacing.lg },
  btnText: { color: colors.background, fontSize: 16, fontWeight: '700' },
})
