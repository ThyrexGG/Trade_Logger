import { Ionicons } from '@expo/vector-icons'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useEffect, useState } from 'react'
import { Pressable, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getDayTrades } from '../api/analytics'
import { describeAccount } from '../accountLabel'
import { Text } from '../components/Text'
import { Card, DirTag, Loading, Notice, Rows, Tag, ui } from '../components/ui'
import { formatMoney, formatUpdated } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, pnlColor, spacing, type } from '../theme'
import type { AnalyticsDayTradesResponse } from '../types/analytics'

/** The trades that closed on one calendar day (opened from the Analytics calendar). */
export function DayTradesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'DayTrades'>>()
  const { params } = useRoute<RouteProp<RootStackParamList, 'DayTrades'>>()
  const [data, setData] = useState<AnalyticsDayTradesResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getDayTrades(params.date, params.account, controller.signal)
      .then(setData)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load this day.')
      })
    return () => controller.abort()
  }, [params.date, params.account])

  const pretty = new Date(`${params.date}T00:00:00`).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <ScrollView contentContainerStyle={ui.content}>
        <View style={styles.hero}>
          <Text style={styles.date}>{pretty}</Text>
          {data ? (
            <>
              <Text style={[styles.total, { color: pnlColor(data.net_profit) }]} numberOfLines={1} adjustsFontSizeToFit>
                {formatMoney(data.net_profit)}
              </Text>
              <Text style={ui.muted}>
                {data.count} trade{data.count === 1 ? '' : 's'} · {data.wins} win{data.wins === 1 ? '' : 's'}
                {params.account ? ` · ${describeAccount(params.account).label}` : ''}
              </Text>
            </>
          ) : null}
        </View>
        {!data && !error ? <Loading /> : null}
        {error ? <Notice>{error}</Notice> : null}
        {data && data.trades.length > 0 ? (
          <Card flush>
            <Rows>
              {data.trades.map((t) => (
                <Pressable
                  key={t.trade_id}
                  onPress={() => navigation.navigate('TradeDetail', { tradeId: t.trade_id })}
                  style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceHover }]}
                  accessibilityRole="button"
                >
                  <View style={styles.main}>
                    <View style={ui.rowWrap}>
                      <Text style={ui.heading}>{t.symbol}</Text>
                      <DirTag direction={t.direction} />
                    </View>
                    <View style={ui.rowWrap}>
                      <Text style={styles.time}>{formatUpdated(t.exit_time)}</Text>
                      {!params.account ? <Text style={ui.muted}>{describeAccount(t.account_id).label}</Text> : null}
                      {t.setup_tag ? <Tag text={t.setup_tag} /> : null}
                    </View>
                  </View>
                  <Text style={[styles.net, { color: pnlColor(t.net_profit) }]}>{formatMoney(t.net_profit)}</Text>
                  <Ionicons name="chevron-forward" size={15} color={colors.textMuted} />
                </Pressable>
              ))}
            </Rows>
          </Card>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  hero: { gap: 2, paddingBottom: spacing.xs },
  date: { ...type.label },
  total: { ...type.hero },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  main: { flex: 1, minWidth: 0, gap: 5 },
  time: { ...type.small, fontVariant: ['tabular-nums'] },
  net: { ...type.num, fontSize: 15, fontWeight: '600', flexShrink: 0 },
})
