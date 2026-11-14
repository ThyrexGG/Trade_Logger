import { Ionicons } from '@expo/vector-icons'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { Image } from 'expo-image'
import { useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { analyzeChartImage, analyzeChartLink } from '../api/chartAnalysis'
import { Text, TextInput } from '../components/Text'
import { Button, Card, Fact, Footnote, Notice, Pill, Rows, ui } from '../components/ui'
import { formatPrice } from '../format'
import { PickError, pickScreenshot, type PickSource } from '../journal/pickImage'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing, type } from '../theme'
import type { ChartAnalysisResponse } from '../types/chartAnalysis'

const TV_LINK = /^https:\/\/(www\.)?tradingview\.com\/x\/[A-Za-z0-9]+\/?(\?.*)?$/i

function ratingColor(n: number | null): string {
  if (n == null) return colors.textMuted
  return n >= 7 ? colors.positive : n >= 4 ? colors.warning : colors.negative
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
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={ui.content} keyboardShouldPersistTaps="handled">
          <Text style={ui.muted}>
            Give it a chart screenshot with your entry, stop and target drawn on it. An AI reads what is visible and returns the levels, the reward compared with the risk, and an opinion. It only sees that one image, so it can be wrong. Treat it as a second look, not a signal.
          </Text>

          <Card title="Analyze a chart">
            <Button label="Choose or take a screenshot" icon="image-outline" busy={busy} onPress={chooseSource} />
            <Text style={styles.or}>or paste a TradingView share link</Text>
            <TextInput
              value={link}
              onChangeText={setLink}
              placeholder="https://www.tradingview.com/x/…"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              style={ui.input}
              onSubmitEditing={analyzeLink}
            />
            <Button label="Analyze link" kind="secondary" disabled={busy || !link.trim()} onPress={analyzeLink} />
          </Card>

          {busy ? (
            <Card>
              <ActivityIndicator color={colors.accent} />
              <Text style={styles.or}>Reading the chart. This usually takes 10 to 30 seconds.</Text>
            </Card>
          ) : null}
          {error ? <Notice>{error}</Notice> : null}

          {r ? (
            <>
              {preview ? <Image source={{ uri: preview }} style={styles.preview} contentFit="contain" accessibilityLabel="The analysed chart" /> : null}

              <Card title="What it read" flush>
                <View style={styles.pills}>
                  {r.symbol ? <Pill text={r.symbol} color={colors.textPrimary} /> : null}
                  {r.timeframe ? <Pill text={r.timeframe} color={colors.textSecondary} /> : null}
                  {r.direction ? <Pill text={r.direction.toUpperCase()} color={dirColor} /> : null}
                  {r.extraction_confidence ? <Pill text={`${r.extraction_confidence} confidence`} color={colors.textSecondary} /> : null}
                </View>
                <Rows inset={0}>
                  <Fact label="Entry" value={r.entry != null ? formatPrice(r.entry) : 'not visible'} />
                  <Fact label="Stop" value={r.stop_loss != null ? formatPrice(r.stop_loss) : 'not visible'} />
                  <Fact label="Target" value={r.take_profit != null ? formatPrice(r.take_profit) : 'not visible'} />
                  {r.additional_targets.length > 0 ? <Fact label="More targets" value={r.additional_targets.map(formatPrice).join(' · ')} /> : null}
                  <Fact label="Reward for each 1 risked" value={r.risk_reward != null ? `${r.risk_reward}` : '—'} />
                </Rows>
              </Card>

              <Card title="Setup rating">
                <Text style={[styles.rating, { color: ratingColor(r.setup_rating) }]}>{r.setup_rating != null ? `${r.setup_rating} / 10` : 'no rating'}</Text>
                {r.rating_reasoning ? <Text style={ui.body}>{r.rating_reasoning}</Text> : null}
                {r.pattern ? <Text style={ui.sub}>Pattern: {r.pattern}</Text> : null}
                {r.confluences.map((c) => (
                  <View key={c} style={styles.bullet}>
                    <Ionicons name="checkmark" size={14} color={colors.textSecondary} style={styles.bulletIcon} />
                    <Text style={[ui.sub, ui.flex]}>{c}</Text>
                  </View>
                ))}
                {r.caveats ? <Notice tone="warn">Unclear: {r.caveats}</Notice> : null}
              </Card>

              <View style={styles.actions}>
                <Button
                  label="Size this trade"
                  disabled={r.entry == null || r.stop_loss == null}
                  style={ui.flex}
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
                <Button label="Save as note" kind="secondary" style={ui.flex} onPress={() => navigation.navigate('Entry', { prefill: noteFor(r) })} />
              </View>
              <Footnote>{r.disclaimer}</Footnote>
            </>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  or: { ...type.small, textAlign: 'center' },
  preview: { width: '100%', aspectRatio: 1.6, backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.borderSubtle },
  rating: { ...type.hero, fontSize: 30, lineHeight: 36 },
  bullet: { flexDirection: 'row', gap: spacing.sm },
  bulletIcon: { marginTop: 2 },
  actions: { flexDirection: 'row', gap: spacing.sm },
})
