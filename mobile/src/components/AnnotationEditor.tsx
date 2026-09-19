import * as Haptics from 'expo-haptics'
import { useEffect } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { ChartLinkPreview } from './ChartLinkPreview'
import { invalidateTagRecord, TagRecord } from './TagRecord'
import { useAutosave, type AnnotationFields, type SaveStatus } from '../journal/useAutosave'
import { colors, radius, spacing } from '../theme'
import type { JournalUpdateRequest } from '../types/journal'

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
        <ActivityIndicator size="small" color={colors.accent} />
        <Text style={styles.statusText}>Saving…</Text>
      </View>
    )
  }
  if (status === 'saved') {
    return (
      <View style={styles.statusRow}>
        <Text style={[styles.statusText, { color: colors.positive }]}>✓ Saved</Text>
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
      <Text style={styles.statusText}>Changes save automatically</Text>
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
          <Text style={[styles.star, n <= value ? styles.starOn : styles.starOff]}>{n <= value ? '★' : '☆'}</Text>
        </Pressable>
      ))}
    </View>
  )
}

/**
 * Notes / setup tag / chart link / star rating with autosave — the same fields
 * and behaviour as the web Journal, for both closed and still-open trades.
 */
export function AnnotationEditor({ initial, save, tagSuggestions, notesLabel = 'Notes' }: Props) {
  const { fields, update, status, error, retry } = useAutosave(initial, async (patch) => {
    await save(patch)
    if ('setup_tag' in patch) invalidateTagRecord() // the record line should reflect the new tag next time
  })
  useEffect(() => {
    if (status === 'saved') void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {})
  }, [status])
  const url = fields.chart_snapshot_url.trim()
  const remaining = tagSuggestions.filter((t) => t !== fields.setup_tag.trim()).slice(0, 8)

  return (
    <View style={styles.wrap}>
      <StatusLine status={status} error={error} onRetry={() => void retry()} />

      <Text style={styles.label}>Rating</Text>
      <StarRating value={fields.rating} onChange={(rating) => update({ rating })} />

      <Text style={styles.label}>Setup tag</Text>
      <TextInput
        style={styles.input}
        value={fields.setup_tag}
        onChangeText={(setup_tag) => update({ setup_tag })}
        placeholder="e.g. London sweep, breakout retest"
        placeholderTextColor={colors.textMuted}
        maxLength={120}
        autoCorrect={false}
      />
      <TagRecord tag={fields.setup_tag} />
      {remaining.length > 0 ? (
        <View style={styles.suggestions}>
          {remaining.map((t) => (
            <Pressable key={t} onPress={() => update({ setup_tag: t })} accessibilityRole="button" style={styles.suggestion}>
              <Text style={styles.suggestionText}>{t}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      <Text style={styles.label}>{notesLabel}</Text>
      <TextInput
        style={[styles.input, styles.notes]}
        value={fields.notes}
        onChangeText={(notes) => update({ notes })}
        placeholder="What was the plan? What happened? What would you change?"
        placeholderTextColor={colors.textMuted}
        multiline
        textAlignVertical="top"
        maxLength={20_000}
        scrollEnabled={false}
      />

      <Text style={styles.label}>Chart link</Text>
      <TextInput
        style={styles.input}
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
  )
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 20 },
  statusText: { color: colors.textMuted, fontSize: 12 },
  label: { color: colors.textMuted, fontSize: 12, marginTop: spacing.sm },
  input: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    color: colors.textPrimary,
    fontSize: 15,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  notes: { minHeight: 140, lineHeight: 21 },
  stars: { flexDirection: 'row', gap: spacing.xs },
  starBtn: { padding: spacing.xs },
  star: { fontSize: 30 },
  starOn: { color: colors.warning },
  starOff: { color: colors.textMuted },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  suggestion: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
  },
  suggestionText: { color: colors.textSecondary, fontSize: 12 },
})
