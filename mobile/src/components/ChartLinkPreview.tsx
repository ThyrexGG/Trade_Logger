import { Image } from 'expo-image'
import { useEffect, useState } from 'react'
import { Linking, Pressable, StyleSheet, Text } from 'react-native'
import { isLinkable, resolveChartImage } from '../lib/chartImage'
import { colors, radius, spacing } from '../theme'

/**
 * The chart link as a big, un-cropped picture (a TradingView share link or any
 * direct image URL) — tap to open the original. Falls back to a plain "Open link"
 * when the URL isn't an image or the snapshot is private/expired. Same behaviour
 * as the website's chart snapshot.
 */
export function ChartLinkPreview({ url }: { url: string }) {
  const link = url.trim()
  const image = resolveChartImage(link)
  const [broken, setBroken] = useState(false)

  // A new link deserves a fresh attempt.
  useEffect(() => setBroken(false), [image])

  if (!link || !isLinkable(link)) return null

  if (!image || broken) {
    return (
      <Pressable onPress={() => void Linking.openURL(link)} accessibilityRole="link">
        <Text style={styles.link}>Open link ↗</Text>
      </Pressable>
    )
  }
  return (
    <Pressable onPress={() => void Linking.openURL(link)} accessibilityRole="imagebutton" accessibilityLabel="Open chart link">
      <Image
        source={{ uri: image }}
        style={styles.image}
        contentFit="contain"
        cachePolicy="disk"
        transition={150}
        onError={() => setBroken(true)}
      />
    </Pressable>
  )
}

const styles = StyleSheet.create({
  // 16:10 + contain: the whole chart is visible, never cropped (the same call as the website).
  image: { width: '100%', aspectRatio: 16 / 10, borderRadius: radius.md, backgroundColor: colors.background },
  link: { color: colors.accent, fontSize: 13, fontWeight: '600', paddingVertical: spacing.xs },
})
