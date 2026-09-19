import { useState } from 'react'
import { StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native'
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg'
import { formatMoney } from '../../format'
import { colors, spacing } from '../../theme'
import type { EquityAnchor } from '../../types/analytics'

const HEIGHT = 150
const PAD = { top: 10, bottom: 10, left: 4, right: 8 }

/** Account balance after each closed trade: one line, area fill, and an emphasised last point. */
export function EquityChart({ points, startingBalance }: { points: EquityAnchor[]; startingBalance: number }) {
  const [width, setWidth] = useState(0)
  const onLayout = (e: LayoutChangeEvent) => setWidth(Math.round(e.nativeEvent.layout.width))

  if (points.length < 2) {
    return <Text style={styles.empty}>Not enough closed trades to plot a curve.</Text>
  }

  const values = points.map((p) => p.equity)
  const lo = Math.min(...values, startingBalance)
  const hi = Math.max(...values, startingBalance)
  const span = hi - lo || 1
  const innerW = Math.max(1, width - PAD.left - PAD.right)
  const innerH = HEIGHT - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (i / (points.length - 1)) * innerW
  const y = (v: number) => PAD.top + (1 - (v - lo) / span) * innerH

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`).join(' ')
  const area = `${line} L${x(points.length - 1).toFixed(1)},${HEIGHT - PAD.bottom} L${x(0).toFixed(1)},${HEIGHT - PAD.bottom} Z`
  const last = points[points.length - 1]
  const up = last.equity >= points[0].equity
  const stroke = up ? colors.positive : colors.negative

  return (
    <View onLayout={onLayout}>
      {width > 0 ? (
        <Svg width={width} height={HEIGHT}>
          <Defs>
            <LinearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={stroke} stopOpacity={0.28} />
              <Stop offset="1" stopColor={stroke} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          {[0.25, 0.5, 0.75].map((f) => (
            <Line
              key={f}
              x1={PAD.left}
              x2={width - PAD.right}
              y1={PAD.top + f * innerH}
              y2={PAD.top + f * innerH}
              stroke={colors.borderSubtle}
              strokeWidth={1}
            />
          ))}
          {/* the starting balance, as a dashed reference */}
          <Line
            x1={PAD.left}
            x2={width - PAD.right}
            y1={y(startingBalance)}
            y2={y(startingBalance)}
            stroke={colors.textMuted}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <Path d={area} fill="url(#eqFill)" />
          <Path d={line} stroke={stroke} strokeWidth={2} fill="none" strokeLinejoin="round" strokeLinecap="round" />
          <Circle cx={x(points.length - 1)} cy={y(last.equity)} r={4} fill={stroke} />
        </Svg>
      ) : (
        <View style={{ height: HEIGHT }} />
      )}
      <View style={styles.axis}>
        <Text style={styles.axisText}>Low {formatMoney(lo, false)}</Text>
        <Text style={styles.axisText}>Dashed = starting balance</Text>
        <Text style={styles.axisText}>High {formatMoney(hi, false)}</Text>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  empty: { color: colors.textMuted, fontSize: 13, paddingVertical: spacing.lg },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.xs },
  axisText: { color: colors.textMuted, fontSize: 11 },
})
