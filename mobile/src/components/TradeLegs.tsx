import { StyleSheet, View } from 'react-native'
import { Text } from './Text'
import { formatMoney, formatUpdated } from '../format'
import { colors, pnlColor, spacing, type } from '../theme'
import type { JournalTradeItem } from '../types/journal'
import { Card, Pill, Rows } from './ui'

const tone = (v: number) => pnlColor(v)

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
    <Card title="Exits" right={`${legs.length} exit${legs.length === 1 ? '' : 's'}`} flush>
      <Text style={styles.intro}>This is one trade closed in parts: {legsSummary(t)}. The P&L at the top is the whole position.</Text>
      <Rows>
        {legs.map((l) => (
          <View key={`${l.n}:${l.trade_id ?? l.time}`} style={styles.row}>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={styles.kind}>{l.kind === 'final' ? 'Final exit' : `Partial ${l.n}`}</Text>
              <Text style={styles.muted}>
                {formatUpdated(l.time)}
                {l.volume != null && l.price != null ? ` · ${l.volume} @ ${l.price}` : ''}
              </Text>
            </View>
            <Text style={[styles.net, { color: tone(l.net) }]}>{formatMoney(l.net)}</Text>
          </View>
        ))}
        <View style={styles.row}>
          <Text style={[styles.kind, { flex: 1 }]}>Whole position</Text>
          <Text style={[styles.net, { color: tone(total) }]}>{formatMoney(total)}</Text>
        </View>
      </Rows>
    </Card>
  )
}

const styles = StyleSheet.create({
  intro: { ...type.small, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.borderSubtle },
  muted: { ...type.small, fontVariant: ['tabular-nums'] },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: 11 },
  kind: { ...type.body, fontWeight: '500' },
  net: { ...type.num, fontWeight: '600' },
})
