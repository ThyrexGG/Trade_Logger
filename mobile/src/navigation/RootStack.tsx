import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { AccountScreen } from '../screens/AccountScreen'
import { AssistantScreen } from '../screens/AssistantScreen'
import { DayTradesScreen } from '../screens/DayTradesScreen'
import { EntriesScreen } from '../screens/EntriesScreen'
import { EntryScreen } from '../screens/EntryScreen'
import { ManualTradeScreen } from '../screens/ManualTradeScreen'
import { KillzoneScreen } from '../screens/KillzoneScreen'
import { TodayScreen } from '../screens/TodayScreen'
import { PositionDetailScreen } from '../screens/PositionDetailScreen'
import { PriceAlertsScreen } from '../screens/PriceAlertsScreen'
import { RiskGatewayScreen } from '../screens/RiskGatewayScreen'
import { TradeDetailScreen } from '../screens/TradeDetailScreen'
import { colors } from '../theme'
import type { JournalEntry, JournalEntryInput } from '../types/entries'
import { AppTabs } from './AppTabs'

export type RootStackParamList = {
  Tabs: undefined
  TradeDetail: { tradeId: string }
  PositionDetail: { positionId: string }
  Entries: undefined
  Entry: { entry?: JournalEntry; prefill?: JournalEntryInput }
  Account: undefined
  DayTrades: { date: string; account?: string }
  PriceAlerts: undefined
  ManualTrade: undefined
  RiskGateway: undefined
  Assistant: undefined
  Killzone: undefined
  Today: undefined
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
      <Stack.Screen name="Account" component={AccountScreen} options={{ title: 'Account & alerts', headerBackTitle: 'Back' }} />
      <Stack.Screen name="DayTrades" component={DayTradesScreen} options={{ title: 'Day', headerBackTitle: 'Back' }} />
      <Stack.Screen name="PriceAlerts" component={PriceAlertsScreen} options={{ title: 'Price alerts', headerBackTitle: 'Back' }} />
      <Stack.Screen name="ManualTrade" component={ManualTradeScreen} options={{ title: 'Log a trade', headerBackTitle: 'Back' }} />
      <Stack.Screen name="RiskGateway" component={RiskGatewayScreen} options={{ title: 'Risk gateway', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Assistant" component={AssistantScreen} options={{ title: 'AI assistant', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Killzone" component={KillzoneScreen} options={{ title: 'Killzone scanner', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Today" component={TodayScreen} options={{ title: 'Today', headerBackTitle: 'Back' }} />
    </Stack.Navigator>
  )
}
