import { useEffect, useState } from 'react'
import { StyleSheet, Text } from 'react-native'
import { getJournalTagStats, type JournalTagStat } from '../api/journal'
import { colors } from '../theme'

// One shared fetch — the stats only change when a trade is tagged.
let cache: JournalTagStat[] | null = null
let inflight: Promise<JournalTagStat[]> | null = null

function load(): Promise<JournalTagStat[]> {
  if (cache) return Promise.resolve(cache)
  if (!inflight) {
    inflight = getJournalTagStats()
      .then((r) => {
        cache = r.tags
        return r.tags
      })
      .catch(() => [] as JournalTagStat[])
      .finally(() => {
        inflight = null
      })
  }
  return inflight
}

/** Call after saving a tag so the next read reflects it. */
export function invalidateTagRecord(): void {
  cache = null
}

/** Your realised record on `tag` from closed trades — trades, win rate, average net P&L (same wording as the website). */
export function TagRecord({ tag }: { tag: string }) {
  const [stats, setStats] = useState<JournalTagStat[] | null>(cache)
  useEffect(() => {
    let alive = true
    void load().then((s) => alive && setStats(s))
    return () => {
      alive = false
    }
  }, [])

  const t = tag.trim().toUpperCase()
  if (!t || !stats) return null
  const hit = stats.find((s) => s.tag.toUpperCase() === t)
  if (!hit || hit.n === 0) return <Text style={styles.text}>No prior trades on “{tag.trim()}”.</Text>

  const wr = hit.win_rate == null ? '—' : `${Math.round(hit.win_rate * 100)}%`
  const exp = hit.expectancy ?? 0
  return (
    <Text style={styles.text}>
      Your record on “{hit.tag}”: <Text style={styles.strong}>{hit.n}</Text> trades · <Text style={styles.strong}>{wr}</Text> win ·{' '}
      <Text style={{ color: exp >= 0 ? colors.positive : colors.negative }}>
        {exp >= 0 ? '+' : ''}
        {exp.toFixed(2)}
      </Text>{' '}
      avg
    </Text>
  )
}

const styles = StyleSheet.create({
  text: { color: colors.textMuted, fontSize: 12 },
  strong: { color: colors.textSecondary },
})
