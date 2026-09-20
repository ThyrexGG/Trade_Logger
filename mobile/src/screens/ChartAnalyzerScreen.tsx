import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { Image } from 'expo-image'
import { useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { analyzeChartImage, analyzeChartLink } from '../api/chartAnalysis'
import { Button, Card, Pill } from '../components/ui'
import { formatPrice } from '../format'
import { PickError, pickScreenshot, type PickSource } from '../journal/pickImage'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { ChartAnalysisResponse } from '../types/chartAnalysis'

const TV_LINK = /^https:\/\/(www\.)?tradingview\.com\/x\/[A-Za-z0-9]+\/?(\?.*)?$/i

function ratingColor(n: number | null): string {
  if (n == null) return colors.textMuted
  return n >= 7 ? colors.positive : n >= 4 ? colors.warning : colors.negative
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.fact}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={[styles.factValue, color ? { color } : null]}>{value}</Text>
    </View>
  )
}

/** The note "Save as note" pre-fills: what the analysis read, laid out as text. */
function noteFor(r: ChartAnalysisResponse) {
  const lines: (string | null)[] = [
    `${(r.direction ?? 'setup').toUpperCase()} ${r.symbol ?? ''}${r.timeframe ? ` (${r.timeframe})` : ''}`.trim(),
    r.entry != null ? `Entry ${formatPrice(r.entry)}` : null,
    r.stop_loss != null ? `Stop ${formatPrice(r.stop_loss)}` : null,
    r.take_profit != null ? `Target ${formatPrice(r.take_profit)}${r.additional_targets.length ? ` (then ${r.additional_targets.map(formatPrice).join(', ')})` : ''}` : null,
    r.risk_reward != null ? `R:R ${r.risk_reward}` : null,
    r.setup_rating != null ? `AI setup rating ${r.setup_rating}/10 — ${r.rating_reasoning ?? ''}` : null,
    r.pattern ? `Pattern: ${r.pattern}` : null,
    r.confluences.length ? `Confluence: ${r.confluences.join('; ')}` : null,
    r.caveats ? `Unclear: ${r.caveats}` : null,
    '',
    'Why I would / would not take it:',
  ]
  return {
    kind: 'idea' as const,
    instrument: r.symbol,
    title: `${r.symbol ?? 'Chart'} ${r.direction ?? ''} chart read`.replace(/\s+/g, ' ').trim(),
    body: lines.filter((l): l is string => l !== null).join('\n'),
    tags: ['chart-analyzer'],
  }
}

/** Chart analyzer: a vision model reads one chart screenshot (or TradingView share link) and pulls out the trade plan drawn on it. */
export function ChartAnalyzerScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ChartAnalysisResponse | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function run(fn: (signal: AbortSignal) => Promise<ChartAnalysisResponse>, localPreview: string | null) {
    controller.current?.abort()
    const c = new AbortController()
    controller.current = c
    setBusy(true)
    setError(null)
    setResult(null)
    setPreview(localPreview)
    try {
      const res = await fn(c.signal)
      if (c.signal.aborted) return
      if (!res.ok) {
        setError(res.error ?? 'The analysis failed.')
        return
      }
      setResult(res)
      if (!localPreview && res.image_base64) setPreview(`data:${res.image_mime ?? 'image/png'};base64,${res.image_base64}`)
    } catch (err) {
      if (!c.signal.aborted) setError(err instanceof Error ? err.message : 'The analysis failed.')
    } finally {
      if (!c.signal.aborted) setBusy(false)
    }
  }

  async function pick(source: PickSource) {
    let uri: string | null
    try {
      uri = await pickScreenshot(source)
    } catch (err) {
      setError(err instanceof PickError || err instanceof Error ? err.message : 'Could not open the picker.')
      return
    }
    if (!uri) return
    void run((signal) => analyzeChartImage(uri as string, signal), uri)
  }

  function chooseSource() {
    Alert.alert('Chart screenshot', undefined, [
      { text: 'Take photo', onPress: () => void pick('camera') },
      { text: 'Choose from library', onPress: () => void pick('library') },
      { text: 'Cancel', style: 'cancel' },
    ])
  }

  function analyzeLink() {
    const url = link.trim()
    if (!TV_LINK.test(url)) return setError('Paste a TradingView share link that looks like https://www.tradingview.com/x/AbCdEfGh/')
    void run((signal) => analyzeChartLink(url, signal), null)
  }

  const r = result
  const dirColor = r?.direction === 'long' ? colors.positive : r?.direction === 'short' ? colors.negative : colors.textSecondary

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.intro}>
            Give it a chart screenshot with your entry, stop and target drawn on it. An AI reads what is visible and returns the levels, the reward-to-risk and an opinion on the setup. It only sees that one image, so it can be wrong — it is a second look, not a signal.
          </Text>

          <Card title="Analyze a chart">
            <Button label="Choose or take a screenshot" busy={busy} onPress={chooseSource} />
            <Text style={styles.or}>or paste a TradingView share link</Text>
            <TextInput
              value={link}
              onChangeText={setLink}
              placeholder="https://www.tradingview.com/x/…"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              style={styles.input}
              onSubmitEditing={analyzeLink}
            />
            <Button label="Analyze link" kind="secondary" disabled={busy || !link.trim()} onPress={analyzeLink} />
          </Card>

          {busy ? (
            <Card>
              <ActivityIndicator color={colors.accent} />
              <Text style={styles.centerMuted}>Reading the chart… this usually takes 10–30 seconds.</Text>
            </Card>
          ) : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}

          {r ? (
            <>
              {preview ? <Image source={{ uri: preview }} style={styles.preview} contentFit="contain" accessibilityLabel="The analysed chart" /> : null}

              <Card title="What it read">
                <View style={styles.pills}>
                  {r.symbol ? <Pill text={r.symbol} color={colors.accent} /> : null}
                  {r.timeframe ? <Pill text={r.timeframe} color={colors.textSecondary} /> : null}
                  {r.direction ? <Pill text={r.direction.toUpperCase()} color={dirColor} /> : null}
                  {r.extraction_confidence ? <Pill text={`${r.extraction_confidence} confidence`} color={colors.textSecondary} /> : null}
                </View>
                <Row label="Entry" value={r.entry != null ? formatPrice(r.entry) : 'not visible'} />
                <Row label="Stop" value={r.stop_loss != null ? formatPrice(r.stop_loss) : 'not visible'} color={r.stop_loss != null ? colors.negative : undefined} />
                <Row label="Target" value={r.take_profit != null ? formatPrice(r.take_profit) : 'not visible'} color={r.take_profit != null ? colors.positive : undefined} />
                {r.additional_targets.length > 0 ? <Row label="More targets" value={r.additional_targets.map(formatPrice).join(' · ')} /> : null}
                <Row label="Reward : risk" value={r.risk_reward != null ? `${r.risk_reward}` : '—'} />
              </Card>

              <Card title="Setup rating">
                <Text style={[styles.rating, { color: ratingColor(r.setup_rating) }]}>{r.setup_rating != null ? `${r.setup_rating} / 10` : 'no rating'}</Text>
                {r.rating_reasoning ? <Text style={styles.body}>{r.rating_reasoning}</Text> : null}
                {r.pattern ? <Text style={styles.body}>Pattern: {r.pattern}</Text> : null}
                {r.confluences.map((c) => (
                  <Text key={c} style={styles.bullet}>
                    ✓ {c}
                  </Text>
                ))}
                {r.caveats ? <Text style={styles.caveat}>Unclear: {r.caveats}</Text> : null}
              </Card>

              <View style={styles.actions}>
                <View style={{ flex: 1 }}>
                  <Button
                    label="Size this trade"
                    disabled={r.entry == null || r.stop_loss == null}
                    onPress={() =>
                      navigation.navigate('RiskGateway', {
                        prefill: {
                          symbol: r.symbol ?? undefined,
                          side: r.direction === 'short' ? 'SELL' : 'BUY',
                          entry: r.entry ?? undefined,
                          stop: r.stop_loss ?? undefined,
                          tp1: r.take_profit ?? undefined,
                          tp2: r.additional_targets[0],
                        },
                      })
                    }
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Button label="Save as note" kind="secondary" onPress={() => navigation.navigate('Entry', { prefill: noteFor(r) })} />
                </View>
              </View>
              <Text style={styles.disclaimer}>{r.disclaimer}</Text>
            </>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xl * 2 },
  intro: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  or: { color: colors.textMuted, fontSize: 12, textAlign: 'center' },
  input: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    color: colors.textPrimary,
    fontSize: 14,
  },
  centerMuted: { color: colors.textMuted, fontSize: 12, textAlign: 'center' },
  error: { color: colors.negative, fontSize: 13 },
  preview: { width: '100%', aspectRatio: 1.6, backgroundColor: colors.surface, borderRadius: radius.md },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  fact: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomColor: colors.borderSubtle, borderBottomWidth: 1 },
  factLabel: { color: colors.textMuted, fontSize: 13 },
  factValue: { color: colors.textPrimary, fontSize: 14, fontVariant: ['tabular-nums'], flexShrink: 1, textAlign: 'right' },
  rating: { fontSize: 32, fontWeight: '700' },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  bullet: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  caveat: { color: colors.warning, fontSize: 12, lineHeight: 17 },
  actions: { flexDirection: 'row', gap: spacing.sm },
  disclaimer: { color: colors.textMuted, fontSize: 11, lineHeight: 16, textAlign: 'center' },
})
