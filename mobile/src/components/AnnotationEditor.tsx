import * as Haptics from 'expo-haptics'
import { useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { ChartLinkPreview } from './ChartLinkPreview'
import { invalidateTagRecord, TagRecord } from './TagRecord'
import { useAutosave, type AnnotationFields, type SaveStatus } from '../journal/useAutosave'
import { colors, radius, spacing } from '../theme'
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
 * One-tap trade label, optional note, and the rest behind More details, with autosave — the same fields
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
  const tag = fields.setup_tag.trim()
  const isQuick = QUICK_TAGS.some((t) => t.value === tag)
  const remaining = tagSuggestions.filter((t) => t !== tag && !QUICK_TAGS.some((q) => q.value === t)).slice(0, 8)
  // the extra section starts open only when something in it is already filled in
  const [moreOpen, setMoreOpen] = useState(Boolean(url) || (tag.length > 0 && !isQuick) || fields.rating > 0)

  return (
    <View style={styles.wrap}>
      <StatusLine status={status} error={error} onRetry={() => void retry()} />

      <Text style={styles.label}>How was this trade? One tap is enough.</Text>
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
              <Text style={[styles.quickText, on && styles.quickTextOn]}>{t.label}</Text>
            </Pressable>
          )
        })}
      </View>
      <TagRecord tag={fields.setup_tag} />

      <Text style={styles.label}>{notesLabel} (optional)</Text>
      <TextInput
        style={[styles.input, styles.notes]}
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
        <Text style={styles.moreText}>{moreOpen ? '▾' : '›'} More details</Text>
        <Text style={styles.moreHint}>stars, your own tag, chart link</Text>
      </Pressable>

      {moreOpen ? (
        <View style={styles.wrap}>
          <Text style={styles.label}>Rating</Text>
          <StarRating value={fields.rating} onChange={(rating) => update({ rating })} />

          <Text style={styles.label}>Your own tag</Text>
          <TextInput
            style={styles.input}
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
      ) : null}
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
  notes: { minHeight: 80, lineHeight: 21 },
  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  quickBtn: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  quickBtnOn: { borderColor: colors.accent, backgroundColor: colors.background },
  quickText: { color: colors.textSecondary, fontSize: 14 },
  quickTextOn: { color: colors.accent, fontWeight: '700' },
  moreBtn: { marginTop: spacing.sm, paddingVertical: spacing.sm },
  moreText: { color: colors.textPrimary, fontSize: 14, fontWeight: '600' },
  moreHint: { color: colors.textMuted, fontSize: 12 },
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
