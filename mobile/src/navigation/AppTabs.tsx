import { Ionicons } from '@expo/vector-icons'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import type { IconName } from '../components/ui'
import { AnalyticsScreen } from '../screens/AnalyticsScreen'
import { JournalScreen } from '../screens/JournalScreen'
import { MoreScreen } from '../screens/MoreScreen'
import { PositionsScreen } from '../screens/PositionsScreen'
import { TodayScreen } from '../screens/TodayScreen'
import { colors, fonts } from '../theme'

const Tab = createBottomTabNavigator()

/** outline while idle, filled when selected — the fill, not just the colour, says where you are */
const icon = (idle: IconName, active: IconName) =>
  function TabIcon({ color, focused }: { color: string; focused: boolean }) {
    return <Ionicons name={focused ? active : idle} color={color} size={22} />
  }

/** The five places, in the order of a trader's day (same zones as the web app): now, open trades, review, numbers, everything else. */
export function AppTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border, borderTopWidth: 1, elevation: 0 },
        tabBarLabelStyle: { fontFamily: fonts.sansMedium, fontSize: 11, letterSpacing: 0.1 },
        tabBarHideOnKeyboard: true,
      }}
    >
      <Tab.Screen name="Today" component={TodayScreen} options={{ tabBarIcon: icon('today-outline', 'today') }} />
      <Tab.Screen name="Positions" component={PositionsScreen} options={{ tabBarIcon: icon('pulse-outline', 'pulse') }} />
      <Tab.Screen name="Journal" component={JournalScreen} options={{ tabBarIcon: icon('book-outline', 'book') }} />
      <Tab.Screen name="Analytics" component={AnalyticsScreen} options={{ tabBarIcon: icon('stats-chart-outline', 'stats-chart') }} />
      <Tab.Screen name="More" component={MoreScreen} options={{ tabBarIcon: icon('grid-outline', 'grid') }} />
    </Tab.Navigator>
  )
}
