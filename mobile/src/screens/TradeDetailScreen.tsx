import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { clearAnalyticsCache } from '../analytics/useAnalytics'
import { deleteManualTrade, patchJournalEntry } from '../api/journal'
import { describeAccount } from '../accountLabel'
import { AnnotationEditor } from '../components/AnnotationEditor'
import { ScreenshotGallery } from '../components/ScreenshotGallery'
import { Text } from '../components/Text'
import { ExitsPill, TradeLegsCard } from '../components/TradeLegs'
import { Button, Card, DirTag, Empty, Fact, Loading, Notice, Rows, ui } from '../components/ui'
import { formatMoney, formatPrice, formatUpdated } from '../format'
import { useJournal } from '../journal/JournalContext'
import { formatDuration } from '../journal/filters'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { pnlColor, spacing, type } from '../theme'

export function TradeDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'TradeDetail'>>()
  const { params } = useRoute<RouteProp<RootStackParamList, 'TradeDetail'>>()
  const { data, applyEntry, loading, refreshing, refresh } = useJournal()
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const tagSuggestions = useTagSuggestions()
  // A link to one partial close (an old notification) opens the trade it belongs to.
  const trade = data?.entries.find((e) => e.trade_id === params.tradeId || e.legs?.some((l) => l.trade_id === params.tradeId))

  // Opened from a push notification: the trade may still be on its way in from the server.
  if (!trade && (loading || refreshing)) {
    return (
      <SafeAreaView style={ui.screen}>
        <Loading fill />
      </SafeAreaView>
    )
  }

  if (!trade) {
    return (
      <SafeAreaView style={ui.screen}>
        <View style={styles.missing}>
          <Empty icon="help-circle-outline" title="This trade is no longer in your journal">
            <Button label="Go back" kind="secondary" size="sm" onPress={() => navigation.goBack()} />
          </Empty>
        </View>
      </SafeAreaView>
    )
  }

  const isManual = trade.trade_id.startsWith('MANUAL_')

  function confirmDelete() {
    if (!trade) return
    Alert.alert('Delete this trade?', 'It is removed from your Journal, Analytics and calendar, along with its notes and screenshots. This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          setDeleting(true)
          setDeleteError(null)
          try {
            await deleteManualTrade(trade.trade_id)
            clearAnalyticsCache()
            await refresh()
            navigation.goBack()
          } catch (err) {
            setDeleteError(err instanceof Error ? err.message : 'Could not delete the trade.')
            setDeleting(false)
          }
        },
      },
    ])
  }

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={ui.content} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <View style={ui.rowWrap}>
              <Text style={styles.symbol}>{trade.symbol}</Text>
              <DirTag direction={trade.direction} />
              <ExitsPill t={trade} />
            </View>
            <Text style={[styles.net, { color: pnlColor(trade.net_profit) }]} numberOfLines={1} adjustsFontSizeToFit>
              {formatMoney(trade.net_profit)}
            </Text>
            <Text style={ui.muted}>
              {describeAccount(trade.account_id).label} · closed {formatUpdated(trade.exit_time)}
            </Text>
          </View>

          <Card feature>
            <AnnotationEditor
              key={trade.trade_id}
              initial={{
                setup_tag: trade.setup_tag ?? '',
                notes: trade.notes ?? '',
                chart_snapshot_url: trade.chart_snapshot_url ?? '',
                rating: trade.rating ?? 0,
              }}
              tagSuggestions={tagSuggestions}
              save={async (patch) => {
                const res = await patchJournalEntry(trade.trade_id, patch)
                applyEntry(res.entry)
              }}
            />
          </Card>

          <Card>
            <ScreenshotGallery
              ownerId={trade.trade_id}
              onCountChange={(n) => {
                if ((trade.screenshot_count ?? 0) !== n) applyEntry({ ...trade, screenshot_count: n })
              }}
            />
          </Card>

          <TradeLegsCard t={trade} />

          <Card title="Trade details" flush>
            <Rows inset={0}>
              <Fact label="Size" value={String(trade.volume)} />
              <Fact label="Entry price" value={formatPrice(trade.entry_price)} />
              <Fact label="Exit price" value={formatPrice(trade.exit_price)} />
              {/* 0 holding time = the broker never sent the open (older-history import); blank, not the close time */}
              <Fact label="Opened" value={trade.duration_minutes > 0 ? formatUpdated(trade.entry_time) : '—'} />
              <Fact label="Closed" value={formatUpdated(trade.exit_time)} />
              <Fact label="Held for" value={formatDuration(trade.duration_minutes)} />
              <Fact label="P&L before costs" value={formatMoney(trade.gross_profit)} />
              <Fact label="Commission" value={formatMoney(trade.commission)} />
              <Fact label="Swap" value={formatMoney(trade.swap)} />
            </Rows>
          </Card>

          {isManual ? (
            <Card title="Logged by hand">
              <Text style={ui.muted}>You entered this trade yourself, so you can fix or remove it. Trades synced from a broker can't be changed here.</Text>
              <View style={styles.manualRow}>
                <Button label="Edit trade" kind="secondary" onPress={() => navigation.navigate('ManualTrade', { trade })} style={ui.flex} />
                <Button label="Delete trade" kind="danger" busy={deleting} onPress={confirmDelete} style={ui.flex} />
              </View>
              {deleteError ? <Notice>{deleteError}</Notice> : null}
            </Card>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  hero: { gap: 2, paddingBottom: spacing.xs },
  symbol: { ...type.title, fontSize: 20, lineHeight: 26 },
  net: { ...type.hero },
  manualRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  missing: { flex: 1, justifyContent: 'center' },
})
