import { StatusBar } from 'expo-status-bar'
import { ActivityIndicator, StyleSheet, View } from 'react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AuthProvider, useAuth } from './src/auth/AuthContext'
import { HomeScreen } from './src/screens/HomeScreen'
import { LoginScreen } from './src/screens/LoginScreen'
import { colors } from './src/theme'

function Root() {
  const { status } = useAuth()
  if (status === 'loading') {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    )
  }
  return status === 'signedIn' ? <HomeScreen /> : <LoginScreen />
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
