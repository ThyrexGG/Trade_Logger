import { DarkTheme, NavigationContainer, type Theme } from '@react-navigation/native'
import * as SplashScreen from 'expo-splash-screen'
import { StatusBar } from 'expo-status-bar'
import { useEffect } from 'react'
import { ActivityIndicator, StyleSheet, View } from 'react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AuthProvider, useAuth } from './src/auth/AuthContext'
import { HealthProvider } from './src/HealthContext'
import { JournalProvider } from './src/journal/JournalContext'
import { LockProvider, useLock } from './src/lock/LockContext'
import { LockScreen } from './src/lock/LockScreen'
import { RootStack } from './src/navigation/RootStack'
import { PositionsProvider } from './src/positions/PositionsContext'
import { LoginScreen } from './src/screens/LoginScreen'
import { colors } from './src/theme'

// Keep the branded splash up until we know whether the user is signed in / locked.
void SplashScreen.preventAutoHideAsync().catch(() => {})

const navTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    text: colors.textPrimary,
    border: colors.borderSubtle,
    primary: colors.accent,
  },
}

function Root() {
  const { status } = useAuth()
  const lock = useLock()
  const booting = status === 'loading' || !lock.ready

  useEffect(() => {
    if (!booting) void SplashScreen.hideAsync().catch(() => {})
  }, [booting])

  // Signing out clears any pending lock so the next sign-in isn't gated behind Face ID.
  const { clearLocked } = lock
  useEffect(() => {
    if (status === 'signedOut') clearLocked()
  }, [status, clearLocked])

  if (booting) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    )
  }
  if (status !== 'signedIn') return <LoginScreen />
  return (
    <HealthProvider>
      <PositionsProvider>
        <JournalProvider>
          <NavigationContainer theme={navTheme}>
            <RootStack />
          </NavigationContainer>
        </JournalProvider>
      </PositionsProvider>
      {/* Overlay (not a replacement) so screens keep their state while locked. */}
      {lock.locked ? <LockScreen /> : null}
    </HealthProvider>
  )
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <AuthProvider>
        <LockProvider>
          <Root />
        </LockProvider>
      </AuthProvider>
    </SafeAreaProvider>
  )
}

const styles = StyleSheet.create({
  loading: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
})
