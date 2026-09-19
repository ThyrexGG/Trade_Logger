import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import * as Haptics from 'expo-haptics'
import { useLayoutEffect, useState } from 'react'
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { createEntry, deleteEntry, updateEntry } from '../api/entries'
import { ScreenshotGallery } from '../components/ScreenshotGallery'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { EntryKind, JournalEntry } from '../types/entries'
import { KIND_COLOR, KIND_LABEL } from './EntriesScreen'

const KINDS: EntryKind[] = ['idea', 'review', 'observation', 'plan']

const parseTags = (raw: string): string[] =>
  raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)

/** Create or edit a free-standing note (idea / review / observation / trade plan). Explicit Save, like the website. */
export function EntryScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'Entry'>>()
  const { params } = useRoute<RouteProp<RootStackParamList, 'Entry'>>()
  const existing = params.entry

  const [kind, setKind] = useState<EntryKind>(existing?.kind ?? 'idea')
  const [instrument, setInstrument] = useState(existing?.instrument ?? '')
  const [title, setTitle] = useState(existing?.title ?? '')
  const [body, setBody] = useState(existing?.body ?? '')
  const [tags, setTags] = useState((existing?.tags ?? []).join(', '))
  const [baseline, setBaseline] = useState<JournalEntry | undefined>(existing)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState(false)

  useLayoutEffect(() => {
    navigation.setOptions({ title: existing ? 'Note' : 'New note' })
  }, [navigation, existing])

  const dirty = baseline
    ? kind !== baseline.kind ||
      instrument.trim() !== (baseline.instrument ?? '') ||
      title.trim() !== (baseline.title ?? '') ||
      body !== baseline.body ||
      parseTags(tags).join('|') !== baseline.tags.join('|')
    : title.trim() !== '' || body.trim() !== '' || instrument.trim() !== '' || parseTags(tags).length > 0

  async function save() {
    if (busy || !dirty) return
    setBusy(true)
    setError(null)
    setSavedAt(false)
    const payload = {
      kind,
      instrument: instrument.trim() || null,
      title: title.trim() || null,
      body,
      tags: parseTags(tags),
    }
    try {
      if (baseline) {
        const updated = await updateEntry(baseline.id, payload)
        setBaseline(updated)
        setSavedAt(true)
        void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {})
      } else {
        const created = await createEntry(payload)
        // Reopen as an existing note so screenshots can be attached right away.
        navigation.replace('Entry', { entry: created })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed.')
    } finally {
      setBusy(false)
    }
  }

  function confirmDelete() {
    if (!baseline) return
    Alert.alert('Delete this note?', 'This also removes its screenshots, everywhere including the website.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          setBusy(true)
          deleteEntry(baseline.id)
            .then(() => navigation.goBack())
            .catch((err: unknown) => {
              setError(err instanceof Error ? err.message : 'Delete failed.')
              setBusy(false)
            })
        },
      },
    ])
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.kinds}>
            {KINDS.map((k) => {
              const active = kind === k
              return (
                <Pressable
                  key={k}
                  onPress={() => setKind(k)}
                  accessibilityRole="button"
                  style={[styles.kindChip, active && { borderColor: KIND_COLOR[k], backgroundColor: 'rgba(255,255,255,0.06)' }]}
                >
                  <Text style={[styles.kindText, active && { color: KIND_COLOR[k], fontWeight: '700' }]}>{KIND_LABEL[k]}</Text>
                </Pressable>
              )
            })}
          </View>

          <Text style={styles.label}>Instrument</Text>
          <TextInput
            style={styles.input}
            value={instrument}
            onChangeText={setInstrument}
            placeholder="e.g. US500, XAUUSD (optional)"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={60}
          />

          <Text style={styles.label}>Title</Text>
          <TextInput
            style={styles.input}
            value={title}
            onChangeText={setTitle}
            placeholder="A short headline (optional)"
            placeholderTextColor={colors.textMuted}
            maxLength={200}
          />

          <Text style={styles.label}>Note</Text>
          <TextInput
            style={[styles.input, styles.body]}
            value={body}
            onChangeText={setBody}
            placeholder="What are you seeing? What's the plan? What did you learn?"
            placeholderTextColor={colors.textMuted}
            multiline
            textAlignVertical="top"
            scrollEnabled={false}
          />

          <Text style={styles.label}>Tags (comma separated)</Text>
          <TextInput
            style={styles.input}
            value={tags}
            onChangeText={setTags}
            placeholder="e.g. weekly, london, risk"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoCorrect={false}
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <View style={styles.actions}>
            <Pressable
              onPress={() => void save()}
              disabled={busy || !dirty}
              accessibilityRole="button"
              style={({ pressed }) => [styles.saveBtn, (busy || !dirty) && styles.disabled, pressed && { opacity: 0.8 }]}
            >
              {busy ? <ActivityIndicator color={colors.background} /> : <Text style={styles.saveText}>{baseline ? 'Save changes' : 'Save note'}</Text>}
            </Pressable>
            {savedAt && !dirty ? <Text style={styles.saved}>✓ Saved</Text> : null}
          </View>

          {baseline ? (
            <View style={styles.card}>
              <ScreenshotGallery ownerId={baseline.id} />
            </View>
          ) : (
            <Text style={styles.hint}>Save the note first, then you can attach screenshots.</Text>
          )}

          {baseline ? (
            <Pressable onPress={confirmDelete} disabled={busy} accessibilityRole="button" style={styles.deleteBtn}>
              <Text style={styles.deleteText}>Delete note</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { padding: spacing.lg, gap: spacing.sm, paddingBottom: spacing.xl * 2 },
  kinds: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  kindChip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.md + 2, paddingVertical: spacing.sm },
  kindText: { color: colors.textSecondary, fontSize: 13 },
  label: { color: colors.textMuted, fontSize: 12, marginTop: spacing.sm },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    color: colors.textPrimary,
    fontSize: 15,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  body: { minHeight: 160, lineHeight: 21 },
  error: { color: colors.negative, fontSize: 13, marginTop: spacing.sm },
  actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.md },
  saveBtn: { backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: spacing.xl, paddingVertical: spacing.md, minWidth: 140, alignItems: 'center' },
  disabled: { opacity: 0.4 },
  saveText: { color: colors.background, fontSize: 15, fontWeight: '700' },
  saved: { color: colors.positive, fontSize: 13 },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginTop: spacing.md,
  },
  hint: { color: colors.textMuted, fontSize: 12, marginTop: spacing.md },
  deleteBtn: { alignItems: 'center', paddingVertical: spacing.md, marginTop: spacing.lg },
  deleteText: { color: colors.negative, fontSize: 14, fontWeight: '600' },
})
