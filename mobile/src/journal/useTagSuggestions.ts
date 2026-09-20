import { useMemo } from 'react'
import { usePositionsContext } from '../positions/PositionsContext'
import { useJournal } from './JournalContext'
import { SETUP_PRESETS } from './presets'

/** Setup tags for the one-tap chips: the ones already used on any trade (open or closed) most-used first, then the starter presets you have not used yet. */
export function useTagSuggestions(): string[] {
  const { data: journal } = useJournal()
  const { data: positions } = usePositionsContext()
  return useMemo(() => {
    const counts = new Map<string, number>()
    const add = (tag: string | null | undefined) => {
      const t = tag?.trim()
      if (t) counts.set(t, (counts.get(t) ?? 0) + 1)
    }
    journal?.entries.forEach((e) => add(e.setup_tag))
    positions?.positions.forEach((p) => add(p.setup_tag))
    const used = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t)
    const seen = new Set(used.map((t) => t.toUpperCase()))
    return [...used, ...SETUP_PRESETS.filter((p) => !seen.has(p))]
  }, [journal, positions])
}
