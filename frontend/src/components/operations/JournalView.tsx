import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { JournalResponse, JournalTradeItem, JournalUpdateRequest } from '../../types/operations'
import { OpsMetric, OpsUnavailable, SectionCard } from './primitives'
import { formatUsd, timeAgo } from '../../lib/format'
import { patchJournalEntry } from '../../api/operations'
import { ChartSnapshot } from '../journal/ChartSnapshot'
import { ScreenshotStrip } from '../journal/ScreenshotStrip'
import { StarRating } from '../journal/StarRating'
import { TagRecord, invalidateTagRecord } from '../journal/TagRecord'

type Outcome = 'all' | 'win' | 'loss'
const PAGE = 40

/** Preset setup categories from the legacy Streamlit journal form (free text still allowed). */
const SETUP_PRESETS = [
  'BREAKOUT',
  'SUPPORT / RESISTANCE BOUNCE',
  'ORDER BLOCK / FVG',
  'NEWS SCALP',
  'TREND FOLLOWING',
  'MEAN REVERSION',
  'LIQUIDITY GRAB',
  'SUPPLY & DEMAND',
  'CHART PATTERN',
  'CUSTOM SETUP',
]

function money(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v).replace('$', '')}`
}

export function JournalSummary({ data }: { data: JournalResponse }) {
  const wr = data.total_trades > 0 ? (data.wins / data.total_trades) * 100 : null
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <OpsMetric label="Closed trades" value={data.total_trades} />
      <OpsMetric
        label="Win / loss"
        value={`${data.wins} / ${data.losses}`}
        sub={wr === null ? undefined : `${wr.toFixed(0)}% win rate`}
      />
      <OpsMetric
        label="Net P&L (recorded)"
        value={money(data.total_net_profit)}
        tone={data.total_net_profit > 0 ? 'positive' : data.total_net_profit < 0 ? 'negative' : 'neutral'}
      />
      <OpsMetric label="Updated" value={timeAgo(data.timestamp) ?? '—'} />
    </div>
  )
}

function Stars({ n }: { n: number | null }) {
  if (!n || n <= 0) return <span className="text-muted">—</span>
  return <span className="text-warning">{'★'.repeat(Math.min(5, n))}</span>
}

/** Inline editor for the subjective annotation fields of one closed trade. */
function JournalEditor({
  entry,
  onSaved,
  onCancel,
}: {
  entry: JournalTradeItem
  onSaved: (updated: JournalTradeItem) => void
  onCancel: () => void
}) {
  const [setupTag, setSetupTag] = useState(entry.setup_tag ?? '')
  const [notes, setNotes] = useState(entry.notes ?? '')
  const [chartUrl, setChartUrl] = useState(entry.chart_snapshot_url ?? '')
  const [rating, setRating] = useState<number>(entry.rating ?? 0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const norm = (s: string) => s.trim()
  const dirty =
    norm(setupTag) !== (entry.setup_tag ?? '') ||
    notes !== (entry.notes ?? '') ||
    norm(chartUrl) !== (entry.chart_snapshot_url ?? '') ||
    rating !== (entry.rating ?? 0)

  async function save() {
    if (saving || !dirty) return
    setSaving(true)
    setError(null)
    // Send only the fields that actually changed.
    const body: JournalUpdateRequest = {}
    if (norm(setupTag) !== (entry.setup_tag ?? '')) body.setup_tag = norm(setupTag)
    if (notes !== (entry.notes ?? '')) body.notes = notes
    if (norm(chartUrl) !== (entry.chart_snapshot_url ?? '')) body.chart_snapshot_url = norm(chartUrl)
    if (rating !== (entry.rating ?? 0)) body.rating = rating
    try {
      const res = await patchJournalEntry(entry.trade_id, body)
      if ('setup_tag' in body) invalidateTagRecord()
      onSaved(res.entry)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
      setSaving(false)
    }
  }

  return (
    <div className="space-y-2 rounded border border-accent/30 bg-surface-elevated/40 p-3">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <label className="block text-[11px] text-muted">
          Setup tag
          <input
            list="journal-setup-presets"
            value={setupTag}
            onChange={(e) => setSetupTag(e.target.value)}
            disabled={saving}
            maxLength={120}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
          <datalist id="journal-setup-presets">
            {SETUP_PRESETS.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          {setupTag.trim() ? (
            <span className="mt-1 block">
              <TagRecord tag={setupTag} />
            </span>
          ) : null}
        </label>
        <label className="block text-[11px] text-muted">
          Chart snapshot URL
          <input
            value={chartUrl}
            onChange={(e) => setChartUrl(e.target.value)}
            disabled={saving}
            maxLength={3_000}
            placeholder="https://www.tradingview.com/x/…"
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
          />
          <span className="mt-0.5 block text-[10px] text-muted">
            Paste a TradingView snapshot link (Alt+S in TradingView) or a direct image URL.
          </span>
          {chartUrl.trim() ? (
            <span className="mt-1 block">
              <ChartSnapshot url={chartUrl} />
            </span>
          ) : null}
        </label>
      </div>
      <label className="block text-[11px] text-muted">
        Notes — setup rationale, confluences, lessons
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={saving}
          maxLength={20_000}
          rows={4}
          className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        />
      </label>

      <div className="flex items-center gap-2 text-[11px] text-muted">
        <span>Rating</span>
        <StarRating value={rating} onChange={setRating} disabled={saving} />
      </div>

      <div>
        <p className="text-[11px] text-muted">Screenshots</p>
        <div className="mt-1">
          <ScreenshotStrip tradeId={entry.trade_id} />
        </div>
      </div>

      {error ? (
        <p className="rounded border border-negative/30 bg-negative/10 px-2 py-1 text-[11px] text-negative" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={save}
          disabled={saving || !dirty}
          className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] text-accent disabled:opacity-40"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded border border-border px-2.5 py-1 text-[11px] text-secondary hover:text-primary disabled:opacity-40"
        >
          Cancel
        </button>
        <span className="ml-auto font-mono text-[10px] text-muted">
          Annotations only · execution facts are immutable
        </span>
      </div>
    </div>
  )
}

/**
 * Trade journal over the authoritative `closed_trades` table. Client-side
 * filtering (small dataset); no request per keystroke. The subjective
 * annotation fields (setup tag / notes / chart snapshot) are editable in place
 * via `PATCH /api/operations/journal/{trade_id}` — every execution / trade fact
 * stays read-only. No execution or broker capability is exposed here.
 */
export function JournalView({
  data,
  onEntryUpdated,
  focusTradeId,
}: {
  data: JournalResponse
  onEntryUpdated?: (entry: JournalTradeItem) => void
  /** deep-link: open this trade's editor and scroll to it (from the calendar) */
  focusTradeId?: string | null
}) {
  const [account, setAccount] = useState('all')
  const [outcome, setOutcome] = useState<Outcome>('all')
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE)
  const [editing, setEditing] = useState<string | null>(null)
  const focusedRef = useRef<HTMLTableRowElement>(null)
  const focusHandled = useRef<string | null>(null)

  useEffect(() => {
    if (!focusTradeId || focusHandled.current === focusTradeId) return
    if (!data.entries.some((e) => e.trade_id === focusTradeId)) return
    focusHandled.current = focusTradeId
    setEditing(focusTradeId)
    // make sure it's within the paged window
    const idx = data.entries.findIndex((e) => e.trade_id === focusTradeId)
    if (idx >= 0) setLimit((l) => Math.max(l, idx + PAGE))
    setTimeout(() => focusedRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 60)
  }, [focusTradeId, data.entries])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return data.entries.filter((e) => {
      if (account !== 'all' && e.account_id !== account) return false
      if (outcome === 'win' && e.net_profit <= 0) return false
      if (outcome === 'loss' && e.net_profit >= 0) return false
      if (
        q &&
        !e.symbol.toLowerCase().includes(q) &&
        !(e.setup_tag ?? '').toLowerCase().includes(q) &&
        !(e.notes ?? '').toLowerCase().includes(q) &&
        !e.trade_id.toLowerCase().includes(q)
      ) {
        return false
      }
      return true
    })
  }, [data.entries, account, outcome, query])

  const shown = filtered.slice(0, limit)

  // With a single broker account, a column of identical 19-digit ids is pure
  // noise — only surface the account filter + column when there's more than one.
  const multiAccount = data.accounts.length > 1
  const colCount = multiAccount ? 11 : 10

  if (data.entries.length === 0) {
    return (
      <SectionCard title="Trade journal">
        <OpsUnavailable>
          No journal entries — the <code>closed_trades</code> table is empty.
        </OpsUnavailable>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      title="Trade journal"
      action={<span className="font-mono text-[11px] text-muted">{data.source} · annotations editable</span>}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="jrnl-q">Search journal</label>
        <input
          id="jrnl-q"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setLimit(PAGE) }}
          placeholder="Symbol, tag, note, id…"
          autoComplete="off"
          className="w-48 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        />
        {multiAccount ? (
          <select
            value={account}
            onChange={(e) => { setAccount(e.target.value); setLimit(PAGE) }}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-primary"
            aria-label="Filter by account"
          >
            <option value="all">All accounts</option>
            {data.accounts.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        ) : null}
        {(['all', 'win', 'loss'] as Outcome[]).map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => { setOutcome(o); setLimit(PAGE) }}
            className={`rounded border px-2 py-0.5 text-[11px] ${
              outcome === o ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-secondary hover:text-primary'
            }`}
          >
            {o === 'all' ? 'All' : o === 'win' ? 'Wins' : 'Losses'}
          </button>
        ))}
        <span className="ml-auto font-mono text-[11px] text-muted">{filtered.length} / {data.entries.length}</span>
      </div>

      {filtered.length === 0 ? (
        <OpsUnavailable>No trades match the current filter.</OpsUnavailable>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead className="border-b border-border text-muted">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium">Closed</th>
                <th className="px-2 py-1.5 text-left font-medium">Symbol</th>
                <th className="px-2 py-1.5 text-left font-medium">Dir</th>
                <th className="px-2 py-1.5 text-right font-medium">Vol</th>
                <th className="px-2 py-1.5 text-right font-medium">Entry</th>
                <th className="px-2 py-1.5 text-right font-medium">Exit</th>
                <th className="px-2 py-1.5 text-right font-medium">Net P&L</th>
                <th className="px-2 py-1.5 text-left font-medium">Setup / note</th>
                <th className="px-2 py-1.5 text-left font-medium">Rating</th>
                {multiAccount ? <th className="px-2 py-1.5 text-left font-medium">Account</th> : null}
                <th className="px-2 py-1.5 text-right font-medium">Edit</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((e: JournalTradeItem) => {
                const isEditing = editing === e.trade_id
                return (
                  <Fragment key={e.trade_id}>
                  <tr
                    ref={e.trade_id === focusTradeId ? focusedRef : undefined}
                    className={`align-top ${isEditing ? '' : 'border-b border-border-subtle/60'} ${
                      e.trade_id === focusTradeId ? 'bg-accent/5' : ''
                    }`}
                  >
                    <td className="whitespace-nowrap px-2 py-1.5 font-mono text-secondary">{e.exit_time.slice(0, 16).replace('T', ' ')}</td>
                    <td className="px-2 py-1.5">
                      <Link to={`/workspace/market?symbol=${encodeURIComponent(e.symbol)}`} className="font-mono font-semibold text-primary hover:text-accent">
                        {e.symbol}
                      </Link>
                    </td>
                    <td className={`px-2 py-1.5 font-mono ${e.direction.includes('LONG') || e.direction.includes('BUY') ? 'text-positive' : 'text-negative'}`}>
                      {e.direction}
                    </td>
                    <td className="px-2 py-1.5 text-right font-mono tabular-nums text-secondary">{e.volume}</td>
                    <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">{e.entry_price}</td>
                    <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">{e.exit_price}</td>
                    <td className={`px-2 py-1.5 text-right font-mono tabular-nums ${e.net_profit > 0 ? 'text-positive' : e.net_profit < 0 ? 'text-negative' : 'text-secondary'}`}>
                      {money(e.net_profit)}
                    </td>
                    <td className="max-w-[16rem] px-2 py-1.5 text-secondary">
                      {e.setup_tag ? <span className="mr-1 rounded bg-surface-elevated px-1 text-[10px] text-muted">{e.setup_tag}</span> : null}
                      {e.notes ?? (e.setup_tag ? '' : <span className="text-muted">—</span>)}
                      {e.screenshot_count ? (
                        <span className="ml-1 text-[10px] text-muted">📷 {e.screenshot_count}</span>
                      ) : null}
                      {e.chart_snapshot_url ? (
                        <span className="ml-1 inline-block align-middle">
                          <ChartSnapshot url={e.chart_snapshot_url} compact />
                        </span>
                      ) : null}
                    </td>
                    <td className="px-2 py-1.5"><Stars n={e.rating} /></td>
                    {multiAccount ? (
                      <td className="px-2 py-1.5 font-mono text-muted" title={e.account_id}>
                        …{e.account_id.slice(-6)}
                      </td>
                    ) : null}
                    <td className="px-2 py-1.5 text-right">
                      <button
                        type="button"
                        onClick={() => setEditing(isEditing ? null : e.trade_id)}
                        className="rounded border border-border px-1.5 py-0.5 text-[10px] text-secondary hover:border-accent/40 hover:text-accent"
                      >
                        {isEditing ? 'Close' : 'Edit'}
                      </button>
                    </td>
                  </tr>
                  {isEditing ? (
                    <tr className="border-b border-border-subtle/60 bg-surface-elevated/20">
                      <td colSpan={colCount} className="p-0">
                        {/* sticky-left keeps the editor in view even while the wide
                            table is scrolled right on a phone */}
                        <div className="sticky left-0 w-[calc(100vw-2rem)] p-3 sm:w-auto sm:max-w-3xl">
                          <JournalEditor
                            entry={e}
                            onSaved={(updated) => {
                              onEntryUpdated?.(updated)
                              setEditing(null)
                            }}
                            onCancel={() => setEditing(null)}
                          />
                        </div>
                      </td>
                    </tr>
                  ) : null}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {limit < filtered.length ? (
        <button
          type="button"
          onClick={() => setLimit((l) => l + PAGE)}
          className="mt-2 rounded border border-border px-2.5 py-1 text-[11px] text-primary hover:bg-surface-hover"
        >
          Show {Math.min(PAGE, filtered.length - limit)} more
        </button>
      ) : null}

      <p className="mt-3 text-[11px] text-muted">
        Source: <code>closed_trades</code> (execution facts + subjective
        setup_tag / notes / chart snapshot). Only the annotation fields are
        editable (<code>PATCH /api/operations/journal/{'{trade_id}'}</code>);
        symbol, side, prices, volume, timestamps, P&L and ids are immutable.
        Nothing here submits, modifies or transmits an order.
      </p>
    </SectionCard>
  )
}
