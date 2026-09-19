import { Ionicons } from '@expo/vector-icons'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { AnalyticsScreen } from '../screens/AnalyticsScreen'
import { JournalScreen } from '../screens/JournalScreen'
import { MoreScreen } from '../screens/MoreScreen'
import { PositionsScreen } from '../screens/PositionsScreen'
import { colors } from '../theme'

const Tab = createBottomTabNavigator()

export function AppTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.borderSubtle },
      }}
    >
      <Tab.Screen
        name="Positions"
        component={PositionsScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="pulse" color={color} size={size} /> }}
      />
      <Tab.Screen
        name="Journal"
        component={JournalScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="journal-outline" color={color} size={size} /> }}
      />
      <Tab.Screen
        name="Analytics"
        component={AnalyticsScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart" color={color} size={size} /> }}
      />
      <Tab.Screen
        name="More"
        component={MoreScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="ellipsis-horizontal-circle-outline" color={color} size={size} /> }}
      />
    </Tab.Navigator>
  )
}
