import { Ionicons } from '@expo/vector-icons'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import * as Haptics from 'expo-haptics'
import { useLayoutEffect, useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { createEntry, deleteEntry, updateEntry } from '../api/entries'
import { ScreenshotGallery } from '../components/ScreenshotGallery'
import { Text } from '../components/Text'
import { Button, Card, Chip, ChipRow, Field, Notice, ui } from '../components/ui'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, spacing, type } from '../theme'
import type { EntryKind, JournalEntry } from '../types/entries'
import { KIND_LABEL } from './EntriesScreen'

const KINDS: EntryKind[] = ['idea', 'review', 'observation', 'plan', 'skipped']

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
  const pre = existing ? undefined : params.prefill // e.g. "Plan this" from the Killzone scanner

  const [kind, setKind] = useState<EntryKind>(existing?.kind ?? pre?.kind ?? 'idea')
  const [instrument, setInstrument] = useState(existing?.instrument ?? pre?.instrument ?? '')
  const [title, setTitle] = useState(existing?.title ?? pre?.title ?? '')
  const [body, setBody] = useState(existing?.body ?? pre?.body ?? '')
  const [tags, setTags] = useState((existing?.tags ?? pre?.tags ?? []).join(', '))
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
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={ui.content} keyboardShouldPersistTaps="handled">
          <ChipRow wrap>
            {KINDS.map((k) => (
              <Chip key={k} label={KIND_LABEL[k]} on={kind === k} onPress={() => setKind(k)} />
            ))}
          </ChipRow>

          <Card>
            <Field label="Market" value={instrument} onChangeText={setInstrument} placeholder="e.g. US500, XAUUSD (optional)" autoCapitalize="characters" maxLength={60} />
            <Field label="Title" value={title} onChangeText={setTitle} placeholder="A short headline (optional)" autoCapitalize="sentences" maxLength={200} />
            <Field label="Note" value={body} onChangeText={setBody} placeholder="What are you seeing? What's the plan? What did you learn?" autoCapitalize="sentences" multiline />
            <Field label="Tags, separated by commas" value={tags} onChangeText={setTags} placeholder="e.g. weekly, london, risk" />
          </Card>

          {error ? <Notice>{error}</Notice> : null}

          <View style={styles.actions}>
            <Button label={baseline ? 'Save changes' : 'Save note'} busy={busy} disabled={!dirty} onPress={() => void save()} style={ui.flex} />
            {savedAt && !dirty ? (
              <View style={styles.saved}>
                <Ionicons name="checkmark" size={14} color={colors.positive} />
                <Text style={styles.savedText}>Saved</Text>
              </View>
            ) : null}
          </View>

          {baseline ? (
            <Card>
              <ScreenshotGallery ownerId={baseline.id} />
            </Card>
          ) : (
            <Text style={ui.muted}>Save the note first, then you can attach screenshots.</Text>
          )}

          {baseline ? <Button label="Delete note" kind="danger" icon="trash-outline" disabled={busy} onPress={confirmDelete} style={styles.delete} /> : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  saved: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  savedText: { ...type.small, color: colors.positive },
  delete: { marginTop: spacing.sm },
})
