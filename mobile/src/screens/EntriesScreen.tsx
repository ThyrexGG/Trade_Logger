import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useRef, useState } from 'react'
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { listEntries } from '../api/entries'
import { Text } from '../components/Text'
import { Button, Empty, Loading, Notice, Tag, ui } from '../components/ui'
import { formatUpdated } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing, type } from '../theme'
import type { EntryKind, JournalEntry } from '../types/entries'

export const KIND_LABEL: Record<EntryKind, string> = {
  idea: 'Idea',
  review: 'Review',
  observation: 'Observation',
  plan: 'Trade plan',
  skipped: 'Skipped setup',
}
/** One icon per kind: the shape tells the kinds apart, so colour doesn't have to. */
export const KIND_ICON: Record<EntryKind, keyof typeof Ionicons.glyphMap> = {
  idea: 'bulb-outline',
  review: 'refresh-circle-outline',
  observation: 'eye-outline',
  plan: 'map-outline',
  skipped: 'play-skip-forward-outline',
}

function EntryCard({ entry, onPress }: { entry: JournalEntry; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.card, pressed && { backgroundColor: colors.surfaceHover }]}>
      <View style={styles.cardTop}>
        <Ionicons name={KIND_ICON[entry.kind] ?? 'document-text-outline'} size={14} color={colors.textSecondary} />
        <Text style={styles.kind}>{KIND_LABEL[entry.kind] ?? entry.kind}</Text>
        {entry.instrument ? <Text style={styles.instrument}>{entry.instrument}</Text> : null}
        <Text style={styles.date}>{formatUpdated(entry.updated_at || entry.created_at)}</Text>
      </View>
      {entry.title ? <Text style={ui.heading}>{entry.title}</Text> : null}
      {entry.body ? (
        <Text style={ui.sub} numberOfLines={3}>
          {entry.body}
        </Text>
      ) : null}
      {entry.tags.length > 0 || entry.screenshot_count > 0 ? (
        <View style={ui.rowWrap}>
          {entry.tags.map((t) => (
            <Tag key={t} text={t} />
          ))}
          {entry.screenshot_count > 0 ? (
            <View style={styles.shots}>
              <Ionicons name="image-outline" size={12} color={colors.textMuted} />
              <Text style={ui.muted}>{entry.screenshot_count}</Text>
            </View>
          ) : null}
        </View>
      ) : null}
    </Pressable>
  )
}

/** Free-standing ideas, reviews, observations and trade plans — the website's "Ideas & reviews", on the phone. */
export function EntriesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const [entries, setEntries] = useState<JournalEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback((manual: boolean) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    if (manual) setRefreshing(true)
    listEntries(controller.signal)
      .then((r) => {
        if (controller.signal.aborted) return
        setEntries(r.entries)
        setError(null)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Could not load your notes.')
      })
      .finally(() => {
        if (inFlight.current === controller) setRefreshing(false)
      })
  }, [])

  // Reload whenever the screen comes back into view (after creating / editing / deleting one).
  useFocusEffect(
    useCallback(() => {
      load(false)
      return () => inFlight.current?.abort()
    }, [load]),
  )

  const sorted = entries ? [...entries].sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at)) : null

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      {sorted === null && !error ? (
        <Loading fill />
      ) : (
        <FlatList
          data={sorted ?? []}
          keyExtractor={(e) => e.id}
          renderItem={({ item }) => <EntryCard entry={item} onPress={() => navigation.navigate('Entry', { entry: item })} />}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.accent} colors={[colors.accent]} />}
          ListHeaderComponent={
            <View style={styles.head}>
              {error ? <Notice>{entries ? `Showing the last loaded notes. Refresh failed: ${error}` : error}</Notice> : null}
              <Button label="New note" icon="add" onPress={() => navigation.navigate('Entry', {})} />
            </View>
          }
          ListEmptyComponent={sorted ? <Empty icon="document-text-outline" title="No notes yet" text="Capture a market idea, a weekly review or a trade plan, with screenshots." /> : null}
        />
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.xxl, gap: spacing.md, flexGrow: 1 },
  head: { gap: spacing.md },
  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  kind: { ...type.label, color: colors.textSecondary },
  instrument: { ...type.label, color: colors.textPrimary, marginLeft: spacing.xs },
  date: { ...type.small, fontVariant: ['tabular-nums'], marginLeft: 'auto' },
  shots: { flexDirection: 'row', alignItems: 'center', gap: 3 },
})
