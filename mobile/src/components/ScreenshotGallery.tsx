import { Image } from 'expo-image'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { authHeaders } from '../api/client'
import { deleteScreenshot, getScreenshots, screenshotUrl, uploadScreenshot } from '../api/screenshots'
import { PickError, pickScreenshot, type PickSource } from '../journal/pickImage'
import { colors, radius, spacing } from '../theme'
import type { JournalScreenshotMeta } from '../types/screenshots'

interface Props {
  /** closed trade id or open position id */
  ownerId: string
  /** called whenever the number of screenshots changes, so list screens can show the 📷 count */
  onCountChange?: (count: number) => void
}

function source(meta: JournalScreenshotMeta) {
  // The image endpoint is behind login; expo-image forwards these headers with its request.
  return { uri: screenshotUrl(meta), headers: authHeaders() }
}

/**
 * Screenshots for one trade: big, un-cropped previews stacked full-width, a
 * small "Add" button, and a full-screen viewer (pinch-zoom on iPhone) with delete.
 */
export function ScreenshotGallery({ ownerId, onCountChange }: Props) {
  const [shots, setShots] = useState<JournalScreenshotMeta[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewing, setViewing] = useState<JournalScreenshotMeta | null>(null)
  const countRef = useRef(onCountChange)
  countRef.current = onCountChange

  const apply = useCallback((next: JournalScreenshotMeta[]) => {
    setShots(next)
    countRef.current?.(next.length)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getScreenshots(ownerId, controller.signal)
      .then((r) => {
        if (!controller.signal.aborted) apply(r.screenshots)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setShots([])
        setError(err instanceof Error ? err.message : 'Could not load screenshots.')
      })
    return () => controller.abort()
  }, [ownerId, apply])

  async function add(from: PickSource) {
    setError(null)
    try {
      const uri = await pickScreenshot(from)
      if (!uri) return
      setBusy(true)
      const meta = await uploadScreenshot(ownerId, uri)
      apply([...(shots ?? []), meta])
    } catch (err) {
      setError(err instanceof PickError || err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  function chooseSource() {
    Alert.alert('Add screenshot', undefined, [
      { text: 'Take photo', onPress: () => void add('camera') },
      { text: 'Choose from library', onPress: () => void add('library') },
      { text: 'Cancel', style: 'cancel' },
    ])
  }

  function confirmDelete(meta: JournalScreenshotMeta) {
    Alert.alert('Delete this screenshot?', 'This removes it from the trade everywhere, including the website.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          setViewing(null)
          deleteScreenshot(meta.id)
            .then(() => apply((shots ?? []).filter((s) => s.id !== meta.id)))
            .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Delete failed.'))
        },
      },
    ])
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.title}>Screenshots{shots && shots.length ? ` (${shots.length})` : ''}</Text>
        <Pressable
          onPress={chooseSource}
          disabled={busy}
          accessibilityRole="button"
          style={({ pressed }) => [styles.addBtn, (busy || pressed) && { opacity: 0.6 }]}
        >
          {busy ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={styles.addText}>＋ Add</Text>}
        </Pressable>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {shots === null ? (
        <ActivityIndicator color={colors.accent} style={styles.loading} />
      ) : shots.length === 0 ? (
        <Pressable onPress={chooseSource} disabled={busy} accessibilityRole="button" style={styles.empty}>
          <Text style={styles.emptyText}>No screenshots yet — tap to add a chart photo</Text>
        </Pressable>
      ) : (
        shots.map((s) => (
          <Pressable key={s.id} onPress={() => setViewing(s)} accessibilityRole="imagebutton" accessibilityLabel="Open screenshot">
            <Image source={source(s)} style={styles.shot} contentFit="contain" cachePolicy="disk" transition={150} />
          </Pressable>
        ))
      )}

      <Modal visible={viewing !== null} animationType="fade" onRequestClose={() => setViewing(null)} statusBarTranslucent>
        <SafeAreaView style={styles.viewer}>
          <View style={styles.viewerBar}>
            <Pressable onPress={() => setViewing(null)} accessibilityRole="button" hitSlop={12}>
              <Text style={styles.viewerBtn}>Close</Text>
            </Pressable>
            {viewing ? (
              <Pressable onPress={() => confirmDelete(viewing)} accessibilityRole="button" hitSlop={12}>
                <Text style={[styles.viewerBtn, { color: colors.negative }]}>Delete</Text>
              </Pressable>
            ) : null}
          </View>
          {viewing ? (
            <ScrollView
              style={styles.zoom}
              contentContainerStyle={styles.zoomContent}
              maximumZoomScale={5}
              minimumZoomScale={1}
              centerContent
              showsHorizontalScrollIndicator={false}
              showsVerticalScrollIndicator={false}
            >
              <Image source={source(viewing)} style={styles.full} contentFit="contain" cachePolicy="disk" />
            </ScrollView>
          ) : null}
        </SafeAreaView>
      </Modal>
    </View>
  )
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  addBtn: {
    minWidth: 64,
    alignItems: 'center',
    borderColor: 'rgba(240,185,11,0.4)',
    backgroundColor: 'rgba(240,185,11,0.1)',
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
  },
  addText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  error: { color: colors.negative, fontSize: 12 },
  loading: { paddingVertical: spacing.lg },
  empty: {
    borderColor: colors.border,
    borderStyle: 'dashed',
    borderWidth: 1,
    borderRadius: radius.md,
    paddingVertical: spacing.xl,
    alignItems: 'center',
  },
  emptyText: { color: colors.textMuted, fontSize: 13 },
  // 16:10, contain: the whole chart is visible, never cropped.
  shot: { width: '100%', aspectRatio: 16 / 10, borderRadius: radius.md, backgroundColor: colors.background },
  viewer: { flex: 1, backgroundColor: '#000' },
  viewerBar: { flexDirection: 'row', justifyContent: 'space-between', padding: spacing.lg },
  viewerBtn: { color: colors.accent, fontSize: 16, fontWeight: '600' },
  zoom: { flex: 1 },
  zoomContent: { flexGrow: 1, justifyContent: 'center' },
  full: { width: '100%', height: '100%', minHeight: 400 },
})
