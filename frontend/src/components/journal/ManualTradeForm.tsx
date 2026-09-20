import { useMemo, useState } from 'react'
import { SectionCard } from '../intelligence/primitives'
import { createManualTrade, updateManualTrade } from '../../api/operations'
import { SETUP_PRESETS } from './PreTradeChecklistForm'
import type { JournalTradeItem } from '../../types/operations'

const ACCOUNT_KEY = 'tl.manualtrade.account'

/** A plain `datetime-local` input value ("2026-09-16T14:30") has no
 * timezone — the browser gives it in local time. Converting through `Date`
 * pins it to a real instant (UTC on the wire), so it stores and sorts
 * identically to an MT5-synced trade's entry_time/exit_time instead of
 * silently drifting by the viewer's UTC offset. */
function toIsoWithZone(local: string): string | null {
  if (!local) return null
  const d = new Date(local)
  return isNaN(d.getTime()) ? null : d.toISOString()
}

/** The inverse of `toIsoWithZone`: an ISO instant as a `datetime-local` value in the viewer's local time.
 * A timestamp with no zone is UTC, matching how the backend stores it. */
function toLocalInput(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

/** A zero volume / price means "not entered" — show an empty field, not a 0. */
const numText = (v: number) => (v ? String(v) : '')

interface Props {
  /** Existing account_ids, purely to suggest — this field stays free text so
   * a first-ever manual trade (no accounts yet) isn't blocked on one existing. */
  knownAccounts: string[]
  /** Called with the saved row (created or corrected) so the caller can drop it straight
   * into view without waiting on the next background refetch. */
  onCreated: (trade: JournalTradeItem) => void
  /** Correct this hand-logged trade instead of logging a new one — the form opens pre-filled. */
  editing?: JournalTradeItem
  /** Edit mode only: the Cancel button (there is no collapsed state to fall back to). */
  onCancel?: () => void
}

/**
 * Log a trade that never touched a broker sync — for money traded outside
 * MT5 or any connected account. Writes a real closed_trades row (see
 * `POST /api/operations/journal/trades`), so it appears in Analytics, the
 * calendar and this Journal exactly like a synced trade would.
 */
export function ManualTradeForm({ knownAccounts, onCreated, editing, onCancel }: Props) {
  const [open, setOpen] = useState(Boolean(editing))
  const [account, setAccount] = useState(() => {
    if (editing) return editing.account_id
    try {
      return localStorage.getItem(ACCOUNT_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [symbol, setSymbol] = useState(editing?.symbol ?? '')
  const [direction, setDirection] = useState<'BUY' | 'SELL'>(editing?.direction === 'SELL' ? 'SELL' : 'BUY')
  const [volume, setVolume] = useState(editing ? numText(editing.volume) : '')
  const [entryPrice, setEntryPrice] = useState(editing ? numText(editing.entry_price) : '')
  const [exitPrice, setExitPrice] = useState(editing ? numText(editing.exit_price) : '')
  const [commission, setCommission] = useState(editing ? numText(editing.commission) : '')
  const [swap, setSwap] = useState(editing ? numText(editing.swap) : '')
  const [grossProfit, setGrossProfit] = useState(editing ? String(editing.gross_profit) : '')
  const [entryTime, setEntryTime] = useState(editing ? toLocalInput(editing.entry_time) : '')
  const [exitTime, setExitTime] = useState(editing ? toLocalInput(editing.exit_time) : '')
  const [setupTag, setSetupTag] = useState(editing?.setup_tag ?? '')
  const [notes, setNotes] = useState(editing?.notes ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const netPreview = useMemo(() => {
    const g = parseFloat(grossProfit)
    if (!isFinite(g)) return null
    const c = parseFloat(commission) || 0
    const s = parseFloat(swap) || 0
    return g + c + s
  }, [grossProfit, commission, swap])

  function reset() {
    setSymbol('')
    setVolume('')
    setEntryPrice('')
    setExitPrice('')
    setCommission('')
    setSwap('')
    setGrossProfit('')
    setEntryTime('')
    setExitTime('')
    setSetupTag('')
    setNotes('')
  }

  async function submit() {
    setError(null)
    const acc = account.trim()
    const sym = symbol.trim().toUpperCase()
    const g = parseFloat(grossProfit)
    const entryIso = toIsoWithZone(entryTime)
    const exitIso = toIsoWithZone(exitTime)

    if (!acc) return setError('Account is required.')
    if (!sym) return setError('Symbol is required.')
    if (!isFinite(g)) return setError('Profit is required — enter 0 for a scratch trade.')
    if (!entryIso || !exitIso) return setError('Entry and exit time are both required.')
    if (new Date(exitIso) < new Date(entryIso)) return setError('Exit time is before entry time.')

    setBusy(true)
    try {
      const body = {
        account_id: acc,
        symbol: sym,
        direction,
        volume: parseFloat(volume) || 0,
        entry_price: parseFloat(entryPrice) || 0,
        exit_price: parseFloat(exitPrice) || 0,
        commission: parseFloat(commission) || 0,
        swap: parseFloat(swap) || 0,
        gross_profit: g,
        entry_time: entryIso,
        exit_time: exitIso,
        setup_tag: setupTag.trim() || undefined,
        // Correcting a trade: notes are only sent when changed (the server leaves them alone when absent),
        // so a note longer than this field's limit is never trimmed or lost by an unrelated correction.
        notes: editing ? (notes !== (editing.notes ?? '') ? notes : undefined) : notes.trim() || undefined,
      }
      if (editing) {
        onCreated(await updateManualTrade(editing.trade_id, body))
        return
      }
      const trade = await createManualTrade(body)
      try {
        localStorage.setItem(ACCOUNT_KEY, acc)
      } catch {
        /* private browsing / storage blocked */
      }
      onCreated(trade)
      reset()
      setOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the trade.')
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-fit rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-primary hover:bg-surface-hover"
      >
        + Log a trade
      </button>
    )
  }

  return (
    <SectionCard
      title={editing ? 'Edit this trade' : 'Log a trade'}
      info="For money traded outside any broker sync — writes a real journal row, same as an MT5-synced trade would. Profit is entered as your broker/platform actually reported it, not recalculated from price and volume."
    >
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Account
          <input
            type="text"
            list={`manual-trade-accounts-${editing?.trade_id ?? 'new'}`}
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            placeholder="e.g. OWN_MONEY"
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
          <datalist id={`manual-trade-accounts-${editing?.trade_id ?? 'new'}`}>
            {knownAccounts.map((a) => (
              <option key={a} value={a} />
            ))}
          </datalist>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Symbol
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="EURUSD"
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Direction
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as 'BUY' | 'SELL')}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          >
            <option value="BUY">Buy / Long</option>
            <option value="SELL">Sell / Short</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Volume <span className="normal-case text-muted/70">(optional)</span>
          <input
            type="number" step="any" value={volume} onChange={(e) => setVolume(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Entry price <span className="normal-case text-muted/70">(optional)</span>
          <input
            type="number" step="any" value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Exit price <span className="normal-case text-muted/70">(optional)</span>
          <input
            type="number" step="any" value={exitPrice} onChange={(e) => setExitPrice(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Entry time
          <input
            type="datetime-local" value={entryTime} onChange={(e) => setEntryTime(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Exit time
          <input
            type="datetime-local" value={exitTime} onChange={(e) => setExitTime(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Setup <span className="normal-case text-muted/70">(optional)</span>
          <input
            type="text" list={`manual-trade-setups-${editing?.trade_id ?? 'new'}`} value={setupTag} onChange={(e) => setSetupTag(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
          <datalist id={`manual-trade-setups-${editing?.trade_id ?? 'new'}`}>
            {SETUP_PRESETS.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </label>

        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Commission <span className="normal-case text-muted/70">(optional, usually negative)</span>
          <input
            type="number" step="any" value={commission} onChange={(e) => setCommission(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Swap <span className="normal-case text-muted/70">(optional)</span>
          <input
            type="number" step="any" value={swap} onChange={(e) => setSwap(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          Profit <span className="normal-case text-muted/70">(before commission/swap, as reported)</span>
          <input
            type="number" step="any" value={grossProfit} onChange={(e) => setGrossProfit(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
      </div>

      {netPreview !== null ? (
        <p className="mt-2 text-[11px] text-secondary">
          Net P&L: <span className={`font-mono font-semibold ${netPreview >= 0 ? 'text-positive' : 'text-negative'}`}>
            {netPreview >= 0 ? '+' : '-'}${Math.abs(netPreview).toFixed(2)}
          </span>
        </p>
      ) : null}

      <label className="mt-3 flex flex-col gap-1 text-[11px] text-muted">
        Notes <span className="normal-case text-muted/70">(optional)</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="What happened, why you took it, what you'd do differently"
          className="resize-y rounded border border-border bg-background px-2 py-1.5 text-xs text-primary focus:border-accent focus:outline-none"
        />
      </label>

      {error ? <p className="mt-2 text-xs text-negative" role="alert">{error}</p> : null}

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
          style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
        >
          {busy ? 'Saving…' : editing ? 'Save changes' : 'Save trade'}
        </button>
        <button
          type="button"
          onClick={() => { setError(null); if (editing) onCancel?.(); else setOpen(false) }}
          disabled={busy}
          className="rounded-lg border border-border px-3 py-1.5 text-xs text-secondary hover:bg-surface-hover disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </SectionCard>
  )
}
