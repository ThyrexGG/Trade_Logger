import { useState } from 'react'
import type { JournalTradeItem } from '../../types/operations'
import { patchJournalEntry } from '../../api/operations'
import { invalidateTagRecord } from './TagRecord'
import { useToast } from '../../lib/toast'
import { QUICK_TAGS } from './reviewOptions'

/** Short table wording for the three one-tap answers, with the tone each one takes when picked. */
const SHORT: Record<string, { label: string; on: string }> = {
  'By my rules': { label: 'By rules', on: 'border-positive/50 bg-positive/10 text-positive' },
  'Bent my rules': { label: 'Bent', on: 'border-warning/50 bg-warning/10 text-warning' },
  Rushed: { label: 'Rushed', on: 'border-negative/50 bg-negative/10 text-negative' },
}

/**
 * The one tap per trade, for a table row: By rules / Bent / Rushed. Tapping the lit one clears it.
 * Same answer, same setup tag, same save as the Cards view, so Analytics' rules card reads both.
 * A tag the user typed themselves is left alone until they tap one of these.
 */
export function RulesTap({ entry, onSaved }: { entry: JournalTradeItem; onSaved: (updated: JournalTradeItem) => void }) {
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const current = QUICK_TAGS.find((t) => t.value.toLowerCase() === (entry.setup_tag ?? '').trim().toLowerCase())?.value ?? ''

  async function pick(value: string) {
    if (busy) return
    setBusy(true)
    try {
      const res = await patchJournalEntry(entry.trade_id, { setup_tag: current === value ? '' : value })
      invalidateTagRecord()
      onSaved(res.entry)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save that')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div role="group" aria-label={`How was this ${entry.symbol} trade?`} className="inline-flex gap-1">
      {QUICK_TAGS.map((t) => {
        const short = SHORT[t.value] ?? { label: t.label, on: 'border-accent bg-surface-hover text-accent' }
        const on = current === t.value
        return (
          <button
            key={t.value}
            type="button"
            title={t.hint}
            aria-pressed={on}
            disabled={busy}
            onClick={() => pick(t.value)}
            className={`whitespace-nowrap rounded border px-1.5 py-0.5 text-[10px] transition-colors disabled:opacity-60 ${
              on ? `${short.on} font-semibold` : 'border-border text-muted hover:border-accent/40 hover:text-primary'
            }`}
          >
            {short.label}
          </button>
        )
      })}
    </div>
  )
}

/** True when the trade carries one of the three one-tap answers. */
export function isRulesMarked(entry: Pick<JournalTradeItem, 'setup_tag'>): boolean {
  const tag = (entry.setup_tag ?? '').trim().toLowerCase()
  return QUICK_TAGS.some((t) => t.value.toLowerCase() === tag)
}
