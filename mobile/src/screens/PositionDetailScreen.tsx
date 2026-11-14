import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { patchPosition } from '../api/positions'
import { describeAccount } from '../accountLabel'
import { AnnotationEditor } from '../components/AnnotationEditor'
import { ScreenshotGallery } from '../components/ScreenshotGallery'
import { Text } from '../components/Text'
import { Button, Card, DirTag, Empty, Fact, LiveDot, Rows, ui } from '../components/ui'
import { formatMoney, formatPrice, formatUpdated } from '../format'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, pnlColor, spacing, type } from '../theme'

/** Journal an open trade while it's still running — the notes carry over to the closed trade automatically. */
export function PositionDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'PositionDetail'>>()
  const { params } = useRoute<RouteProp<RootStackParamList, 'PositionDetail'>>()
  const { data, applyPosition } = usePositionsContext()
  const tagSuggestions = useTagSuggestions()
  const position = data?.positions.find((p) => p.position_id === params.positionId)

  if (!position) {
    return (
      <SafeAreaView style={ui.screen}>
        <View style={styles.missing}>
          <Empty icon="checkmark-done-outline" title="This trade is no longer open" text="If it just closed, find it in the Journal tab. Your notes carried over.">
            <Button label="Go back" kind="secondary" size="sm" onPress={() => navigation.goBack()} />
          </Empty>
        </View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={ui.content} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <View style={ui.rowWrap}>
              <LiveDot size={8} />
              <Text style={styles.symbol}>{position.symbol}</Text>
              <DirTag direction={position.direction} />
            </View>
            <Text style={[styles.pnl, { color: pnlColor(position.floating_pnl) }]} numberOfLines={1} adjustsFontSizeToFit>
              {formatMoney(position.floating_pnl)}
            </Text>
            <Text style={ui.muted}>{describeAccount(position.account_id).label} · still open, so this number moves</Text>
          </View>

          <Card feature>
            <AnnotationEditor
              key={position.position_id}
              initial={{
                setup_tag: position.setup_tag ?? '',
                notes: position.notes ?? '',
                chart_snapshot_url: position.chart_snapshot_url ?? '',
                rating: position.rating ?? 0,
              }}
              tagSuggestions={tagSuggestions}
              notesLabel="Note: the plan and how it's playing out"
              save={async (patch) => {
                const res = await patchPosition(position.position_id, patch)
                applyPosition(res.entry)
              }}
            />
            <Text style={styles.carry}>Carries over to the closed trade once this position closes.</Text>
          </Card>

          <Card>
            <ScreenshotGallery
              ownerId={position.position_id}
              onCountChange={(n) => {
                if ((position.screenshot_count ?? 0) !== n) applyPosition({ ...position, screenshot_count: n })
              }}
            />
          </Card>

          <Card title="Position" flush>
            <Rows inset={0}>
              {position.open_time ? <Fact label="Opened" value={formatUpdated(position.open_time)} /> : null}
              <Fact label="Size" value={String(position.volume)} />
              <Fact label="Entry price" value={formatPrice(position.entry_price)} />
              <Fact label="Price now" value={formatPrice(position.current_price)} />
              <Fact label="Stop loss" value={position.sl ? formatPrice(position.sl) : 'None set'} color={position.sl ? undefined : colors.warning} />
              <Fact label="Target" value={position.tp ? formatPrice(position.tp) : '—'} />
            </Rows>
          </Card>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  hero: { gap: 2, paddingBottom: spacing.xs },
  symbol: { ...type.title, fontSize: 20, lineHeight: 26 },
  pnl: { ...type.hero },
  carry: { ...type.small, fontSize: 11, marginTop: spacing.xs },
  missing: { flex: 1, justifyContent: 'center' },
})
