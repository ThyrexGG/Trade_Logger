import { useState } from 'react'
import { deleteManualTrade } from '../../api/operations'
import { invalidateAllCaches } from '../../lib/dataCache'
import { useToast } from '../../lib/toast'
import type { JournalTradeItem } from '../../types/operations'
import { ManualTradeForm } from './ManualTradeForm'

/** Trades logged by hand carry a `MANUAL_` id (the same rule the server applies). Synced trades come from the
 * broker and would be overwritten by the next sync, so they are never editable or deletable here. */
export function isHandLogged(tradeId: string): boolean {
  return tradeId.startsWith('MANUAL_')
}

/**
 * "Logged by hand" strip for one journal entry: correct its numbers or delete it. Renders nothing for a
 * broker-synced trade. Analytics, the calendar and the loss limits read the same table, so every cached page
 * is dropped once a trade changes.
 */
export function HandLoggedControls({
  entry,
  knownAccounts,
  onUpdated,
  onDeleted,
}: {
  entry: JournalTradeItem
  knownAccounts: string[]
  onUpdated: (entry: JournalTradeItem) => void
  onDeleted: (tradeId: string) => void
}) {
  const toast = useToast()
  const [mode, setMode] = useState<'idle' | 'editing' | 'confirming'>('idle')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isHandLogged(entry.trade_id)) return null

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      await deleteManualTrade(entry.trade_id)
      invalidateAllCaches()
      toast.success(`${entry.symbol} trade deleted`)
      onDeleted(entry.trade_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the trade.')
      setBusy(false)
    }
  }

  if (mode === 'editing') {
    return (
      <ManualTradeForm
        knownAccounts={knownAccounts}
        editing={entry}
        onCancel={() => setMode('idle')}
        onCreated={(updated) => {
          invalidateAllCaches()
          toast.success(`${updated.symbol} trade updated`)
          setMode('idle')
          onUpdated(updated)
        }}
      />
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-2 text-[11px]">
      <span className="text-muted">Logged by hand</span>
      {mode === 'confirming' ? (
        <>
          <span className="text-secondary">Delete this trade and its screenshots?</span>
          <button
            type="button"
            onClick={() => void remove()}
            disabled={busy}
            className="rounded border border-negative/40 bg-negative/10 px-2 py-0.5 text-negative hover:bg-negative/20 disabled:opacity-40"
          >
            {busy ? 'Deleting…' : 'Yes, delete'}
          </button>
          <button
            type="button"
            onClick={() => setMode('idle')}
            disabled={busy}
            className="rounded border border-border px-2 py-0.5 text-secondary hover:bg-surface-hover disabled:opacity-40"
          >
            Keep it
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={() => setMode('editing')}
            className="rounded border border-border px-2 py-0.5 text-secondary hover:border-accent/40 hover:text-accent"
          >
            Edit details
          </button>
          <button
            type="button"
            onClick={() => setMode('confirming')}
            className="rounded border border-border px-2 py-0.5 text-secondary hover:border-negative/40 hover:text-negative"
          >
            Delete
          </button>
        </>
      )}
      {error ? <span className="text-negative" role="alert">{error}</span> : null}
    </div>
  )
}
