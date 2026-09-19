import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getDayTrades } from '../api/analytics'
import { formatMoney, formatUpdated, isBuy } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
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
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.date}>{pretty}</Text>
        {!data && !error ? <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} /> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {data ? (
          <>
            <Text style={[styles.total, { color: data.net_profit > 0 ? colors.positive : data.net_profit < 0 ? colors.negative : colors.textSecondary }]}>
              {formatMoney(data.net_profit)}
            </Text>
            <Text style={styles.sub}>
              {data.count} trade{data.count === 1 ? '' : 's'} · {data.wins} win{data.wins === 1 ? '' : 's'}
            </Text>
            {data.trades.map((t) => {
              const dirColor = isBuy(t.direction) ? colors.positive : colors.negative
              const net = t.net_profit
              return (
                <Pressable
                  key={t.trade_id}
                  onPress={() => navigation.navigate('TradeDetail', { tradeId: t.trade_id })}
                  style={({ pressed }) => [styles.row, pressed && { opacity: 0.75 }]}
                  accessibilityRole="button"
                >
                  <View style={styles.rowTop}>
                    <View style={styles.symbolRow}>
                      <Text style={styles.symbol}>{t.symbol}</Text>
                      <View style={[styles.dirPill, { borderColor: dirColor }]}>
                        <Text style={[styles.dirText, { color: dirColor }]}>{t.direction.toUpperCase()}</Text>
                      </View>
                    </View>
                    <Text style={[styles.net, { color: net > 0 ? colors.positive : net < 0 ? colors.negative : colors.textSecondary }]}>
                      {formatMoney(net)}
                    </Text>
                  </View>
                  <Text style={styles.meta}>
                    {t.account_id} · closed {formatUpdated(t.exit_time)}
                    {t.setup_tag ? ` · ${t.setup_tag}` : ''}
                  </Text>
                </Pressable>
              )
            })}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.sm },
  date: { color: colors.textSecondary, fontSize: 14 },
  total: { fontSize: 30, fontWeight: '800', fontVariant: ['tabular-nums'] },
  sub: { color: colors.textMuted, fontSize: 13, marginBottom: spacing.sm },
  error: { color: colors.negative },
  row: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: 4,
  },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  symbolRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  symbol: { color: colors.textPrimary, fontSize: 17, fontWeight: '700' },
  dirPill: { borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 1 },
  dirText: { fontSize: 11, fontWeight: '700' },
  net: { fontSize: 17, fontWeight: '700', fontVariant: ['tabular-nums'] },
  meta: { color: colors.textMuted, fontSize: 12 },
})
