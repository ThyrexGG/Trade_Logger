import { StyleSheet, View } from 'react-native'
import { Text } from '../Text'
import { formatMoney } from '../../format'
import { colors, pnlColor, radius, spacing, type } from '../../theme'

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
        const color = pnlColor(r.value)
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
                  // rounded at the data end only, square at the centre line
                  r.value >= 0 ? { left: '50%', borderTopRightRadius: 3, borderBottomRightRadius: 3 } : { right: '50%', borderTopLeftRadius: 3, borderBottomLeftRadius: 3 },
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
  empty: { ...type.small, fontSize: 13 },
  row: { paddingVertical: 7 },
  head: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md },
  label: { ...type.body, fontWeight: '500', flexShrink: 1 },
  value: { ...type.num, fontWeight: '600' },
  track: { height: 6, borderRadius: radius.sm, backgroundColor: colors.surfaceElevated, marginTop: 6, overflow: 'hidden' },
  centre: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, backgroundColor: colors.border },
  bar: { position: 'absolute', top: 0, bottom: 0, opacity: 0.85 },
  sub: { ...type.small, fontSize: 11, marginTop: 4 },
})
