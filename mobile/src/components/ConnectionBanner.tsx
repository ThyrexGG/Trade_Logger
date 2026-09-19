import { Pressable, StyleSheet, Text } from 'react-native'
import { useHealth } from '../HealthContext'
import { colors, radius, spacing } from '../theme'

/** Shown only when the server can't be reached — tells the user the screen is showing saved data. */
export function ConnectionBanner() {
  const { state, recheck } = useHealth()
  if (state !== 'unreachable') return null
  return (
    <Pressable onPress={recheck} accessibilityRole="button" accessibilityLabel="Retry connection" style={styles.banner}>
      <Text style={styles.text}>Can't reach the server — showing the last data we loaded. Tap to retry.</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: 'rgba(239,68,68,0.12)',
    borderColor: 'rgba(239,68,68,0.35)',
    borderWidth: 1,
    borderRadius: radius.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
  },
  text: { color: colors.negative, fontSize: 12 },
})
