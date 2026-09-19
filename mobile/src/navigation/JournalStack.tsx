import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { JournalScreen } from '../screens/JournalScreen'
import { TradeDetailScreen } from '../screens/TradeDetailScreen'
import { colors } from '../theme'

export type JournalStackParamList = {
  JournalList: undefined
  TradeDetail: { tradeId: string }
}

const Stack = createNativeStackNavigator<JournalStackParamList>()

export function JournalStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.accent,
        headerTitleStyle: { color: colors.textPrimary },
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="JournalList" component={JournalScreen} options={{ headerShown: false }} />
      <Stack.Screen name="TradeDetail" component={TradeDetailScreen} options={{ title: 'Trade', headerBackTitle: 'Journal' }} />
    </Stack.Navigator>
  )
}
