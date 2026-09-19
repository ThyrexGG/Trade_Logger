import { StyleSheet, Text, View } from 'react-native'
import { formatMoney } from '../../format'
import { colors, spacing } from '../../theme'

export interface PnlBarRow {
  label: string
  value: number
  sub?: string
}

/** Horizontal P&L bars: right of the centre line for profit, left for loss; width is |value| against the largest row. */
export function PnlBars({ rows }: { rows: PnlBarRow[] }) {
  if (rows.length === 0) return <Text style={styles.empty}>Nothing in this range.</Text>
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.value)))
  return (
    <View>
      {rows.map((r) => {
        const pct = (Math.abs(r.value) / max) * 50
        const color = r.value > 0 ? colors.positive : r.value < 0 ? colors.negative : colors.textSecondary
        return (
          <View key={r.label} style={styles.row}>
            <View style={styles.head}>
              <Text style={styles.label} numberOfLines={1}>
                {r.label}
              </Text>
              <Text style={[styles.value, { color }]}>{formatMoney(r.value)}</Text>
            </View>
            <View style={styles.track}>
              <View style={styles.centre} />
              <View
                style={[
                  styles.bar,
                  { width: `${pct}%`, backgroundColor: color },
                  r.value >= 0 ? { left: '50%' } : { right: '50%' },
                ]}
              />
            </View>
            {r.sub ? <Text style={styles.sub}>{r.sub}</Text> : null}
          </View>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  empty: { color: colors.textMuted, fontSize: 13 },
  row: { paddingVertical: spacing.sm },
  head: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md },
  label: { color: colors.textPrimary, fontSize: 14, fontWeight: '600', flexShrink: 1 },
  value: { fontSize: 14, fontWeight: '700', fontVariant: ['tabular-nums'] },
  track: { height: 8, borderRadius: 4, backgroundColor: colors.surfaceElevated, marginTop: 6, overflow: 'hidden' },
  centre: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, backgroundColor: colors.border },
  bar: { position: 'absolute', top: 0, bottom: 0, opacity: 0.7 },
  sub: { color: colors.textMuted, fontSize: 11, marginTop: 4 },
})
