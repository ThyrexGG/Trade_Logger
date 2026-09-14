import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createJournalEntry,
  getJournal,
  patchJournalEntry,
  uploadJournalScreenshot,
} from '../../api/operations'
import type { JournalEntryKind, JournalTradeItem } from '../../types/operations'
import type { ChartAnalysisResponse } from '../../types/chartAnalysis'
import { formatUsd } from '../../lib/format'

type Mode = 'trade' | 'note'

function buildDescription(r: ChartAnalysisResponse): string {
  const lines: string[] = []
  const head = [r.direction?.toUpperCase(), r.symbol, r.timeframe].filter(Boolean).join(' ')
  lines.push(`Chart Analyzer read${head ? ': ' + head : ''}`)

  const levels: string[] = []
  if (r.entry !== null) levels.push(`Entry ${r.entry}`)
  if (r.stop_loss !== null) levels.push(`SL ${r.stop_loss}`)
  if (r.take_profit !== null) levels.push(`TP ${r.take_profit}`)
  if (r.risk_reward !== null) levels.push(`R:R ${r.risk_reward}`)
  if (levels.length) lines.push(levels.join(' · '))

  if (r.additional_targets.length) lines.push(`Additional targets: ${r.additional_targets.join(', ')}`)
  if (r.pattern) lines.push(`Pattern: ${r.pattern}`)
  if (r.confluences.length) lines.push(`Confluences: ${r.confluences.join(', ')}`)
  if (r.setup_rating !== null) {
    lines.push(`Setup rating: ${r.setup_rating}/10${r.rating_reasoning ? ' — ' + r.rating_reasoning : ''}`)
  }
  if (r.caveats) lines.push(`Caveats: ${r.caveats}`)
  return lines.join('\n')
}

function base64ToFile(base64: string, mime: string, filename: string): File {
  const bytes = atob(base64)
  const arr = new Uint8Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
  return new File([arr], filename, { type: mime })
}

function extFor(mime: string): string {
  return mime === 'image/jpeg' ? 'jpg' : mime === 'image/webp' ? 'webp' : 'png'
}

/**
 * Lets the user attach a finished chart analysis to the Journal — either onto
 * a real closed trade they actually took (screenshot + a notes append), or as
 * a free-standing note when it's just an analyzed setup, not (yet) a trade.
 * Uses the same screenshot/notes/free-entry endpoints the Journal page
 * already exposes — no new backend surface.
 */
export function SaveToJournal({ result }: { result: ChartAnalysisResponse }) {
  const [mode, setMode] = useState<Mode>('trade')
  const [description, setDescription] = useState(() => buildDescription(result))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedTradeId, setSavedTradeId] = useState<string | null>(null)
  const [savedNoteId, setSavedNoteId] = useState<string | null>(null)

  // trade picker (mode: 'trade')
  const [trades, setTrades] = useState<JournalTradeItem[] | null>(null)
  const [tradesError, setTradesError] = useState<string | null>(null)
  const [search, setSearch] = useState(result.symbol ?? '')
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null)

  useEffect(() => {
    if (mode !== 'trade' || trades !== null) return
    getJournal()
      .then((r) => setTrades(r.entries))
      .catch((e) => setTradesError(e instanceof Error ? e.message : 'Could not load the journal.'))
  }, [mode, trades])

  const filteredTrades = useMemo(() => {
    const list = trades ?? []
    const q = search.trim().toUpperCase()
    const narrowed = q ? list.filter((t) => t.symbol.includes(q) || t.account_id.toUpperCase().includes(q)) : list
    return narrowed.slice(0, 25)
  }, [trades, search])

  // note fields (mode: 'note')
  const [kind, setKind] = useState<JournalEntryKind>('review')
  const [instrument, setInstrument] = useState(result.symbol ?? '')
  const [title, setTitle] = useState(
    [result.direction?.toUpperCase(), result.symbol, 'chart analysis'].filter(Boolean).join(' '),
  )

  async function saveToTrade() {
    if (!selectedTradeId) return
    setBusy(true)
    setError(null)
    try {
      const trade = (trades ?? []).find((t) => t.trade_id === selectedTradeId)
      if (result.image_base64 && result.image_mime) {
        const file = base64ToFile(result.image_base64, result.image_mime, `chart-analysis.${extFor(result.image_mime)}`)
        await uploadJournalScreenshot(selectedTradeId, file, 'Chart Analyzer')
      }
      const merged = trade?.notes ? `${trade.notes}\n\n---\n${description}` : description
      await patchJournalEntry(selectedTradeId, { notes: merged })
      setSavedTradeId(selectedTradeId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save to that trade.')
    } finally {
      setBusy(false)
    }
  }

  async function saveAsNote() {
    setBusy(true)
    setError(null)
    try {
      const entry = await createJournalEntry({
        kind,
        instrument: instrument.trim() || undefined,
        title: title.trim() || undefined,
        body: description,
      })
      if (result.image_base64 && result.image_mime) {
        const file = base64ToFile(result.image_base64, result.image_mime, `chart-analysis.${extFor(result.image_mime)}`)
        await uploadJournalScreenshot(entry.id, file, 'Chart Analyzer')
      }
      setSavedNoteId(entry.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the journal note.')
    } finally {
      setBusy(false)
    }
  }

  if (savedTradeId) {
    return (
      <div className="rounded-lg border border-positive/30 bg-positive/10 p-3 text-xs text-positive">
        Saved to that trade's journal entry.{' '}
        <Link to={`/operations/journal?trade=${encodeURIComponent(savedTradeId)}`} className="underline underline-offset-2">
          Open it
        </Link>
      </div>
    )
  }
  if (savedNoteId) {
    return (
      <div className="rounded-lg border border-positive/30 bg-positive/10 p-3 text-xs text-positive">
        Saved as a journal note.{' '}
        <Link to="/operations/journal" className="underline underline-offset-2">
          Open the journal
        </Link>
      </div>
    )
  }

  return (
    <div className="border-t border-border-subtle pt-3">
      <h4 className="text-xs font-semibold text-primary">Save to Journal</h4>
      <div className="mt-2 flex rounded-xl border border-border p-1 text-xs">
        {(['trade', 'note'] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`flex-1 rounded-lg px-2 py-1.5 font-medium transition-colors ${
              mode === m ? 'shadow' : 'text-muted'
            }`}
            style={mode === m ? { background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' } : undefined}
          >
            {m === 'trade' ? 'I traded this' : 'Just a note / idea'}
          </button>
        ))}
      </div>

      {mode === 'trade' ? (
        <div className="mt-2 space-y-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by symbol or account…"
            className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
          {tradesError ? (
            <p className="text-[11px] text-negative">{tradesError}</p>
          ) : trades === null ? (
            <p className="text-[11px] text-muted">Loading your closed trades…</p>
          ) : filteredTrades.length === 0 ? (
            <p className="text-[11px] text-muted">No closed trades match that filter.</p>
          ) : (
            <div className="max-h-40 space-y-1 overflow-y-auto rounded border border-border-subtle p-1">
              {filteredTrades.map((t) => (
                <button
                  key={t.trade_id}
                  type="button"
                  onClick={() => setSelectedTradeId(t.trade_id)}
                  className={`flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-[11px] ${
                    selectedTradeId === t.trade_id ? 'bg-accent/15 text-accent' : 'text-secondary hover:bg-surface-hover'
                  }`}
                >
                  <span className="truncate">
                    {t.symbol} · {t.direction} · {t.account_id} · {new Date(t.exit_time).toLocaleDateString()}
                  </span>
                  <span className={`font-mono ${t.net_profit >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {formatUsd(t.net_profit)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Kind
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as JournalEntryKind)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            >
              <option value="idea">Idea</option>
              <option value="review">Review</option>
              <option value="observation">Observation</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted">
            Instrument
            <input
              type="text"
              value={instrument}
              onChange={(e) => setInstrument(e.target.value)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label className="col-span-2 flex flex-col gap-1 text-[11px] text-muted">
            Title
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
            />
          </label>
        </div>
      )}

      <label className="mt-2 flex flex-col gap-1 text-[11px] text-muted">
        Description {mode === 'trade' ? '(appended to that trade’s notes)' : ''}
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          className="resize-y rounded border border-border bg-background px-2 py-1.5 text-xs text-primary focus:border-accent focus:outline-none"
        />
      </label>

      {error ? <p className="mt-1 text-[11px] text-negative">{error}</p> : null}

      <button
        type="button"
        onClick={mode === 'trade' ? saveToTrade : saveAsNote}
        disabled={busy || (mode === 'trade' && !selectedTradeId)}
        className="mt-2 w-full rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
        style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
      >
        {busy ? 'Saving…' : mode === 'trade' ? 'Attach to selected trade' : 'Save as journal note'}
      </button>
    </div>
  )
}
