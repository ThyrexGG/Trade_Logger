import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { Fragment } from 'react'
import { ScrollView } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useAuth } from '../auth/AuthContext'
import { Card, Row, Rows, ScreenHeader, SectionLabel, ui, type IconName } from '../components/ui'
import type { RootStackParamList } from '../navigation/RootStack'

type Item = {
  route: keyof RootStackParamList
  icon: IconName
  title: string
  sub: string
}

/**
 * Everything that doesn't get its own tab, grouped the way the web app groups its pages (Plan / Review / Settings).
 * New phone features are added to the group they belong to.
 */
const GROUPS: { label: string; items: Item[] }[] = [
  {
    label: 'Plan',
    items: [
      { route: 'Killzone', icon: 'scan-outline', title: 'Find setups', sub: 'Stop-hunts and turns, by session' },
      { route: 'ChartAnalyzer', icon: 'image-outline', title: 'Chart analyzer', sub: 'AI reads the plan drawn on a chart screenshot' },
      { route: 'RiskGateway', icon: 'calculator-outline', title: 'Position size', sub: 'How big to trade, from your stop and risk' },
      { route: 'PriceAlerts', icon: 'notifications-outline', title: 'Price alerts', sub: 'Get told when a price crosses your level' },
    ],
  },
  {
    label: 'Review',
    items: [
      { route: 'WeeklySummary', icon: 'calendar-outline', title: 'Weekly summary', sub: 'How your week went, sent every Sunday' },
      { route: 'Setups', icon: 'pricetags-outline', title: 'Rules & setups', sub: 'What makes money, and trades still to mark' },
      { route: 'Challenge', icon: 'trophy-outline', title: 'Challenge tracker', sub: 'Prop-firm target, drawdown and daily loss' },
      { route: 'Entries', icon: 'document-text-outline', title: 'Notes', sub: 'Ideas, reviews and trade plans' },
      { route: 'Assistant', icon: 'sparkles-outline', title: 'Ask AI', sub: 'Questions about your own trading' },
      { route: 'ManualTrade', icon: 'add-circle-outline', title: 'Log a trade', sub: 'Record a trade taken outside a synced broker' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { route: 'Connections', icon: 'link-outline', title: 'Broker connection', sub: 'Connect Capital.com so trades sync in' },
      { route: 'Account', icon: 'settings-outline', title: 'Settings', sub: 'Auto-sync, trade alerts, app lock, log out' },
    ],
  },
]

export function MoreScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { user } = useAuth()
  return (
    <SafeAreaView style={ui.screen} edges={['top']}>
      <ScreenHeader title="More" sub={user?.email ?? undefined} />
      <ScrollView contentContainerStyle={ui.content}>
        {GROUPS.map((g, gi) => (
          <Fragment key={g.label}>
            <SectionLabel style={gi === 0 ? { marginTop: 0 } : undefined}>{g.label}</SectionLabel>
            <Card flush>
              <Rows inset={60}>
                {g.items.map((r) => (
                  <Row key={r.route} icon={r.icon} title={r.title} sub={r.sub} chevron onPress={() => navigation.navigate(r.route as never)} />
                ))}
              </Rows>
            </Card>
          </Fragment>
        ))}
      </ScrollView>
    </SafeAreaView>
  )
}
