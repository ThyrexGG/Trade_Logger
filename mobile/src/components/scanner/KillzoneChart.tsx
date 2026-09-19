import { useEffect, useMemo, useRef, useState } from 'react'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native'
import Svg, { Circle, G, Line, Polygon, Rect, Text as SvgText } from 'react-native-svg'
import { getCandles } from '../../api/market'
import { formatPrice } from '../../format'
import { buildSessions, nearestBarIndex, previousLevels, priceRange, spreadLabels } from '../../scanner/chartLogic'
import { colors, radius, spacing } from '../../theme'
import type { Candle } from '../../types/market'
import type { FairValueGap, KillzoneCandidate, LiquidityPool } from '../../types/scanner'

const VIEW_TFS = ['1m', '5m', '15m', '1h']
const HISTORY = [150, 300, 500]
const CHART_H = 320
const TIME_H = 18
const AXIS_W = 66
const STEP = 8 // px per candle
const BODY = 5
const TAG_H = 13
const PLOT_H = CHART_H - TIME_H

interface LevelLine {
  key: string
  price: number
  color: string
  dash?: string
  width: number
  tag: string
}

const rgba = (rgb: string, a: number) => `rgba(${rgb},${a})`
const pad2 = (n: number) => String(n).padStart(2, '0')
const hhmm = (unixSec: number) => {
  const d = new Date(unixSec * 1000)
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}
const dayLabel = (unixSec: number) => new Date(unixSec * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

/**
 * The scanner's findings drawn on the real candles (the website's chart, redrawn for a phone):
 * killzone session boxes, sweep + shift arrows per candidate, BSL/SSL liquidity levels, unmitigated
 * FVG edges with a dot on the confirming candle, previous day/week levels, and the focused
 * candidate's entry/stop/target. Scroll sideways for history, tap a candle for its prices.
 * Purely visual context — nothing here is computed apart from the scan, and there is no order path.
 */
export function KillzoneChart({
  symbol,
  ltf,
  candidates,
  liquidity,
  fvgs,
  focusedIndex,
}: {
  symbol: string
  ltf: string
  candidates: KillzoneCandidate[]
  liquidity: { bsl: LiquidityPool[]; ssl: LiquidityPool[] } | null
  fvgs: FairValueGap[]
  focusedIndex: number | null
}) {
  const [viewTf, setViewTf] = useState(ltf)
  const [count, setCount] = useState(300)
  const [showKz, setShowKz] = useState(true)
  const [candles, setCandles] = useState<Candle[]>([])
  const [source, setSource] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const scrollRef = useRef<ScrollView>(null)
  const viewW = useRef(0)
  const wantEnd = useRef(true)

  // a genuinely new scan configuration re-syncs the chart's timeframe
  useEffect(() => {
    setViewTf(ltf)
  }, [ltf])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    setPicked(null)
    wantEnd.current = true
    getCandles(symbol, viewTf, count, controller.signal)
      .then((r) => {
        if (controller.signal.aborted) return
        setCandles((r.candles ?? []).filter((c) => Number.isFinite(c.open) && Number.isFinite(c.close)))
        setSource(r.source)
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load the chart.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [symbol, viewTf, count])

  const real = source !== 'synthetic_fallback'
  const n = candles.length
  const contentW = n * STEP + 24
  const sessions = useMemo(() => (showKz ? buildSessions(candles) : []), [candles, showKz])
  const levels = useMemo(() => (showKz ? previousLevels(candles) : { prevDay: null, prevWeek: null }), [candles, showKz])
  const focused = focusedIndex != null ? (candidates[focusedIndex] ?? null) : null

  const { min, max } = useMemo(
    () =>
      priceRange(candles, [liquidity?.bsl?.[0]?.price, liquidity?.ssl?.[0]?.price, focused?.potential_target, focused?.shift_level, focused?.sweep_level]),
    [candles, liquidity, focused],
  )
  const yOf = (p: number) => ((max - p) / (max - min)) * PLOT_H
  const xOf = (i: number) => i * STEP + STEP / 2

  const lines = useMemo(() => {
    const out: LevelLine[] = []
    const add = (l: LevelLine) => {
      if (Number.isFinite(l.price)) out.push(l)
    }
    ;(liquidity?.bsl ?? []).forEach((p, i) => add({ key: `bsl${i}`, price: p.price, color: rgba('239,68,68', 0.7), dash: '5,4', width: 1, tag: 'BSL' }))
    ;(liquidity?.ssl ?? []).forEach((p, i) => add({ key: `ssl${i}`, price: p.price, color: rgba('34,197,94', 0.7), dash: '5,4', width: 1, tag: 'SSL' }))
    fvgs.forEach((f, i) => {
      const c = f.type === 'Bullish' ? rgba('34,197,94', 0.55) : rgba('239,68,68', 0.55)
      add({ key: `fvgt${i}`, price: f.top, color: c, dash: '2,3', width: 1, tag: 'FVG' })
      add({ key: `fvgb${i}`, price: f.bottom, color: c, dash: '2,3', width: 1, tag: 'FVG' })
    })
    if (levels.prevDay) {
      add({ key: 'pdh', price: levels.prevDay.high, color: rgba('59,130,246', 0.85), dash: '2,3', width: 1, tag: 'PDH' })
      add({ key: 'pdl', price: levels.prevDay.low, color: rgba('59,130,246', 0.85), dash: '2,3', width: 1, tag: 'PDL' })
    }
    if (levels.prevWeek) {
      add({ key: 'pwh', price: levels.prevWeek.high, color: rgba('168,85,247', 0.85), dash: '2,3', width: 1, tag: 'PWH' })
      add({ key: 'pwl', price: levels.prevWeek.low, color: rgba('168,85,247', 0.85), dash: '2,3', width: 1, tag: 'PWL' })
    }
    if (focused) {
      add({ key: 'entry', price: focused.shift_level, color: colors.accent, width: 2, tag: 'Entry' })
      add({ key: 'stop', price: focused.sweep_level, color: colors.negative, width: 2, tag: 'Stop' })
      if (focused.potential_target != null) add({ key: 'target', price: focused.potential_target, color: colors.positive, width: 2, tag: 'Target' })
    }
    if (n > 0) add({ key: 'last', price: candles[n - 1].close, color: colors.textSecondary, dash: '1,3', width: 1, tag: 'Last' })
    return out.filter((l) => l.price >= min && l.price <= max)
  }, [liquidity, fvgs, levels, focused, candles, n, min, max])

  const tagYs = useMemo(() => spreadLabels(lines.map((l) => yOf(l.price)), TAG_H, TAG_H / 2, PLOT_H - TAG_H / 2), [lines, min, max]) // eslint-disable-line react-hooks/exhaustive-deps

  const gridPrices = [0.1, 0.3, 0.5, 0.7, 0.9].map((f) => max - (max - min) * f)

  // scroll to the newest candle after each load, and to a candidate when one is picked
  useEffect(() => {
    if (!focused || n === 0) return
    const mid = (nearestBarIndex(candles, focused.sweep_time) + nearestBarIndex(candles, focused.shift_time)) / 2
    scrollRef.current?.scrollTo({ x: Math.max(0, xOf(mid) - viewW.current / 2), animated: true })
  }, [focusedIndex, n]) // eslint-disable-line react-hooks/exhaustive-deps

  const onLayout = (e: LayoutChangeEvent) => {
    viewW.current = e.nativeEvent.layout.width
  }

  const pickedCandle = picked != null ? candles[picked] : null
  const timeLabels: { i: number; text: string }[] = []
  {
    let lastDay = ''
    for (let i = 0; i < n; i += 12) {
      const day = dayLabel(candles[i].time)
      timeLabels.push({ i, text: day !== lastDay ? day : hhmm(candles[i].time) })
      lastDay = day
    }
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.controlRow}>
        <Text style={styles.label}>View</Text>
        {VIEW_TFS.map((t) => (
          <Pressable key={t} onPress={() => setViewTf(t)} style={[styles.chip, viewTf === t && styles.chipOn]} accessibilityRole="button">
            <Text style={[styles.chipText, viewTf === t && styles.chipTextOn]}>{t}</Text>
          </Pressable>
        ))}
        <Pressable onPress={() => setShowKz((v) => !v)} style={[styles.chip, showKz && styles.chipOn]} accessibilityRole="button">
          <Text style={[styles.chipText, showKz && styles.chipTextOn]}>Killzones</Text>
        </Pressable>
      </View>
      <View style={styles.controlRow}>
        <Text style={styles.label}>History</Text>
        {HISTORY.map((h) => (
          <Pressable key={h} onPress={() => setCount(h)} style={[styles.chip, count === h && styles.chipOn]} accessibilityRole="button">
            <Text style={[styles.chipText, count === h && styles.chipTextOn]}>{h} bars</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.readout} numberOfLines={1}>
        {pickedCandle
          ? `${dayLabel(pickedCandle.time)} ${hhmm(pickedCandle.time)} · O ${formatPrice(pickedCandle.open)} H ${formatPrice(pickedCandle.high)} L ${formatPrice(pickedCandle.low)} C ${formatPrice(pickedCandle.close)}`
          : n > 0
            ? 'Tap a candle for its prices · scroll sideways for history'
            : ' '}
      </Text>

      {error ? (
        <Text style={styles.error}>{error}</Text>
      ) : !real ? (
        <Text style={styles.error}>The price feed is offline, so there is no real chart to show right now.</Text>
      ) : n === 0 ? (
        <View style={[styles.empty, { height: CHART_H }]}>{loading ? <ActivityIndicator color={colors.accent} /> : <Text style={styles.muted}>No candles for {symbol}.</Text>}</View>
      ) : (
        <View style={[styles.plot, { height: CHART_H }]}>
          <ScrollView
            ref={scrollRef}
            horizontal
            showsHorizontalScrollIndicator={false}
            style={{ flex: 1 }}
            onLayout={onLayout}
            onContentSizeChange={() => {
              if (wantEnd.current) {
                wantEnd.current = false
                scrollRef.current?.scrollToEnd({ animated: false })
              }
            }}
          >
            <Pressable
              onPress={(e) => {
                const i = Math.floor(e.nativeEvent.locationX / STEP)
                setPicked(i >= 0 && i < n ? i : null)
              }}
              accessibilityLabel="Candle chart"
            >
              <Svg width={contentW} height={CHART_H}>
                {gridPrices.map((p, i) => (
                  <Line key={`g${i}`} x1={0} x2={contentW} y1={yOf(p)} y2={yOf(p)} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
                ))}

                {sessions.map((s, i) => {
                  const x1 = xOf(nearestBarIndex(candles, s.from)) - STEP / 2
                  const x2 = xOf(nearestBarIndex(candles, s.to)) + STEP / 2
                  const top = yOf(s.high)
                  const bottom = yOf(s.low)
                  return (
                    <G key={`s${i}`}>
                      <Rect x={x1} y={top} width={Math.max(x2 - x1, 2)} height={Math.max(bottom - top, 1)} fill={rgba(s.rgb, 0.1)} stroke={rgba(s.rgb, 0.45)} strokeWidth={1} />
                      <SvgText x={x1 + 3} y={Math.max(top - 3, 9)} fontSize={9} fill={rgba(s.rgb, 0.95)}>
                        {s.name}
                      </SvgText>
                      {(['high', 'low'] as const).map((side) => {
                        const price = side === 'high' ? s.high : s.low
                        const takenAt = side === 'high' ? s.highTakenAt : s.lowTakenAt
                        const endX = takenAt == null ? contentW : xOf(nearestBarIndex(candles, takenAt))
                        return (
                          <Line
                            key={side}
                            x1={x2}
                            x2={endX}
                            y1={yOf(price)}
                            y2={yOf(price)}
                            stroke={rgba(s.rgb, takenAt == null ? 0.75 : 0.3)}
                            strokeWidth={1}
                            strokeDasharray={takenAt == null ? undefined : '3,3'}
                          />
                        )
                      })}
                    </G>
                  )
                })}

                {candles.map((c, i) => {
                  const up = c.close >= c.open
                  const col = up ? colors.positive : colors.negative
                  const x = xOf(i)
                  const yTop = yOf(Math.max(c.open, c.close))
                  const yBot = yOf(Math.min(c.open, c.close))
                  return (
                    <G key={c.time}>
                      <Line x1={x} x2={x} y1={yOf(c.high)} y2={yOf(c.low)} stroke={col} strokeWidth={1} />
                      <Rect x={x - BODY / 2} y={yTop} width={BODY} height={Math.max(yBot - yTop, 1)} fill={col} />
                    </G>
                  )
                })}

                {lines.map((l) => (
                  <Line key={l.key} x1={0} x2={contentW} y1={yOf(l.price)} y2={yOf(l.price)} stroke={l.color} strokeWidth={l.width} strokeDasharray={l.dash} />
                ))}

                {fvgs.map((f, i) => {
                  const idx = nearestBarIndex(candles, f.creation_time)
                  const col = f.type === 'Bullish' ? colors.positive : colors.negative
                  return <Circle key={`f${i}`} cx={xOf(idx)} cy={yOf(candles[idx].close)} r={3} fill={col} stroke="#000" strokeWidth={0.8} />
                })}

                {candidates.map((c, i) => {
                  const bull = c.direction === 'bullish'
                  const isFocused = focusedIndex === i
                  const dim = focusedIndex != null && !isFocused
                  const events = [
                    { idx: nearestBarIndex(candles, c.sweep_time), letter: 'S', color: colors.textPrimary, text: `Sweep ${formatPrice(c.sweep_level)}` },
                    { idx: nearestBarIndex(candles, c.shift_time), letter: 'M', color: bull ? colors.positive : colors.negative, text: `MSS ${formatPrice(c.shift_level)}` },
                  ]
                  return (
                    <G key={`c${i}`} opacity={dim ? 0.3 : 1}>
                      {events.map((ev) => {
                        const cd = candles[ev.idx]
                        const x = xOf(ev.idx)
                        const y = bull ? yOf(cd.low) + 3 : yOf(cd.high) - 3
                        const pts = bull ? `${x},${y} ${x - 4.5},${y + 8} ${x + 4.5},${y + 8}` : `${x},${y} ${x - 4.5},${y - 8} ${x + 4.5},${y - 8}`
                        return (
                          <G key={ev.letter}>
                            <Polygon points={pts} fill={ev.color} />
                            <SvgText x={x} y={bull ? y + 18 : y - 11} fontSize={9} fontWeight="bold" fill={ev.color} textAnchor="middle">
                              {isFocused ? ev.text : ev.letter}
                            </SvgText>
                          </G>
                        )
                      })}
                    </G>
                  )
                })}

                {picked != null ? <Line x1={xOf(picked)} x2={xOf(picked)} y1={0} y2={PLOT_H} stroke="rgba(255,255,255,0.45)" strokeWidth={1} /> : null}

                {timeLabels.map((t) => (
                  <SvgText key={`t${t.i}`} x={xOf(t.i)} y={CHART_H - 5} fontSize={9} fill={colors.textMuted} textAnchor="middle">
                    {t.text}
                  </SvgText>
                ))}
              </Svg>
            </Pressable>
          </ScrollView>

          <Svg width={AXIS_W} height={CHART_H} style={styles.axis}>
            {gridPrices.map((p, i) => {
              const y = yOf(p)
              if (lines.some((_, k) => Math.abs(tagYs[k] - y) < TAG_H)) return null
              return (
                <SvgText key={`a${i}`} x={AXIS_W - 4} y={y + 3} fontSize={9} fill={colors.textMuted} textAnchor="end">
                  {formatPrice(p)}
                </SvgText>
              )
            })}
            {lines.map((l, i) => (
              <G key={l.key}>
                <Rect x={1} y={tagYs[i] - TAG_H / 2} width={AXIS_W - 2} height={TAG_H} rx={3} fill="#0a0a0a" stroke={l.color} strokeWidth={1} />
                <SvgText x={AXIS_W - 5} y={tagYs[i] + 3} fontSize={8.5} fill={colors.textPrimary} textAnchor="end">
                  {`${l.tag} ${formatPrice(l.price)}`}
                </SvgText>
              </G>
            ))}
          </Svg>
        </View>
      )}

      <Text style={styles.muted}>
        {`S = liquidity sweep · M = market-structure shift · dot = the candle that confirmed a fair value gap${
          source && real ? ` · prices from ${source}${viewTf !== ltf ? ` · chart shows ${viewTf}, scan is ${ltf}` : ''}` : ''
        }.`}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  controlRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  label: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6, marginRight: spacing.xs, width: 52 },
  chip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 5 },
  chipOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: '600' },
  chipTextOn: { color: colors.accent },
  readout: { color: colors.textSecondary, fontSize: 11, fontVariant: ['tabular-nums'] },
  plot: { flexDirection: 'row', backgroundColor: '#0d0d0d', borderColor: colors.borderSubtle, borderWidth: 1, borderRadius: radius.md, overflow: 'hidden' },
  axis: { backgroundColor: '#0d0d0d', borderLeftColor: colors.borderSubtle, borderLeftWidth: 1 },
  empty: { alignItems: 'center', justifyContent: 'center' },
  muted: { color: colors.textMuted, fontSize: 11, lineHeight: 16 },
  error: { color: colors.negative, fontSize: 13 },
})
