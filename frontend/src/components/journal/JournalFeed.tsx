import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { JournalResponse, JournalTradeItem, JournalUpdateRequest } from '../../types/operations'
import { formatUsd } from '../../lib/format'
import { patchJournalEntry } from '../../api/operations'
import { ChartSnapshot } from './ChartSnapshot'
import { ScreenshotStrip, type ScreenshotStripHandle } from './ScreenshotStrip'
import { StarRating } from './StarRating'
import { invalidateTagRecord } from './TagRecord'
import { OpsUnavailable } from '../operations/primitives'

const SAVE_DEBOUNCE_MS = 900

function money(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v).replace('$', '')}`
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

/**
 * One trade as a scrapbook-style entry: chart screenshot(s) up top, a plain
 * textarea for the writeup, P&L and tags around it — the Google-Doc habit
 * (paste image, write what happened) with the numbers filled in for you and
 * autosaved as you type, instead of a table row you have to click into.
 */
function FeedCard({
  entry,
  onSaved,
}: {
  entry: JournalTradeItem
  onSaved: (updated: JournalTradeItem) => void
}) {
  const [notes, setNotes] = useState(entry.notes ?? '')
  const [setupTag, setSetupTag] = useState(entry.setup_tag ?? '')
  const [chartUrl, setChartUrl] = useState(entry.chart_snapshot_url ?? '')
  const [rating, setRating] = useState(entry.rating ?? 0)
  const [status, setStatus] = useState<SaveStatus>('idle')
  const [showLinkField, setShowLinkField] = useState(Boolean(entry.chart_snapshot_url))
  const baseline = useRef({
    notes: entry.notes ?? '',
    setupTag: entry.setup_tag ?? '',
    chartUrl: entry.chart_snapshot_url ?? '',
    rating: entry.rating ?? 0,
  })
  const stripRef = useRef<ScreenshotStripHandle>(null)

  // Autosave: 900ms after the last keystroke/tag/rating/link change, send
  // only the fields that actually differ from what's confirmed saved. Same
  // annotation endpoint as the table view — execution facts are never
  // touched.
  useEffect(() => {
    const b = baseline.current
    const chartUrlTrim = chartUrl.trim()
    if (notes === b.notes && setupTag.trim() === b.setupTag && chartUrlTrim === b.chartUrl && rating === b.rating) return
    setStatus('saving')
    const t = setTimeout(async () => {
      const body: JournalUpdateRequest = {}
      if (notes !== b.notes) body.notes = notes
      if (setupTag.trim() !== b.setupTag) body.setup_tag = setupTag.trim()
      if (chartUrlTrim !== b.chartUrl) body.chart_snapshot_url = chartUrlTrim
      if (rating !== b.rating) body.rating = rating
      if (Object.keys(body).length === 0) return
      try {
        const res = await patchJournalEntry(entry.trade_id, body)
        baseline.current = {
          notes: res.entry.notes ?? '',
          setupTag: res.entry.setup_tag ?? '',
          chartUrl: res.entry.chart_snapshot_url ?? '',
          rating: res.entry.rating ?? 0,
        }
        if ('setup_tag' in body) invalidateTagRecord()
        onSaved(res.entry)
        setStatus('saved')
      } catch {
        setStatus('error')
      }
    }, SAVE_DEBOUNCE_MS)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notes, setupTag, chartUrl, rating, entry.trade_id])

  const win = entry.net_profit > 0
  const loss = entry.net_profit < 0

  return (
    <article
      className="space-y-3 rounded-lg border border-border bg-surface p-4"
      onPaste={(e) => {
        // Ctrl+V anywhere in the card (including while typing in the notes
        // box) routes an image straight to the screenshot strip; plain text
        // paste is left alone since no image item is found for it.
        const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith('image/'))
        const file = item?.getAsFile()
        if (file) {
          e.preventDefault()
          stripRef.current?.upload(file)
        }
      }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <Link
            to={`/workspace/market?symbol=${encodeURIComponent(entry.symbol)}`}
            className="font-mono text-base font-semibold text-primary hover:text-accent"
          >
            {entry.symbol}
          </Link>
          <span className={`font-mono text-xs ${entry.direction.includes('LONG') || entry.direction.includes('BUY') ? 'text-positive' : 'text-negative'}`}>
            {entry.direction}
          </span>
          <span className="text-[11px] text-muted">{entry.exit_time.slice(0, 16).replace('T', ' ')}</span>
        </div>
        <span className={`font-mono text-lg font-semibold ${win ? 'text-positive' : loss ? 'text-negative' : 'text-secondary'}`}>
          {win ? 'Won: ' : loss ? 'Lost: ' : 'Net: '}
          {money(entry.net_profit)}
        </span>
      </div>

      <ScreenshotStrip ref={stripRef} tradeId={entry.trade_id} layout="stack" />

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="What happened — bias, structure, entry, how it played out… (paste a screenshot with Ctrl+V anywhere in this card)"
        rows={4}
        maxLength={20_000}
        className="w-full resize-y rounded border border-border bg-background px-3 py-2 text-sm text-primary placeholder:text-muted focus:border-accent focus:outline-none"
      />

      {showLinkField ? (
        <label className="block text-[11px] text-muted">
          Chart link (TradingView snapshot or any image URL)
          <input
            value={chartUrl}
            onChange={(e) => setChartUrl(e.target.value)}
            placeholder="https://www.tradingview.com/x/…"
            maxLength={3_000}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
          />
          {chartUrl.trim() ? (
            <span className="mt-1 block">
              <ChartSnapshot url={chartUrl} />
            </span>
          ) : null}
        </label>
      ) : (
        <button
          type="button"
          onClick={() => setShowLinkField(true)}
          className="text-[11px] text-accent hover:underline"
        >
          + add a chart link instead of a screenshot
        </button>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={setupTag}
          onChange={(e) => setSetupTag(e.target.value)}
          placeholder="setup tag (e.g. NY-AM-OB)"
          maxLength={120}
          className="w-48 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <StarRating value={rating} onChange={setRating} />
        <span className="ml-auto text-[10px] text-muted" aria-live="polite">
          {status === 'saving' ? 'Saving…' : status === 'saved' ? 'Saved' : status === 'error' ? 'Save failed — check your connection' : ''}
        </span>
      </div>
    </article>
  )
}

/**
 * Scrollable, doc-like alternative to the journal table: one card per closed
 * trade — screenshots, a freeform writeup, P&L and tag — autosaving as you
 * type instead of an explicit Edit/Save step. Same data, same endpoint as
 * the table view (`JournalView`); just a different shape for people who
 * think in a running scrapbook rather than a spreadsheet.
 */
export function JournalFeed({
  data,
  onEntryUpdated,
}: {
  data: JournalResponse
  onEntryUpdated?: (entry: JournalTradeItem) => void
}) {
  const [limit, setLimit] = useState(20)
  const shown = data.entries.slice(0, limit)

  if (data.entries.length === 0) {
    return <OpsUnavailable>No journal entries — the closed_trades table is empty.</OpsUnavailable>
  }

  return (
    <div className="space-y-3">
      {shown.map((e) => (
        <FeedCard key={e.trade_id} entry={e} onSaved={(u) => onEntryUpdated?.(u)} />
      ))}
      {limit < data.entries.length ? (
        <button
          type="button"
          onClick={() => setLimit((l) => l + 20)}
          className="w-full rounded border border-border py-2 text-xs text-primary hover:bg-surface-hover"
        >
          Show {Math.min(20, data.entries.length - limit)} more
        </button>
      ) : null}
    </div>
  )
}
