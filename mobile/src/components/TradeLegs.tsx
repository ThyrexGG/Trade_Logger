import { StyleSheet, Text, View } from 'react-native'
import { formatMoney, formatUpdated } from '../format'
import { colors, radius, spacing } from '../theme'
import type { JournalTradeItem } from '../types/journal'
import { Pill } from './ui'

const tone = (v: number) => (v > 0 ? colors.positive : v < 0 ? colors.negative : colors.textSecondary)

/** "3 partials + final exit" — which exits were partial and which closed the trade. */
export function legsSummary(t: JournalTradeItem): string {
  const partials = (t.legs ?? []).filter((l) => l.kind === 'partial').length
  const part = `${partials} partial${partials === 1 ? '' : 's'}`
  return t.position_open ? `${part} · position still open` : `${part} + final exit`
}

/** Pill for a trade row: "4 exits", or "2 partials · open" while some of it is still running. */
export function ExitsPill({ t }: { t: JournalTradeItem }) {
  const n = t.legs?.length ?? 0
  if (n === 0) return null
  return <Pill text={t.position_open ? `${n} partial${n === 1 ? '' : 's'} · open` : `${n} exits`} color={colors.accent} />
}

/** Every exit of a scaled-out trade, oldest first, partials labelled apart from the final exit. */
export function TradeLegsCard({ t }: { t: JournalTradeItem }) {
  const legs = t.legs ?? []
  if (legs.length === 0) return null
  const total = legs.reduce((s, l) => s + l.net, 0)
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Exits</Text>
      <Text style={styles.muted}>
        One trade, {legs.length} exit{legs.length === 1 ? '' : 's'}: {legsSummary(t)}. The P&L above is the whole position.
      </Text>
      {legs.map((l) => (
        <View key={`${l.n}:${l.trade_id ?? l.time}`} style={styles.row}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={[styles.kind, l.kind === 'final' && { color: colors.accent }]}>{l.kind === 'final' ? 'Final exit' : `Partial ${l.n}`}</Text>
            <Text style={styles.muted}>
              {formatUpdated(l.time)}
              {l.volume != null && l.price != null ? ` · ${l.volume} @ ${l.price}` : ''}
            </Text>
          </View>
          <Text style={[styles.net, { color: tone(l.net) }]}>{formatMoney(l.net)}</Text>
        </View>
      ))}
      <View style={[styles.row, styles.totalRow]}>
        <Text style={styles.muted}>Position total</Text>
        <Text style={[styles.net, { color: tone(total) }]}>{formatMoney(total)}</Text>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, gap: spacing.xs },
  title: { color: colors.textMuted, fontSize: 11, fontWeight: '600', letterSpacing: 0.8, textTransform: 'uppercase' },
  muted: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.borderSubtle },
  totalRow: { justifyContent: 'space-between' },
  kind: { color: colors.textPrimary, fontSize: 14, fontWeight: '600' },
  net: { fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
})
