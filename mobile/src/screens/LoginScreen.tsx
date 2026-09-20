import { useRef, useState } from 'react'
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useAuth } from '../auth/AuthContext'
import { colors, radius, spacing } from '../theme'

export function LoginScreen() {
  const { signIn, notice } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const passwordRef = useRef<TextInput>(null)

  const canSubmit = email.trim().length > 0 && password.length > 0 && !busy

  async function submit() {
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      await signIn(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.')
      setBusy(false)
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.brand}>TradeLogger</Text>
          <Text style={styles.subtitle}>Sign in to your account</Text>

          {notice && !error ? <Text style={styles.notice}>{notice}</Text> : null}
          {error ? (
            <Text style={styles.error} accessibilityRole="alert">
              {error}
            </Text>
          ) : null}

          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoComplete="email"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="username"
            returnKeyType="next"
            editable={!busy}
            onSubmitEditing={() => passwordRef.current?.focus()}
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            ref={passwordRef}
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            placeholder="Your password"
            placeholderTextColor={colors.textMuted}
            secureTextEntry
            autoCapitalize="none"
            autoComplete="current-password"
            textContentType="password"
            returnKeyType="go"
            editable={!busy}
            onSubmitEditing={submit}
          />

          <Pressable
            onPress={submit}
            disabled={!canSubmit}
            accessibilityRole="button"
            style={({ pressed }) => [styles.button, !canSubmit && styles.buttonDisabled, pressed && styles.buttonPressed]}
          >
            {busy ? <ActivityIndicator color={colors.background} /> : <Text style={styles.buttonText}>Sign in</Text>}
          </Pressable>

          <Text style={styles.footnote}>
            No account yet? Accounts are created at tradelogger.site — the app only signs in.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { flexGrow: 1, justifyContent: 'center', padding: spacing.xl, gap: spacing.sm },
  brand: { color: colors.accent, fontSize: 34, fontWeight: '700', textAlign: 'center' },
  subtitle: { color: colors.textSecondary, fontSize: 15, textAlign: 'center', marginBottom: spacing.xl },
  notice: {
    color: colors.warning,
    backgroundColor: 'rgba(245,158,11,0.1)',
    borderColor: 'rgba(245,158,11,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
  error: {
    color: colors.negative,
    backgroundColor: 'rgba(239,68,68,0.1)',
    borderColor: 'rgba(239,68,68,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
  label: { color: colors.textMuted, fontSize: 12, marginTop: spacing.sm },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    color: colors.textPrimary,
    fontSize: 16,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md + 2,
    alignItems: 'center',
    marginTop: spacing.xl,
  },
  buttonDisabled: { opacity: 0.4 },
  buttonPressed: { opacity: 0.8 },
  buttonText: { color: colors.background, fontSize: 16, fontWeight: '700' },
  footnote: { color: colors.textMuted, fontSize: 12, textAlign: 'center', marginTop: spacing.xl },
})
