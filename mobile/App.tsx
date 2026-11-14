import { Geist_400Regular, Geist_500Medium, Geist_600SemiBold } from '@expo-google-fonts/geist'
import { GeistMono_400Regular, GeistMono_500Medium, GeistMono_600SemiBold } from '@expo-google-fonts/geist-mono'
import { DarkTheme, NavigationContainer, type Theme } from '@react-navigation/native'
import { useFonts } from 'expo-font'
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
import { flushPendingNavigation, navigationRef } from './src/navigation/ref'
import { RootStack } from './src/navigation/RootStack'
import { PositionsProvider } from './src/positions/PositionsContext'
import { PushBridge } from './src/push/PushBridge'
import { LoginScreen } from './src/screens/LoginScreen'
import { colors, fonts } from './src/theme'

// Keep the branded splash up until we know whether the user is signed in / locked.
void SplashScreen.preventAutoHideAsync().catch(() => {})

const navTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.background,
    text: colors.textPrimary,
    border: colors.borderSubtle,
    primary: colors.accent,
  },
  // navigation's own text (headers, tab labels) in Geist too; each weight is its own font file
  fonts: {
    regular: { fontFamily: fonts.sans, fontWeight: 'normal' },
    medium: { fontFamily: fonts.sansMedium, fontWeight: 'normal' },
    bold: { fontFamily: fonts.sansSemi, fontWeight: 'normal' },
    heavy: { fontFamily: fonts.sansSemi, fontWeight: 'normal' },
  },
}

function Root({ fontsReady }: { fontsReady: boolean }) {
  const { status } = useAuth()
  const lock = useLock()
  const booting = status === 'loading' || !lock.ready || !fontsReady

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
          <NavigationContainer theme={navTheme} ref={navigationRef} onReady={flushPendingNavigation}>
            <RootStack />
          </NavigationContainer>
          <PushBridge />
        </JournalProvider>
      </PositionsProvider>
      {/* Overlay (not a replacement) so screens keep their state while locked. */}
      {lock.locked ? <LockScreen /> : null}
    </HealthProvider>
  )
}

export default function App() {
  // Geist + Geist Mono (the web app's fonts). The splash stays up until they are in, so text never
  // flashes in the system font; if loading fails the app still opens, in the system font.
  const [fontsLoaded, fontError] = useFonts({
    Geist_400Regular,
    Geist_500Medium,
    Geist_600SemiBold,
    GeistMono_400Regular,
    GeistMono_500Medium,
    GeistMono_600SemiBold,
  })
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <AuthProvider>
        <LockProvider>
          <Root fontsReady={fontsLoaded || fontError != null} />
        </LockProvider>
      </AuthProvider>
    </SafeAreaProvider>
  )
}

const styles = StyleSheet.create({
  loading: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
})
