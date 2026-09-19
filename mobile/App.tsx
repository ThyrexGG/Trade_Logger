import { DarkTheme, NavigationContainer, type Theme } from '@react-navigation/native'
import { StatusBar } from 'expo-status-bar'
import { ActivityIndicator, StyleSheet, View } from 'react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AuthProvider, useAuth } from './src/auth/AuthContext'
import { JournalProvider } from './src/journal/JournalContext'
import { AppTabs } from './src/navigation/AppTabs'
import { PositionsProvider } from './src/positions/PositionsContext'
import { LoginScreen } from './src/screens/LoginScreen'
import { colors } from './src/theme'

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
  if (status === 'loading') {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    )
  }
  if (status !== 'signedIn') return <LoginScreen />
  return (
    <PositionsProvider>
      <JournalProvider>
        <NavigationContainer theme={navTheme}>
          <AppTabs />
        </NavigationContainer>
      </JournalProvider>
    </PositionsProvider>
  )
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <AuthProvider>
        <Root />
      </AuthProvider>
    </SafeAreaProvider>
  )
}

const styles = StyleSheet.create({
  loading: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
})
