import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { EntriesScreen } from '../screens/EntriesScreen'
import { EntryScreen } from '../screens/EntryScreen'
import { PositionDetailScreen } from '../screens/PositionDetailScreen'
import { TradeDetailScreen } from '../screens/TradeDetailScreen'
import { colors } from '../theme'
import type { JournalEntry } from '../types/entries'
import { AppTabs } from './AppTabs'

export type RootStackParamList = {
  Tabs: undefined
  TradeDetail: { tradeId: string }
  PositionDetail: { positionId: string }
  Entries: undefined
  Entry: { entry?: JournalEntry }
}

const Stack = createNativeStackNavigator<RootStackParamList>()

/** Tabs at the root; trade / position detail screens push over them from either tab. */
export function RootStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.accent,
        headerTitleStyle: { color: colors.textPrimary },
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="Tabs" component={AppTabs} options={{ headerShown: false }} />
      <Stack.Screen name="TradeDetail" component={TradeDetailScreen} options={{ title: 'Trade', headerBackTitle: 'Back' }} />
      <Stack.Screen
        name="PositionDetail"
        component={PositionDetailScreen}
        options={{ title: 'Open trade', headerBackTitle: 'Back' }}
      />
      <Stack.Screen name="Entries" component={EntriesScreen} options={{ title: 'Ideas & reviews', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Entry" component={EntryScreen} options={{ title: 'Note', headerBackTitle: 'Back' }} />
    </Stack.Navigator>
  )
}
