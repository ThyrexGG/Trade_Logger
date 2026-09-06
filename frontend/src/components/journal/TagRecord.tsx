import { useEffect, useState } from 'react'
import { getJournalTagStats, type JournalTagStat } from '../../api/operations'

// one shared fetch for the page — the stats change only when a trade is tagged
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
      .catch(() => [])
      .finally(() => {
        inflight = null
      })
  }
  return inflight
}

/** Call after saving a tag so the next read reflects it. */
export function invalidateTagRecord() {
  cache = null
}

/** Your realised record on `tag` from closed trades — win rate + avg net P&L. */
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
  if (!hit || hit.n === 0) {
    return <span className="text-[10px] text-muted">No prior trades on “{tag}”.</span>
  }
  const wr = hit.win_rate == null ? '—' : `${Math.round(hit.win_rate * 100)}%`
  const exp = hit.expectancy ?? 0
  return (
    <span className="text-[10px] text-muted">
      Your record on “{hit.tag}”: <span className="text-secondary">{hit.n}</span> trades ·{' '}
      <span className="text-secondary">{wr}</span> win ·{' '}
      <span className={exp >= 0 ? 'text-positive' : 'text-negative'}>
        {exp >= 0 ? '+' : ''}
        {exp.toFixed(2)}
      </span>{' '}
      avg
    </span>
  )
}
