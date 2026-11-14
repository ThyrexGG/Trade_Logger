import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { AccountScreen } from '../screens/AccountScreen'
import { AssistantScreen } from '../screens/AssistantScreen'
import { DayTradesScreen } from '../screens/DayTradesScreen'
import { EntriesScreen } from '../screens/EntriesScreen'
import { EntryScreen } from '../screens/EntryScreen'
import { ManualTradeScreen } from '../screens/ManualTradeScreen'
import { KillzoneScreen } from '../screens/KillzoneScreen'
import { ChallengeScreen } from '../screens/ChallengeScreen'
import { ChartAnalyzerScreen } from '../screens/ChartAnalyzerScreen'
import { ConnectionsScreen } from '../screens/ConnectionsScreen'
import { SetupsScreen } from '../screens/SetupsScreen'
import { WeeklySummaryScreen } from '../screens/WeeklySummaryScreen'
import { PositionDetailScreen } from '../screens/PositionDetailScreen'
import { PriceAlertsScreen } from '../screens/PriceAlertsScreen'
import { RiskGatewayScreen } from '../screens/RiskGatewayScreen'
import { TradeDetailScreen } from '../screens/TradeDetailScreen'
import { colors, fonts } from '../theme'
import type { JournalEntry, JournalEntryInput } from '../types/entries'
import type { JournalTradeItem } from '../types/journal'
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
  ManualTrade: { trade?: JournalTradeItem } | undefined
  RiskGateway: { prefill?: { symbol?: string; side?: 'BUY' | 'SELL'; entry?: number; stop?: number; tp1?: number; tp2?: number } } | undefined
  Assistant: undefined
  Killzone: undefined
  Connections: undefined
  Challenge: undefined
  ChartAnalyzer: undefined
  Setups: undefined
  WeeklySummary: undefined
}

const Stack = createNativeStackNavigator<RootStackParamList>()

/** Tabs at the root; every other screen pushes over them. Titles use the web app's names for the same pages. */
export function RootStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        // the header is part of the page (same ground, no shadow line), so a pushed screen reads as one surface
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTintColor: colors.accent,
        headerTitleStyle: { color: colors.textPrimary, fontFamily: fonts.sansSemi, fontSize: 17 },
        headerBackTitleStyle: { fontFamily: fonts.sans },
        contentStyle: { backgroundColor: colors.background },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="Tabs" component={AppTabs} options={{ headerShown: false }} />
      <Stack.Screen name="TradeDetail" component={TradeDetailScreen} options={{ title: 'Trade', headerBackTitle: 'Back' }} />
      <Stack.Screen
        name="PositionDetail"
        component={PositionDetailScreen}
        options={{ title: 'Open trade', headerBackTitle: 'Back' }}
      />
      <Stack.Screen name="Entries" component={EntriesScreen} options={{ title: 'Notes', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Entry" component={EntryScreen} options={{ title: 'Note', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Account" component={AccountScreen} options={{ title: 'Settings', headerBackTitle: 'Back' }} />
      <Stack.Screen name="DayTrades" component={DayTradesScreen} options={{ title: 'Day', headerBackTitle: 'Back' }} />
      <Stack.Screen name="PriceAlerts" component={PriceAlertsScreen} options={{ title: 'Price alerts', headerBackTitle: 'Back' }} />
      <Stack.Screen name="ManualTrade" component={ManualTradeScreen} options={{ title: 'Log a trade', headerBackTitle: 'Back' }} />
      <Stack.Screen name="RiskGateway" component={RiskGatewayScreen} options={{ title: 'Position size', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Assistant" component={AssistantScreen} options={{ title: 'Ask AI', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Killzone" component={KillzoneScreen} options={{ title: 'Find setups', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Connections" component={ConnectionsScreen} options={{ title: 'Broker connection', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Challenge" component={ChallengeScreen} options={{ title: 'Challenge tracker', headerBackTitle: 'Back' }} />
      <Stack.Screen name="ChartAnalyzer" component={ChartAnalyzerScreen} options={{ title: 'Chart analyzer', headerBackTitle: 'Back' }} />
      <Stack.Screen name="Setups" component={SetupsScreen} options={{ title: 'Rules & setups', headerBackTitle: 'Back' }} />
      <Stack.Screen name="WeeklySummary" component={WeeklySummaryScreen} options={{ title: 'Weekly summary', headerBackTitle: 'Back' }} />
    </Stack.Navigator>
  )
}
