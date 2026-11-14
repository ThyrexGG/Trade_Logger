import { Image } from 'expo-image'
import { useRef, useState } from 'react'
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useAuth } from '../auth/AuthContext'
import { Text, TextInput } from '../components/Text'
import { Button, Notice, ui } from '../components/ui'
import { colors, radius, spacing, type } from '../theme'

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
    <SafeAreaView style={ui.screen}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.brandBlock}>
            <Image source={require('../../assets/icon.png')} style={styles.logo} contentFit="cover" accessibilityIgnoresInvertColors />
            <Text style={styles.brand}>TradeLogger</Text>
            <Text style={styles.subtitle}>Your trading journal. Sign in to continue.</Text>
          </View>

          {notice && !error ? <Notice tone="warn">{notice}</Notice> : null}
          {error ? <Notice>{error}</Notice> : null}

          <View style={styles.field}>
            <Text style={ui.fieldLabel}>Email</Text>
            <TextInput
              style={ui.input}
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
          </View>

          <View style={styles.field}>
            <Text style={ui.fieldLabel}>Password</Text>
            <TextInput
              ref={passwordRef}
              style={ui.input}
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
          </View>

          <Button label="Sign in" onPress={() => void submit()} busy={busy} disabled={!canSubmit} style={styles.submit} />

          <Text style={styles.footnote}>No account yet? Create one at tradelogger.site. The app only signs in.</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, justifyContent: 'center', padding: spacing.xl, gap: spacing.md },
  brandBlock: { alignItems: 'center', gap: spacing.sm, marginBottom: spacing.lg },
  logo: { width: 60, height: 60, borderRadius: radius.lg + 4, marginBottom: spacing.xs },
  brand: { ...type.title, fontSize: 26, lineHeight: 32 },
  subtitle: { ...type.sub, textAlign: 'center' },
  field: { gap: 6 },
  submit: { marginTop: spacing.sm },
  footnote: { ...type.small, textAlign: 'center', marginTop: spacing.md },
})
