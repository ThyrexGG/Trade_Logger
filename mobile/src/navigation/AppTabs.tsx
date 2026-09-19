import { Ionicons } from '@expo/vector-icons'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { AccountScreen } from '../screens/AccountScreen'
import { JournalScreen } from '../screens/JournalScreen'
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
        name="Account"
        component={AccountScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="person-circle-outline" color={color} size={size} /> }}
      />
    </Tab.Navigator>
  )
}
