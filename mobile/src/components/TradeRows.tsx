import { Ionicons } from '@expo/vector-icons'
import { Pressable, StyleSheet, View } from 'react-native'
import { formatMoney, formatUpdated } from '../format'
import { colors, pnlColor, spacing, type } from '../theme'
import type { JournalTradeItem } from '../types/journal'
import type { PositionItem } from '../types/positions'
import { AccountTag } from './AccountTag'
import { Text } from './Text'
import { ExitsPill } from './TradeLegs'
import { DirTag, LiveDot, Tag } from './ui'

/**
 * The two trade rows every list shares (Today, Journal, a calendar day): one line that answers
 * "which market, which way, how did it go", then a quiet second line. Use inside <Rows> in a `flush` Card.
 */

/** A trade that is still open: live dot, market, direction, size, floating P&L. */
export function OpenTradeRow({ p, onPress, showAccount }: { p: PositionItem; onPress: () => void; showAccount?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <View style={styles.main}>
        <View style={styles.top}>
          <LiveDot />
          <Text style={styles.symbol}>{p.symbol}</Text>
          <DirTag direction={p.direction} />
          <Text style={styles.vol}>{p.volume}</Text>
        </View>
        {showAccount || p.setup_tag ? (
          <View style={styles.meta}>
            {showAccount ? <AccountTag accountId={p.account_id} /> : null}
            {p.setup_tag ? <Tag text={p.setup_tag} /> : null}
          </View>
        ) : null}
      </View>
      <Text style={[styles.pnl, { color: pnlColor(p.floating_pnl) }]}>{formatMoney(p.floating_pnl)}</Text>
      <Ionicons name="chevron-forward" size={15} color={colors.textMuted} />
    </Pressable>
  )
}

/** A closed trade: market, direction, size, net P&L; then when it closed, its label, stars, screenshots, first line of the note. */
export function ClosedTradeRow({ t, onPress, showAccount }: { t: JournalTradeItem; onPress: () => void; showAccount?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.row, styles.rowTop, pressed && styles.pressed]}>
      <View style={styles.main}>
        <View style={styles.top}>
          <Text style={styles.symbol}>{t.symbol}</Text>
          <DirTag direction={t.direction} />
          <Text style={styles.vol}>{t.volume}</Text>
          <ExitsPill t={t} />
        </View>
        <View style={styles.meta}>
          <Text style={styles.time}>{formatUpdated(t.exit_time)}</Text>
          {showAccount ? <AccountTag accountId={t.account_id} /> : null}
          {t.setup_tag ? <Tag text={t.setup_tag} /> : null}
          <Stars n={t.rating} />
          {t.screenshot_count ? (
            <View style={styles.shots}>
              <Ionicons name="image-outline" size={12} color={colors.textMuted} />
              <Text style={styles.time}>{t.screenshot_count}</Text>
            </View>
          ) : null}
        </View>
        {t.notes ? (
          <Text style={styles.note} numberOfLines={1}>
            {t.notes}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.pnl, { color: pnlColor(t.net_profit) }]}>{formatMoney(t.net_profit)}</Text>
    </Pressable>
  )
}

export function Stars({ n }: { n: number | null | undefined }) {
  if (!n || n <= 0) return null
  const count = Math.min(5, n)
  return (
    <View style={styles.shots} accessibilityLabel={`${count} of 5 stars`}>
      <Ionicons name="star" size={11} color={colors.warning} />
      <Text style={styles.time}>{count}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  // the P&L sits on the market's line, so the eye reads "US100 ... -$1.63" straight across
  rowTop: { alignItems: 'flex-start' },
  pressed: { backgroundColor: colors.surfaceHover },
  main: { flex: 1, minWidth: 0, gap: 5 },
  // badges wrap onto a second line instead of running under the P&L
  top: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', columnGap: spacing.sm, rowGap: 4 },
  symbol: { ...type.heading },
  vol: { ...type.small, fontVariant: ['tabular-nums'] },
  meta: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', columnGap: spacing.sm, rowGap: 4 },
  time: { ...type.small, fontVariant: ['tabular-nums'] },
  shots: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  note: { ...type.small, color: colors.textSecondary },
  pnl: { ...type.num, fontSize: 15, fontWeight: '600', flexShrink: 0 },
})
