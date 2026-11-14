import { Ionicons } from '@expo/vector-icons'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshControl, ScrollView, Share, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { scanKillzone } from '../api/scanner'
import { KillzoneChart } from '../components/scanner/KillzoneChart'
import { Text, TextInput } from '../components/Text'
import { Button, Card, Chip, ChipRow, Fact, Footnote, Loading, MoreDetails, Notice, Pill, Rows, SectionLabel, Seg, ui } from '../components/ui'
import { formatPrice } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { buildScanMarkdown } from '../scanner/markdown'
import { colors, spacing, type } from '../theme'
import type { KillzoneCandidate, KillzoneScanResponse } from '../types/scanner'

const LTF_OPTIONS = [
  { key: '1m', label: '1m' },
  { key: '5m', label: '5m' },
  { key: '15m', label: '15m' },
  { key: '1h', label: '1h' },
]
const SYMBOL_CHIPS = ['USDJPY', 'EURUSD', 'GBPUSD', 'XAUUSD', 'GBPJPY', 'EURJPY', 'AUDUSD', 'USDCAD', 'XAGUSD', 'NAS100', 'SPX500']
const REFRESH_MS = 5 * 60 * 1000
const SYMBOL_KEY = 'tl.scanner.symbol'
const LTF_KEY = 'tl.scanner.ltf'

const fmtTime = (unixSec: number) =>
  new Date(unixSec * 1000).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

/** up / down / unclear: a direction of the market, not money, so it stays neutral; the word carries it */
const biasWord = (bias: string | null | undefined) => (bias === 'bullish' ? 'Up' : bias === 'bearish' ? 'Down' : 'Unclear')
const biasIcon = (bias: string | null | undefined) => (bias === 'bullish' ? 'trending-up' : bias === 'bearish' ? 'trending-down' : 'remove') as 'trending-up' | 'trending-down' | 'remove'

/** The plan note "Plan this" pre-fills — the same numbers the candidate card shows, laid out as text. */
function planFor(symbol: string, ltf: string, data: KillzoneScanResponse, c: KillzoneCandidate) {
  const lines: (string | null)[] = [
    `${c.direction.toUpperCase()} idea on ${symbol} (${ltf}, bias timeframe ${data.htf ?? '1h'})`,
    `Killzone: ${c.killzone} · ${c.agrees_with_htf_bias ? 'agrees with' : 'conflicts with'} the ${data.htf_bias ?? 'unknown'} higher-timeframe bias`,
    `Sweep ${c.sweep_level} (${fmtTime(c.sweep_time)}), then structure shift ${c.shift_level} (${fmtTime(c.shift_time)})`,
    c.potential_entry != null && c.potential_stop != null
      ? `Entry ${c.potential_entry} · stop ${c.potential_stop}${c.potential_target != null ? ` · target ${c.potential_target} (R:R ${c.risk_reward})` : ' · no target nearby'}`
      : null,
    `Confluence ${c.confluence_score}/5: ${(c.confluence_factors ?? []).map((f) => `${f.met ? '✓' : '✗'} ${f.label}`).join(', ')}`,
    '',
    'Why I would / would not take it:',
  ]
  return {
    kind: 'plan' as const,
    instrument: symbol,
    title: `${symbol} ${c.direction} plan`,
    body: lines.filter((l): l is string => l !== null).join('\n'),
    tags: ['killzone'],
  }
}

/** Five steps filled to the score: how many of the five checks a setup passes. */
function Score({ n }: { n: number }) {
  const score = Math.max(0, Math.min(5, n ?? 0))
  return (
    <View style={styles.score} accessibilityLabel={`${score} of 5 checks passed`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <View key={i} style={[styles.scoreStep, i <= score && styles.scoreStepOn]} />
      ))}
      <Text style={styles.scoreText}>{score}/5 checks</Text>
    </View>
  )
}

function Candidate({ c, shown, onShow, onPlan }: { c: KillzoneCandidate; shown: boolean; onShow: () => void; onPlan: () => void }) {
  const [open, setOpen] = useState(false)
  const up = c.direction === 'bullish'
  return (
    <Card flush>
      <View style={styles.candHead}>
        <View style={ui.rowWrap}>
          <Ionicons name={up ? 'trending-up' : 'trending-down'} size={16} color={colors.textPrimary} />
          <Text style={ui.heading}>{up ? 'Possible buy' : 'Possible sell'}</Text>
          <Pill text={c.killzone} color={colors.textSecondary} />
          <Pill text={c.agrees_with_htf_bias ? 'With the trend' : 'Against the trend'} color={c.agrees_with_htf_bias ? colors.textSecondary : colors.warning} />
        </View>
        <Score n={c.confluence_score} />
      </View>
      <Rows inset={0}>
        {c.potential_entry != null && c.potential_stop != null ? <Fact label="Entry" value={formatPrice(c.potential_entry)} /> : null}
        {c.potential_entry != null && c.potential_stop != null ? <Fact label="Stop" value={formatPrice(c.potential_stop)} /> : null}
        {c.potential_entry != null && c.potential_stop != null ? (
          <Fact label="Target" value={c.potential_target != null ? `${formatPrice(c.potential_target)} · R:R ${c.risk_reward}` : 'none nearby'} />
        ) : null}
      </Rows>
      <MoreDetails open={open} onToggle={() => setOpen((o) => !o)} hint="what price did, which checks passed">
        <Rows inset={0}>
          <Fact label={`Stops taken · ${fmtTime(c.sweep_time)}`} value={formatPrice(c.sweep_level)} />
          <Fact label={`Turned · ${fmtTime(c.shift_time)}`} value={formatPrice(c.shift_level)} />
        </Rows>
        <View style={styles.factors}>
          {(c.confluence_factors ?? []).map((f) => (
            <View key={f.label} style={styles.factor}>
              <Ionicons name={f.met ? 'checkmark' : 'close'} size={14} color={f.met ? colors.textPrimary : colors.textMuted} />
              <Text style={[ui.sub, ui.flex, !f.met && { color: colors.textMuted }]}>{f.label}</Text>
            </View>
          ))}
        </View>
      </MoreDetails>
      <View style={styles.candActions}>
        <Button label={shown ? 'Hide from chart' : 'Show on chart'} kind="secondary" size="sm" onPress={onShow} style={ui.flex} />
        <Button label="Plan this" kind="secondary" size="sm" icon="document-text-outline" onPress={onPlan} style={ui.flex} />
      </View>
    </Card>
  )
}

/** Find setups: flags places where price took out stops and then turned. Pattern-flagging only — never a signal. */
export function KillzoneScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [symbol, setSymbol] = useState('USDJPY')
  const [ltf, setLtf] = useState('15m')
  const [data, setData] = useState<KillzoneScanResponse | null>(null)
  const [scanned, setScanned] = useState<{ symbol: string; ltf: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [focused, setFocused] = useState<number | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const pageRef = useRef<ScrollView>(null)
  const chartY = useRef(0)
  const inFlight = useRef<AbortController | null>(null)
  const prefsLoaded = useRef(false)
  const symbolRef = useRef(symbol)
  const ltfRef = useRef(ltf)
  symbolRef.current = symbol
  ltfRef.current = ltf

  const scan = useCallback((sym: string, tf: string) => {
    const s = sym.trim().toUpperCase()
    if (s.length < 2) return
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setLoading(true)
    setError(null)
    scanKillzone(s, tf, controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return
        if (!res.ok) {
          setError(res.error ?? 'The scan failed.')
          return
        }
        setData(res)
        setFocused(null)
        setScanned({ symbol: s, ltf: tf })
        AsyncStorage.multiSet([[SYMBOL_KEY, s], [LTF_KEY, tf]]).catch(() => {})
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'The scan failed.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [])

  // restore the last symbol / timeframe, then scan whenever the screen is showing (and every 5 min while it is)
  useFocusEffect(
    useCallback(() => {
      let timer: ReturnType<typeof setInterval> | null = null
      let cancelled = false
      ;(async () => {
        if (!prefsLoaded.current) {
          try {
            const [s, t] = await Promise.all([AsyncStorage.getItem(SYMBOL_KEY), AsyncStorage.getItem(LTF_KEY)])
            if (s) {
              setSymbol(s)
              symbolRef.current = s
            }
            if (t) {
              setLtf(t)
              ltfRef.current = t
            }
          } catch {
            /* defaults */
          }
          prefsLoaded.current = true
        }
        if (cancelled) return
        scan(symbolRef.current, ltfRef.current)
        timer = setInterval(() => scan(symbolRef.current, ltfRef.current), REFRESH_MS)
      })()
      return () => {
        cancelled = true
        if (timer) clearInterval(timer)
        inFlight.current?.abort()
      }
    }, [scan]),
  )

  useEffect(() => () => inFlight.current?.abort(), [])

  const bsl = data?.htf_liquidity_targets?.bsl ?? []
  const ssl = data?.htf_liquidity_targets?.ssl ?? []

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <ScrollView
        ref={pageRef}
        contentContainerStyle={ui.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={() => scan(symbol, ltf)} tintColor={colors.accent} colors={[colors.accent]} />}
      >
        <Card>
          <View style={ui.cols}>
            <TextInput
              value={symbol}
              onChangeText={setSymbol}
              placeholder="Market, e.g. USDJPY"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="characters"
              autoCorrect={false}
              onSubmitEditing={() => scan(symbol, ltf)}
              accessibilityLabel="Market symbol"
              style={[ui.input, ui.flex]}
            />
            <Button label="Scan" icon="scan-outline" busy={loading} onPress={() => scan(symbol, ltf)} style={styles.scanBtn} />
          </View>
          <ChipRow>
            {SYMBOL_CHIPS.map((s) => (
              <Chip
                key={s}
                label={s}
                on={symbol.toUpperCase() === s}
                onPress={() => {
                  setSymbol(s)
                  scan(s, ltf)
                }}
              />
            ))}
          </ChipRow>
          <View style={styles.field}>
            <Text style={ui.fieldLabel}>Chart timeframe</Text>
            <Seg
              options={LTF_OPTIONS}
              value={ltf}
              onChange={(t) => {
                setLtf(t)
                scan(symbol, t)
              }}
            />
          </View>
          {data ? (
            <Text style={styles.updated}>
              Updated {new Date(data.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} · refreshes every 5 min while open
            </Text>
          ) : null}
        </Card>

        {error ? <Notice>{error}</Notice> : null}

        {data && scanned ? (
          <>
            <Card title="The bigger picture" right={data.htf ?? undefined} flush>
              <View style={styles.bias}>
                <Ionicons name={biasIcon(data.htf_bias)} size={22} color={colors.textPrimary} />
                <View style={ui.flex}>
                  <Text style={ui.heading}>Trend: {biasWord(data.htf_bias).toLowerCase()}</Text>
                  <Text style={ui.muted}>
                    {data.current_killzone ? `Session now: ${data.current_killzone}` : 'No active session window right now'}
                    {data.bias_alignment ? ` · ${data.bias_alignment.bullish} up, ${data.bias_alignment.bearish} down of ${data.bias_alignment.usable} timeframes` : ''}
                  </Text>
                </View>
              </View>
              <MoreDetails open={detailOpen} onToggle={() => setDetailOpen((o) => !o)} hint="each timeframe, nearby stop levels, gaps">
                {data.htf_structure ? (
                  <View style={styles.detailBlock}>
                    <Text style={ui.sub}>{data.htf_structure.recent_sequence}</Text>
                    <Text style={ui.muted}>
                      Last break: {data.htf_structure.last_break} · swing high {data.htf_structure.last_swing_high != null ? formatPrice(data.htf_structure.last_swing_high) : '—'} · swing low{' '}
                      {data.htf_structure.last_swing_low != null ? formatPrice(data.htf_structure.last_swing_low) : '—'}
                    </Text>
                  </View>
                ) : null}
                {data.bias_ladder.length > 0 ? (
                  <Rows inset={0}>
                    {data.bias_ladder.map((r) => (
                      <Fact key={r.timeframe} label={r.timeframe} value={r.sufficient ? biasWord(r.bias) : 'not enough bars'} />
                    ))}
                  </Rows>
                ) : null}
                <View style={styles.detailBlock}>
                  <Text style={styles.detailLabel}>Stops resting above price</Text>
                  {bsl.length === 0 ? <Text style={ui.muted}>None nearby.</Text> : null}
                  {bsl.map((p, i) => (
                    <Text key={`b${i}`} style={ui.sub}>
                      <Text style={ui.num}>{formatPrice(p.price)}</Text> · {formatPrice(p.distance_from_price)} away · {p.source}
                    </Text>
                  ))}
                  <Text style={[styles.detailLabel, { marginTop: spacing.sm }]}>Stops resting below price</Text>
                  {ssl.length === 0 ? <Text style={ui.muted}>None nearby.</Text> : null}
                  {ssl.map((p, i) => (
                    <Text key={`s${i}`} style={ui.sub}>
                      <Text style={ui.num}>{formatPrice(p.price)}</Text> · {formatPrice(p.distance_from_price)} away · {p.source}
                    </Text>
                  ))}
                  <Text style={[styles.detailLabel, { marginTop: spacing.sm }]}>Unfilled price gaps</Text>
                  {data.recent_unmitigated_fvgs.length === 0 ? <Text style={ui.muted}>None right now.</Text> : null}
                  {data.recent_unmitigated_fvgs.map((f, i) => (
                    <Text key={i} style={ui.sub}>
                      {f.type === 'Bullish' ? 'Up' : 'Down'} gap{' '}
                      <Text style={ui.num}>
                        {formatPrice(f.bottom)}–{formatPrice(f.top)}
                      </Text>{' '}
                      · {f.age_candles} candles ago
                    </Text>
                  ))}
                </View>
              </MoreDetails>
            </Card>

            <View onLayout={(e) => { chartY.current = e.nativeEvent.layout.y }}>
              <Card title={`${scanned.symbol} chart`} right={scanned.ltf}>
                <KillzoneChart symbol={scanned.symbol} ltf={scanned.ltf} candidates={data.candidates} liquidity={data.htf_liquidity_targets} fvgs={data.recent_unmitigated_fvgs} focusedIndex={focused} />
              </Card>
            </View>

            <SectionLabel right={String(data.candidates.length)}>Possible setups</SectionLabel>
            {data.candidates.length === 0 ? <Text style={ui.muted}>None in the recent window. That is normal: most of the time there is nothing to do.</Text> : null}
            {data.candidates.map((c, i) => (
              <Candidate
                key={`${c.shift_time}-${i}`}
                c={c}
                shown={focused === i}
                onShow={() => {
                  setFocused(focused === i ? null : i)
                  pageRef.current?.scrollTo({ y: Math.max(0, chartY.current - 8), animated: true })
                }}
                onPlan={() => navigation.navigate('Entry', { prefill: planFor(scanned.symbol, scanned.ltf, data, c) })}
              />
            ))}

            <Button label="Share this scan" kind="ghost" size="sm" icon="share-outline" onPress={() => void Share.share({ message: buildScanMarkdown(data, scanned?.ltf ?? ltf) }).catch(() => {})} />
            <Footnote>{data.disclaimer ?? 'Pattern-flagging only. Not a signal and not a recommendation. Nothing here places a trade.'}</Footnote>
          </>
        ) : loading ? (
          <Loading />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  scanBtn: { minWidth: 104 },
  field: { gap: 6 },
  updated: { ...type.small, fontSize: 11 },
  bias: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  detailBlock: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, gap: 4, borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  detailLabel: { ...type.label },
  candHead: { paddingHorizontal: spacing.lg, paddingTop: spacing.md + 2, paddingBottom: spacing.md, gap: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.borderSubtle },
  score: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  scoreStep: { width: 18, height: 5, borderRadius: 2, backgroundColor: colors.surfaceElevated },
  scoreStepOn: { backgroundColor: colors.accent },
  scoreText: { ...type.small, fontSize: 11, marginLeft: spacing.sm, fontVariant: ['tabular-nums'] },
  factors: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, gap: 5, borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  factor: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  candActions: { flexDirection: 'row', gap: spacing.sm, padding: spacing.lg, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.borderSubtle },
})
