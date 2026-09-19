import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useCallback, useRef, useState } from 'react'
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { listEntries } from '../api/entries'
import { formatUpdated } from '../format'
import type { RootStackParamList } from '../navigation/RootStack'
import { colors, radius, spacing } from '../theme'
import type { EntryKind, JournalEntry } from '../types/entries'

export const KIND_LABEL: Record<EntryKind, string> = {
  idea: 'Idea',
  review: 'Review',
  observation: 'Observation',
  plan: 'Trade plan',
}
export const KIND_COLOR: Record<EntryKind, string> = {
  idea: colors.accent,
  review: colors.warning,
  observation: colors.textSecondary,
  plan: colors.positive,
}

function EntryCard({ entry, onPress }: { entry: JournalEntry; onPress: () => void }) {
  const color = KIND_COLOR[entry.kind] ?? colors.textSecondary
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.card, pressed && { opacity: 0.7 }]}>
      <View style={styles.cardTop}>
        <View style={[styles.kind, { borderColor: color }]}>
          <Text style={[styles.kindText, { color }]}>{KIND_LABEL[entry.kind] ?? entry.kind}</Text>
        </View>
        {entry.instrument ? <Text style={styles.instrument}>{entry.instrument}</Text> : null}
        <Text style={styles.date}>{formatUpdated(entry.updated_at || entry.created_at)}</Text>
      </View>
      {entry.title ? <Text style={styles.title}>{entry.title}</Text> : null}
      {entry.body ? (
        <Text style={styles.body} numberOfLines={3}>
          {entry.body}
        </Text>
      ) : null}
      {entry.tags.length > 0 || entry.screenshot_count > 0 ? (
        <View style={styles.meta}>
          {entry.tags.map((t) => (
            <Text key={t} style={styles.tag}>
              {t}
            </Text>
          ))}
          {entry.screenshot_count > 0 ? <Text style={styles.metaText}>📷 {entry.screenshot_count}</Text> : null}
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
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      {error ? <Text style={styles.err}>{entries ? `Showing last loaded notes — refresh failed: ${error}` : error}</Text> : null}
      {sorted === null && !error ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} size="large" />
        </View>
      ) : (
        <FlatList
          data={sorted ?? []}
          keyExtractor={(e) => e.id}
          renderItem={({ item }) => <EntryCard entry={item} onPress={() => navigation.navigate('Entry', { entry: item })} />}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.accent} colors={[colors.accent]} />}
          ListHeaderComponent={
            <Pressable onPress={() => navigation.navigate('Entry', {})} accessibilityRole="button" style={styles.newBtn}>
              <Text style={styles.newText}>＋ New note</Text>
            </Pressable>
          }
          ListEmptyComponent={
            sorted ? (
              <View style={styles.empty}>
                <Text style={styles.emptyTitle}>No notes yet</Text>
                <Text style={styles.emptyText}>Capture a market idea, a weekly review or a trade plan — with screenshots.</Text>
              </View>
            ) : null
          }
        />
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  err: {
    color: colors.negative,
    backgroundColor: 'rgba(239,68,68,0.1)',
    borderColor: 'rgba(239,68,68,0.3)',
    borderWidth: 1,
    borderRadius: radius.md,
    margin: spacing.lg,
    padding: spacing.md,
    fontSize: 12,
  },
  list: { padding: spacing.lg, gap: spacing.md, flexGrow: 1 },
  newBtn: {
    alignItems: 'center',
    borderColor: 'rgba(240,185,11,0.4)',
    backgroundColor: 'rgba(240,185,11,0.1)',
    borderWidth: 1,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
  },
  newText: { color: colors.accent, fontSize: 15, fontWeight: '600' },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.borderSubtle,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  kind: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 1 },
  kindText: { fontSize: 11, fontWeight: '700' },
  instrument: { color: colors.textPrimary, fontSize: 13, fontWeight: '600' },
  date: { color: colors.textMuted, fontSize: 12, marginLeft: 'auto' },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  body: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },
  meta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
  tag: {
    color: colors.textSecondary,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    fontSize: 11,
    overflow: 'hidden',
  },
  metaText: { color: colors.textMuted, fontSize: 12 },
  empty: { alignItems: 'center', paddingVertical: 48, paddingHorizontal: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  emptyText: { color: colors.textMuted, fontSize: 13, textAlign: 'center' },
})
