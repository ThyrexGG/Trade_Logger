import type { ReactNode } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, type KeyboardTypeOptions, type StyleProp, type ViewStyle } from 'react-native'
import { colors, radius, spacing } from '../theme'

/** Small building blocks shared by the newer screens (connections, limits, challenge, chart analyzer). */

export function Card({ title, right, children, style }: { title?: string; right?: string; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.card, style]}>
      {title ? (
        <View style={styles.cardHead}>
          <Text style={styles.cardTitle}>{title}</Text>
          {right ? <Text style={styles.cardRight}>{right}</Text> : null}
        </View>
      ) : null}
      {children}
    </View>
  )
}

export function Pill({ text, color }: { text: string; color: string }) {
  return (
    <View style={[styles.pill, { borderColor: color }]}>
      <Text style={[styles.pillText, { color }]}>{text}</Text>
    </View>
  )
}

/** A budget bar: green while comfortable, amber from 80% of the limit, red once it is reached. */
export function Bar({ ratio, warnAt = 0.8 }: { ratio: number | null | undefined; warnAt?: number }) {
  const r = Math.max(0, Math.min(1, ratio ?? 0))
  const color = r >= 1 ? colors.negative : r >= warnAt ? colors.warning : colors.positive
  return (
    <View style={styles.barTrack} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(r * 100) }}>
      <View style={[styles.barFill, { width: `${r * 100}%`, backgroundColor: color }]} />
    </View>
  )
}

export function Button({
  label,
  onPress,
  busy,
  disabled,
  kind = 'primary',
}: {
  label: string
  onPress: () => void
  busy?: boolean
  disabled?: boolean
  kind?: 'primary' | 'secondary' | 'danger'
}) {
  const off = busy || disabled
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      style={[styles.btn, kind === 'primary' ? styles.btnPrimary : kind === 'danger' ? styles.btnDanger : styles.btnSecondary, off && { opacity: 0.55 }]}
    >
      {busy ? (
        <ActivityIndicator color={kind === 'primary' ? '#000' : kind === 'danger' ? colors.negative : colors.accent} />
      ) : (
        <Text style={[styles.btnText, kind === 'primary' ? { color: '#000' } : kind === 'danger' ? { color: colors.negative } : { color: colors.accent }]}>{label}</Text>
      )}
    </Pressable>
  )
}

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  secure,
  half,
  autoCapitalize = 'none',
  hint,
}: {
  label: string
  value: string
  onChangeText: (t: string) => void
  placeholder?: string
  keyboardType?: KeyboardTypeOptions
  secure?: boolean
  half?: boolean
  autoCapitalize?: 'none' | 'characters' | 'sentences'
  hint?: string
}) {
  return (
    <View style={[styles.field, half && { flex: 1 }]}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        keyboardType={keyboardType}
        secureTextEntry={secure}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
        autoComplete="off"
        style={styles.input}
      />
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  )
}

/** "12.5" -> 12.5, "" -> null, junk -> NaN (so the caller can tell "empty" from "invalid"). */
export function parseNum(s: string): number | null {
  const t = s.trim().replace(/,/g, '')
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? n : NaN
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  cardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  cardRight: { color: colors.textMuted, fontSize: 11 },
  pill: { borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 7, paddingVertical: 2 },
  pillText: { fontSize: 11, fontWeight: '700' },
  barTrack: { height: 8, borderRadius: radius.pill, backgroundColor: colors.surfaceElevated, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: radius.pill },
  btn: { borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.md, paddingHorizontal: spacing.lg, borderWidth: 1 },
  btnPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  btnSecondary: { backgroundColor: 'rgba(240,185,11,0.1)', borderColor: 'rgba(240,185,11,0.5)' },
  btnDanger: { backgroundColor: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.5)' },
  btnText: { fontWeight: '700', fontSize: 14 },
  field: { gap: 4 },
  label: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6 },
  input: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    color: colors.textPrimary,
    fontSize: 15,
  },
  hint: { color: colors.textMuted, fontSize: 11 },
})
