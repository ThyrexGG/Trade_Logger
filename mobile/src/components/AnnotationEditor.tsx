import { Ionicons } from '@expo/vector-icons'
import * as Haptics from 'expo-haptics'
import { useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native'
import { ChartLinkPreview } from './ChartLinkPreview'
import { invalidateTagRecord, TagRecord } from './TagRecord'
import { Text, TextInput } from './Text'
import { ui } from './ui'
import { useAutosave, type AnnotationFields, type SaveStatus } from '../journal/useAutosave'
import { colors, radius, spacing, type } from '../theme'
import type { JournalUpdateRequest } from '../types/journal'

/** The ONE tap per trade (same three answers as the web Journal; stored as the setup tag so the tag record works with no backend change). */
const QUICK_TAGS = [
  { value: 'By my rules', label: 'By my rules' },
  { value: 'Bent my rules', label: 'Bent my rules' },
  { value: 'Rushed', label: 'Rushed / off-plan' },
] as const

interface Props {
  initial: AnnotationFields
  save: (patch: JournalUpdateRequest) => Promise<void>
  /** previously used setup tags, most-used first — shown as one-tap chips */
  tagSuggestions: string[]
  notesLabel?: string
}

function StatusLine({ status, error, onRetry }: { status: SaveStatus; error: string | null; onRetry: () => void }) {
  if (status === 'saving') {
    return (
      <View style={styles.statusRow}>
        <ActivityIndicator size="small" color={colors.textMuted} />
        <Text style={styles.statusText}>Saving…</Text>
      </View>
    )
  }
  if (status === 'saved') {
    return (
      <View style={styles.statusRow}>
        <Ionicons name="checkmark" size={13} color={colors.positive} />
        <Text style={[styles.statusText, { color: colors.positive }]}>Saved</Text>
      </View>
    )
  }
  if (status === 'error') {
    return (
      <Pressable onPress={onRetry} accessibilityRole="button" style={styles.statusRow}>
        <Text style={[styles.statusText, { color: colors.negative }]}>{error ?? 'Save failed.'} Tap to retry.</Text>
      </Pressable>
    )
  }
  return (
    <View style={styles.statusRow}>
      <Text style={styles.statusText}>Saves on its own</Text>
    </View>
  )
}

function StarRating({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <View style={styles.stars}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Pressable
          key={n}
          // Tapping the current rating again clears it.
          onPress={() => onChange(value === n ? 0 : n)}
          hitSlop={4}
          accessibilityRole="button"
          accessibilityLabel={`${n} star${n > 1 ? 's' : ''}`}
          style={styles.starBtn}
        >
          <Ionicons name={n <= value ? 'star' : 'star-outline'} size={26} color={n <= value ? colors.warning : colors.textMuted} />
        </Pressable>
      ))}
    </View>
  )
}

/**
 * One-tap trade label, optional note, and the rest behind More details, with autosave — the same fields
 * and behaviour as the web Journal, for both closed and still-open trades.
 */
export function AnnotationEditor({ initial, save, tagSuggestions, notesLabel = 'Note' }: Props) {
  const { fields, update, status, error, retry } = useAutosave(initial, async (patch) => {
    await save(patch)
    if ('setup_tag' in patch) invalidateTagRecord() // the record line should reflect the new tag next time
  })
  useEffect(() => {
    if (status === 'saved') void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {})
  }, [status])
  const url = fields.chart_snapshot_url.trim()
  const tag = fields.setup_tag.trim()
  const isQuick = QUICK_TAGS.some((t) => t.value === tag)
  const remaining = tagSuggestions.filter((t) => t !== tag && !QUICK_TAGS.some((q) => q.value === t)).slice(0, 8)
  // the extra section starts open only when something in it is already filled in
  const [moreOpen, setMoreOpen] = useState(Boolean(url) || (tag.length > 0 && !isQuick) || fields.rating > 0)

  return (
    <View style={styles.wrap}>
      <View style={ui.rowBetween}>
        <Text style={styles.question}>How was this trade?</Text>
        <StatusLine status={status} error={error} onRetry={() => void retry()} />
      </View>
      <View style={styles.quickRow}>
        {QUICK_TAGS.map((t) => {
          const on = tag === t.value
          return (
            <Pressable
              key={t.value}
              onPress={() => update({ setup_tag: on ? '' : t.value })}
              accessibilityRole="button"
              accessibilityState={{ selected: on }}
              style={[styles.quickBtn, on && styles.quickBtnOn]}
            >
              <Text style={[styles.quickText, on && styles.quickTextOn]} numberOfLines={2}>
                {t.label}
              </Text>
            </Pressable>
          )
        })}
      </View>
      <TagRecord tag={fields.setup_tag} />

      <Text style={styles.label}>{notesLabel} (optional)</Text>
      <TextInput
        style={[ui.input, ui.inputMultiline]}
        value={fields.notes}
        onChangeText={(notes) => update({ notes })}
        placeholder="One line on what you saw and why you took it"
        placeholderTextColor={colors.textMuted}
        multiline
        textAlignVertical="top"
        maxLength={20_000}
        scrollEnabled={false}
      />

      <Pressable onPress={() => setMoreOpen((o) => !o)} accessibilityRole="button" accessibilityState={{ expanded: moreOpen }} style={styles.moreBtn}>
        <Text style={styles.moreText}>More details</Text>
        {!moreOpen ? <Text style={styles.moreHint}>stars, your own tag, chart link</Text> : <View style={ui.flex} />}
        <Ionicons name={moreOpen ? 'chevron-up' : 'chevron-down'} size={15} color={colors.textMuted} />
      </Pressable>

      {moreOpen ? (
        <View style={styles.wrap}>
          <Text style={styles.label}>Rating</Text>
          <StarRating value={fields.rating} onChange={(rating) => update({ rating })} />

          <Text style={styles.label}>Your own tag</Text>
          <TextInput
            style={ui.input}
            value={isQuick ? '' : fields.setup_tag}
            onChangeText={(setup_tag) => update({ setup_tag })}
            placeholder="optional, e.g. London sweep"
            placeholderTextColor={colors.textMuted}
            maxLength={120}
            autoCorrect={false}
          />
          {remaining.length > 0 ? (
            <View style={styles.suggestions}>
              {remaining.map((t) => (
                <Pressable key={t} onPress={() => update({ setup_tag: t })} accessibilityRole="button" style={styles.suggestion}>
                  <Text style={styles.suggestionText}>{t}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}

          <Text style={styles.label}>Chart link</Text>
          <TextInput
            style={ui.input}
            value={fields.chart_snapshot_url}
            onChangeText={(chart_snapshot_url) => update({ chart_snapshot_url })}
            placeholder="https://www.tradingview.com/x/…"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <ChartLinkPreview url={url} />
        </View>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  question: { ...type.heading, flexShrink: 1 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 5, minHeight: 20, flexShrink: 1 },
  statusText: { ...type.small, fontSize: 11 },
  label: { ...type.small, color: colors.textSecondary, marginTop: spacing.sm },
  quickRow: { flexDirection: 'row', gap: spacing.sm },
  quickBtn: {
    flex: 1,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  quickBtnOn: { borderColor: colors.accentLine, backgroundColor: colors.accentSoft },
  quickText: { color: colors.textSecondary, fontSize: 13, lineHeight: 17, fontWeight: '500', textAlign: 'center' },
  quickTextOn: { color: colors.accent, fontWeight: '600' },
  moreBtn: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.sm, paddingTop: spacing.md, minHeight: 40, borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  moreText: { ...type.sub, fontWeight: '500' },
  moreHint: { ...type.small, flex: 1, textAlign: 'right' },
  stars: { flexDirection: 'row', gap: spacing.xs },
  starBtn: { padding: spacing.xs },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  suggestion: { backgroundColor: colors.surfaceElevated, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: spacing.xs + 2 },
  suggestionText: { color: colors.textSecondary, fontSize: 12 },
})
