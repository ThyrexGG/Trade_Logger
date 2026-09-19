import AsyncStorage from '@react-native-async-storage/async-storage'
import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { scanKillzone } from '../api/scanner'
import { formatPrice } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { KillzoneCandidate, KillzoneScanResponse } from '../types/scanner'

const LTF_OPTIONS = ['1m', '5m', '15m', '1h']
const SYMBOL_CHIPS = ['USDJPY', 'EURUSD', 'GBPUSD', 'XAUUSD', 'GBPJPY', 'EURJPY', 'AUDUSD', 'USDCAD', 'XAGUSD']
const REFRESH_MS = 5 * 60 * 1000
const SYMBOL_KEY = 'tl.scanner.symbol'
const LTF_KEY = 'tl.scanner.ltf'

const fmtTime = (unixSec: number) =>
  new Date(unixSec * 1000).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

const stars = (score: number) => {
  const n = Math.max(0, Math.min(5, score ?? 0))
  return '★'.repeat(n) + '☆'.repeat(5 - n)
}

function biasColor(bias: string | null | undefined): string {
  return bias === 'bullish' ? colors.positive : bias === 'bearish' ? colors.negative : colors.textSecondary
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      {children}
    </View>
  )
}

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <View style={[styles.pill, { borderColor: color }]}>
      <Text style={[styles.pillText, { color }]}>{text}</Text>
    </View>
  )
}

/** The plan note "Plan this" pre-fills — the same numbers the candidate card shows, laid out as text. */
function planFor(symbol: string, ltf: string, data: KillzoneScanResponse, c: KillzoneCandidate) {
  const lines: (string | null)[] = [
    `${c.direction.toUpperCase()} idea on ${symbol} (${ltf}, bias timeframe ${data.htf ?? '1h'})`,
    `Killzone: ${c.killzone} · ${c.agrees_with_htf_bias ? 'agrees with' : 'conflicts with'} the ${data.htf_bias ?? 'unknown'} higher-timeframe bias`,
    `Sweep ${c.sweep_level} (${fmtTime(c.sweep_time)}) → structure shift ${c.shift_level} (${fmtTime(c.shift_time)})`,
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

/** Killzone scanner: flags candidate liquidity-sweep + market-structure-shift events. Pattern-flagging only — never a signal. */
export function KillzoneScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [symbol, setSymbol] = useState('USDJPY')
  const [ltf, setLtf] = useState('15m')
  const [data, setData] = useState<KillzoneScanResponse | null>(null)
  const [scanned, setScanned] = useState<{ symbol: string; ltf: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
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
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={() => scan(symbol, ltf)} tintColor={colors.accent} />}
      >
        <Card title="Scan">
          <TextInput
            value={symbol}
            onChangeText={setSymbol}
            placeholder="Symbol, e.g. USDJPY"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="characters"
            autoCorrect={false}
            onSubmitEditing={() => scan(symbol, ltf)}
            style={styles.input}
          />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
            {SYMBOL_CHIPS.map((s) => (
              <Pressable
                key={s}
                onPress={() => {
                  setSymbol(s)
                  scan(s, ltf)
                }}
                style={[styles.chip, symbol.toUpperCase() === s && styles.chipOn]}
                accessibilityRole="button"
              >
                <Text style={[styles.chipText, symbol.toUpperCase() === s && styles.chipTextOn]}>{s}</Text>
              </Pressable>
            ))}
          </ScrollView>
          <View style={styles.ltfRow}>
            <Text style={styles.label}>Entry timeframe</Text>
            {LTF_OPTIONS.map((t) => (
              <Pressable
                key={t}
                onPress={() => {
                  setLtf(t)
                  scan(symbol, t)
                }}
                style={[styles.chip, ltf === t && styles.chipOn]}
                accessibilityRole="button"
              >
                <Text style={[styles.chipText, ltf === t && styles.chipTextOn]}>{t}</Text>
              </Pressable>
            ))}
          </View>
          <Pressable onPress={() => scan(symbol, ltf)} disabled={loading} style={[styles.primary, loading && { opacity: 0.6 }]} accessibilityRole="button">
            {loading ? <ActivityIndicator color="#000" /> : <Text style={styles.primaryText}>Scan now</Text>}
          </Pressable>
          {data ? (
            <Text style={styles.muted}>
              Updated {new Date(data.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} · auto-refreshes every 5 min while open · data {data.ltf_source ?? '?'} / {data.htf_source ?? '?'}
            </Text>
          ) : null}
        </Card>

        {error ? (
          <View style={styles.errBox}>
            <Text style={styles.errText}>{error}</Text>
          </View>
        ) : null}

        {data && scanned ? (
          <>
            <Card title="Higher-timeframe bias">
              <View style={styles.rowWrap}>
                <Pill text={(data.htf_bias ?? 'unknown').toUpperCase()} color={biasColor(data.htf_bias)} />
                {data.current_killzone ? <Pill text={data.current_killzone} color={colors.accent} /> : null}
                {data.bias_alignment ? (
                  <Pill
                    text={`${data.bias_alignment.verdict} · ${data.bias_alignment.bullish}▲ ${data.bias_alignment.bearish}▼ of ${data.bias_alignment.usable}`}
                    color={biasColor(data.bias_alignment.verdict)}
                  />
                ) : null}
              </View>
              {data.htf_structure ? (
                <>
                  <Text style={styles.body}>{data.htf_structure.recent_sequence}</Text>
                  <Text style={styles.muted}>
                    Last break: {data.htf_structure.last_break} · swing high {data.htf_structure.last_swing_high != null ? formatPrice(data.htf_structure.last_swing_high) : '—'} · swing low{' '}
                    {data.htf_structure.last_swing_low != null ? formatPrice(data.htf_structure.last_swing_low) : '—'}
                  </Text>
                </>
              ) : null}
              {data.bias_ladder.length > 0 ? (
                <View style={{ gap: 4, marginTop: spacing.xs }}>
                  {data.bias_ladder.map((r) => (
                    <View key={r.timeframe} style={styles.rung}>
                      <Text style={styles.rungTf}>{r.timeframe}</Text>
                      <Text style={[styles.rungBias, { color: biasColor(r.bias) }]}>{r.sufficient ? r.bias : 'not enough bars'}</Text>
                      <Text style={styles.rungSeq} numberOfLines={1}>
                        {r.sufficient ? (r.recent_sequence ?? '') : ''}
                      </Text>
                    </View>
                  ))}
                </View>
              ) : null}
            </Card>

            <Card title="Draw on liquidity">
              {bsl.length === 0 && ssl.length === 0 ? <Text style={styles.muted}>None nearby.</Text> : null}
              {bsl.map((p, i) => (
                <Text key={`b${i}`} style={styles.body}>
                  BSL {formatPrice(p.price)} <Text style={styles.muted}>· {formatPrice(p.distance_from_price)} away · {p.source}</Text>
                </Text>
              ))}
              {ssl.map((p, i) => (
                <Text key={`s${i}`} style={styles.body}>
                  SSL {formatPrice(p.price)} <Text style={styles.muted}>· {formatPrice(p.distance_from_price)} away · {p.source}</Text>
                </Text>
              ))}
            </Card>

            <Text style={styles.section}>Candidate events · {data.candidates.length}</Text>
            {data.candidates.length === 0 ? <Text style={styles.muted}>None in the recent window.</Text> : null}
            {data.candidates.map((c, i) => {
              const dc = c.direction === 'bullish' ? colors.positive : colors.negative
              return (
                <View key={`${c.shift_time}-${i}`} style={styles.cand}>
                  <View style={styles.rowWrap}>
                    <Pill text={c.direction.toUpperCase()} color={dc} />
                    <Pill text={c.killzone} color={colors.accent} />
                    <Pill text={c.agrees_with_htf_bias ? 'with HTF bias' : 'against HTF bias'} color={c.agrees_with_htf_bias ? colors.positive : colors.warning} />
                  </View>
                  <Text style={styles.body}>
                    Sweep {formatPrice(c.sweep_level)} <Text style={styles.muted}>({fmtTime(c.sweep_time)})</Text>
                    {'\n'}Shift {formatPrice(c.shift_level)} <Text style={styles.muted}>({fmtTime(c.shift_time)})</Text>
                  </Text>
                  {c.potential_entry != null && c.potential_stop != null ? (
                    <Text style={styles.plan}>
                      Entry {formatPrice(c.potential_entry)} · Stop {formatPrice(c.potential_stop)}
                      {c.potential_target != null ? ` · Target ${formatPrice(c.potential_target)} · R:R ${c.risk_reward}` : ' · no target nearby'}
                    </Text>
                  ) : null}
                  <Text style={[styles.stars, { color: c.confluence_score >= 4 ? colors.positive : c.confluence_score >= 2 ? colors.warning : colors.textMuted }]}>
                    {stars(c.confluence_score)} <Text style={styles.muted}>confluence {c.confluence_score}/5</Text>
                  </Text>
                  <View style={{ gap: 1 }}>
                    {(c.confluence_factors ?? []).map((f) => (
                      <Text key={f.label} style={[styles.factor, { color: f.met ? colors.positive : colors.textMuted }]}>
                        {f.met ? '✓' : '✗'} {f.label}
                      </Text>
                    ))}
                  </View>
                  <Pressable
                    onPress={() => navigation.navigate('Entry', { prefill: planFor(scanned.symbol, scanned.ltf, data, c) })}
                    style={styles.planBtn}
                    accessibilityRole="button"
                  >
                    <Text style={styles.planBtnText}>Plan this</Text>
                  </Pressable>
                </View>
              )
            })}

            <Card title="Unmitigated fair value gaps">
              {data.recent_unmitigated_fvgs.length === 0 ? <Text style={styles.muted}>None currently.</Text> : null}
              {data.recent_unmitigated_fvgs.map((f, i) => (
                <Text key={i} style={styles.body}>
                  <Text style={{ color: f.type === 'Bullish' ? colors.positive : colors.negative }}>{f.type}</Text> {formatPrice(f.bottom)}–{formatPrice(f.top)}{' '}
                  <Text style={styles.muted}>· {f.age_candles} candles ago</Text>
                </Text>
              ))}
            </Card>

            <Text style={styles.disclaimer}>
              {data.disclaimer ?? 'Pattern-flagging only — not a signal and not a recommendation. Nothing here places a trade.'}
            </Text>
          </>
        ) : loading ? (
          <ActivityIndicator color={colors.accent} size="large" style={{ marginTop: spacing.xl }} />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  cardTitle: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  input: {
    color: colors.textPrimary,
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
  },
  chips: { gap: spacing.sm, paddingRight: spacing.lg },
  chip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  chipOn: { borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.12)' },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: '600' },
  chipTextOn: { color: colors.accent },
  ltfRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  label: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6, marginRight: spacing.xs },
  primary: { backgroundColor: colors.accent, borderRadius: radius.md, alignItems: 'center', paddingVertical: spacing.md },
  primaryText: { color: '#000', fontWeight: '700', fontSize: 15 },
  muted: { color: colors.textMuted, fontSize: 12 },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  errBox: { backgroundColor: 'rgba(239,68,68,0.1)', borderColor: 'rgba(239,68,68,0.4)', borderWidth: 1, borderRadius: radius.md, padding: spacing.md },
  errText: { color: colors.negative, fontSize: 13 },
  rowWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, alignItems: 'center' },
  pill: { borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 7, paddingVertical: 2 },
  pillText: { fontSize: 11, fontWeight: '700' },
  rung: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  rungTf: { color: colors.textPrimary, fontSize: 13, fontWeight: '700', width: 32 },
  rungBias: { fontSize: 13, width: 96 },
  rungSeq: { color: colors.textMuted, fontSize: 11, flex: 1 },
  section: { color: colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, marginTop: spacing.sm },
  cand: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  plan: { color: colors.textPrimary, fontSize: 13, fontVariant: ['tabular-nums'] },
  stars: { fontSize: 16, letterSpacing: 2 },
  factor: { fontSize: 12 },
  planBtn: { alignSelf: 'flex-start', borderColor: 'rgba(240,185,11,0.5)', backgroundColor: 'rgba(240,185,11,0.1)', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  planBtnText: { color: colors.accent, fontWeight: '700', fontSize: 13 },
  disclaimer: { color: colors.textMuted, fontSize: 11, lineHeight: 16, textAlign: 'center' },
})
