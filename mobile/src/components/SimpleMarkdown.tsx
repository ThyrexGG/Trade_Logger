import { Fragment, type ReactNode } from 'react'
import { StyleSheet, Text, View } from 'react-native'
import { colors, spacing } from '../theme'

/** **bold** and `code` inside one line of text. */
function inline(text: string, keyBase: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return parts.map((p, i) => {
    const key = `${keyBase}-${i}`
    if (p.startsWith('**') && p.endsWith('**') && p.length > 4) {
      return (
        <Text key={key} style={styles.bold}>
          {p.slice(2, -2)}
        </Text>
      )
    }
    if (p.startsWith('`') && p.endsWith('`') && p.length > 2) {
      return (
        <Text key={key} style={styles.code}>
          {p.slice(1, -1)}
        </Text>
      )
    }
    return <Fragment key={key}>{p}</Fragment>
  })
}

/**
 * The small slice of Markdown the assistant actually uses: headings, bullets,
 * numbered lists, **bold** and `code`. Anything else is shown as plain text.
 */
export function SimpleMarkdown({ text, color = colors.textPrimary }: { text: string; color?: string }) {
  const lines = text.replace(/\r/g, '').split('\n')
  return (
    <View style={{ gap: 4 }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd()
        if (!line.trim()) return <View key={i} style={{ height: 4 }} />
        const heading = /^#{1,6}\s+(.*)$/.exec(line)
        if (heading) {
          return (
            <Text key={i} style={[styles.text, styles.heading, { color }]}>
              {inline(heading[1], `h${i}`)}
            </Text>
          )
        }
        const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
        if (bullet) {
          return (
            <View key={i} style={styles.listRow}>
              <Text style={[styles.text, { color }]}>•</Text>
              <Text style={[styles.text, styles.listText, { color }]}>{inline(bullet[1], `b${i}`)}</Text>
            </View>
          )
        }
        const numbered = /^\s*(\d+)[.)]\s+(.*)$/.exec(line)
        if (numbered) {
          return (
            <View key={i} style={styles.listRow}>
              <Text style={[styles.text, { color }]}>{numbered[1]}.</Text>
              <Text style={[styles.text, styles.listText, { color }]}>{inline(numbered[2], `n${i}`)}</Text>
            </View>
          )
        }
        return (
          <Text key={i} style={[styles.text, { color }]}>
            {inline(line, `p${i}`)}
          </Text>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  text: { fontSize: 15, lineHeight: 21 },
  heading: { fontWeight: '700', marginTop: spacing.xs },
  bold: { fontWeight: '700' },
  code: { fontFamily: 'monospace', backgroundColor: 'rgba(255,255,255,0.08)' },
  listRow: { flexDirection: 'row', gap: spacing.sm, paddingRight: spacing.sm },
  listText: { flex: 1 },
})
