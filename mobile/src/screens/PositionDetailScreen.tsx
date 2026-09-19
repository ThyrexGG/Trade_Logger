import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { patchPosition } from '../api/positions'
import { AnnotationEditor } from '../components/AnnotationEditor'
import { ScreenshotGallery } from '../components/ScreenshotGallery'
import { formatMoney, formatPrice, isBuy } from '../format'
import { useTagSuggestions } from '../journal/useTagSuggestions'
import type { RootStackParamList } from '../navigation/RootStack'
import { usePositionsContext } from '../positions/PositionsContext'
import { colors, radius, spacing } from '../theme'

/** Journal an open trade while it's still running — the notes carry over to the closed trade automatically. */
export function PositionDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'PositionDetail'>>()
  const { params } = useRoute<RouteProp<RootStackParamList, 'PositionDetail'>>()
  const { data, applyPosition } = usePositionsContext()
  const tagSuggestions = useTagSuggestions()
  const position = data?.positions.find((p) => p.position_id === params.positionId)

  if (!position) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.missing}>
          <Text style={styles.missingText}>
            This trade is no longer open. If it just closed, find it in the Journal tab — your notes carried over.
          </Text>
          <Pressable onPress={() => navigation.goBack()} style={styles.backBtn} accessibilityRole="button">
            <Text style={styles.backText}>Go back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    )
  }

  const dirColor = isBuy(position.direction) ? colors.positive : colors.negative
  const pnlColor = position.floating_pnl > 0 ? colors.positive : position.floating_pnl < 0 ? colors.negative : colors.textSecondary

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <View style={styles.heroTop}>
              <View style={styles.liveDot} />
              <Text style={styles.symbol}>{position.symbol}</Text>
              <View style={[styles.dirPill, { borderColor: dirColor }]}>
                <Text style={[styles.dirText, { color: dirColor }]}>{position.direction.toUpperCase()}</Text>
              </View>
            </View>
            <Text style={[styles.pnl, { color: pnlColor }]}>{formatMoney(position.floating_pnl)}</Text>
            <Text style={styles.sub}>{position.account_id} · floating P&L, still open</Text>
          </View>

          <View style={styles.card}>
            <ScreenshotGallery
              ownerId={position.position_id}
              onCountChange={(n) => {
                if ((position.screenshot_count ?? 0) !== n) applyPosition({ ...position, screenshot_count: n })
              }}
            />
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Journal</Text>
            <AnnotationEditor
              key={position.position_id}
              initial={{
                setup_tag: position.setup_tag ?? '',
                notes: position.notes ?? '',
                chart_snapshot_url: position.chart_snapshot_url ?? '',
                rating: position.rating ?? 0,
              }}
              tagSuggestions={tagSuggestions}
              notesLabel="Notes — the plan and how it's playing out"
              save={async (patch) => {
                const res = await patchPosition(position.position_id, patch)
                applyPosition(res.entry)
              }}
            />
            <Text style={styles.carry}>Carries over to the closed trade automatically once this position closes.</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Position</Text>
            <Fact label="Volume" value={String(position.volume)} />
            <Fact label="Entry" value={formatPrice(position.entry_price)} />
            <Fact label="Current" value={formatPrice(position.current_price)} />
            <Fact label="Stop" value={position.sl ? formatPrice(position.sl) : '—'} />
            <Fact label="Target" value={position.tp ? formatPrice(position.tp) : '—'} last />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

function Fact({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.fact, !last && styles.factBorder]}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={styles.factValue}>{value}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  hero: { gap: spacing.xs },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  liveDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.accent },
  symbol: { color: colors.textPrimary, fontSize: 26, fontWeight: '700' },
  dirPill: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  dirText: { fontSize: 12, fontWeight: '700' },
  pnl: { fontSize: 34, fontWeight: '700', fontVariant: ['tabular-nums'] },
  sub: { color: colors.textMuted, fontSize: 13 },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  carry: { color: colors.textMuted, fontSize: 11, marginTop: spacing.md },
  fact: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.md, gap: spacing.lg },
  factBorder: { borderBottomColor: colors.borderSubtle, borderBottomWidth: 1 },
  factLabel: { color: colors.textMuted, fontSize: 13 },
  factValue: { color: colors.textPrimary, fontSize: 14, fontVariant: ['tabular-nums'] },
  missing: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.lg, padding: spacing.xl },
  missingText: { color: colors.textSecondary, fontSize: 15, textAlign: 'center' },
  backBtn: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  backText: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
})
