import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { PositionItem, PositionUpdateRequest } from '../../types/positions'
import { formatSignedAmount } from '../../lib/format'
import { patchPosition } from '../../api/positions'
import { ChartSnapshot } from './ChartSnapshot'
import { ScreenshotStrip, type ScreenshotStripHandle } from './ScreenshotStrip'
import { StarRating } from './StarRating'
import { invalidateTagRecord } from './TagRecord'

const SAVE_DEBOUNCE_MS = 900

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

/**
 * One currently-open trade, editable exactly like a closed journal card
 * (screenshot, notes, chart link, setup tag, rating) — autosaving to the same
 * open_positions row the Positions page reads. The backend carries these
 * annotations over to the resulting closed_trades entry the moment the
 * position actually closes, so nothing needs to be re-entered.
 */
function OpenTradeCard({ position }: { position: PositionItem }) {
  const [notes, setNotes] = useState(position.notes ?? '')
  const [setupTag, setSetupTag] = useState(position.setup_tag ?? '')
  const [chartUrl, setChartUrl] = useState(position.chart_snapshot_url ?? '')
  const [rating, setRating] = useState(position.rating ?? 0)
  const [status, setStatus] = useState<SaveStatus>('idle')
  const [showLinkField, setShowLinkField] = useState(Boolean(position.chart_snapshot_url))
  const [shotCount, setShotCount] = useState(0)
  const baseline = useRef({
    notes: position.notes ?? '',
    setupTag: position.setup_tag ?? '',
    chartUrl: position.chart_snapshot_url ?? '',
    rating: position.rating ?? 0,
  })
  const stripRef = useRef<ScreenshotStripHandle>(null)

  useEffect(() => {
    const b = baseline.current
    const chartUrlTrim = chartUrl.trim()
    if (notes === b.notes && setupTag.trim() === b.setupTag && chartUrlTrim === b.chartUrl && rating === b.rating) return
    setStatus('saving')
    const t = setTimeout(async () => {
      const body: PositionUpdateRequest = {}
      if (notes !== b.notes) body.notes = notes
      if (setupTag.trim() !== b.setupTag) body.setup_tag = setupTag.trim()
      if (chartUrlTrim !== b.chartUrl) body.chart_snapshot_url = chartUrlTrim
      if (rating !== b.rating) body.rating = rating
      if (Object.keys(body).length === 0) return
      try {
        const res = await patchPosition(position.position_id, body)
        baseline.current = {
          notes: res.entry.notes ?? '',
          setupTag: res.entry.setup_tag ?? '',
          chartUrl: res.entry.chart_snapshot_url ?? '',
          rating: res.entry.rating ?? 0,
        }
        if ('setup_tag' in body) invalidateTagRecord()
        setStatus('saved')
      } catch {
        setStatus('error')
      }
    }, SAVE_DEBOUNCE_MS)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notes, setupTag, chartUrl, rating, position.position_id])

  const win = position.floating_pnl > 0
  const loss = position.floating_pnl < 0

  return (
    <article
      className="space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-4"
      onPaste={(e) => {
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
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <Link
            to={`/workspace/market?symbol=${encodeURIComponent(position.symbol)}`}
            className="font-mono text-base font-semibold text-primary hover:text-accent"
          >
            {position.symbol}
          </Link>
          <span
            className={`font-mono text-xs ${
              position.direction.includes('BUY') || position.direction.includes('LONG') ? 'text-positive' : 'text-negative'
            }`}
          >
            {position.direction}
          </span>
          <span className="text-[11px] text-muted">
            {position.volume} @ {position.entry_price} → {position.current_price}
          </span>
        </div>
        <span className={`font-mono text-lg font-semibold ${win ? 'text-positive' : loss ? 'text-negative' : 'text-secondary'}`}>
          Floating: {formatSignedAmount(position.floating_pnl)}
        </span>
      </div>

      {chartUrl.trim() ? <ChartSnapshot url={chartUrl} large /> : null}
      <ScreenshotStrip
        ref={stripRef}
        tradeId={position.position_id}
        layout="stack"
        onCountChange={setShotCount}
        minimalAdd={shotCount > 0 || Boolean(chartUrl.trim())}
      />

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="What's the plan / what's happening — bias, structure, entry, how it's playing out so far… (paste a screenshot with Ctrl+V anywhere in this card)"
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
 * Currently-open trades, shown inline at the top of the journal — pulled from
 * the same live `open_positions` feed as the Positions page, so it updates on
 * the same schedule (45s, or immediately after a sync). Editable exactly like
 * a closed-trade card; once a trade closes it drops out of here on the next
 * refresh and its annotations reappear on the resulting closed-trade card.
 */
export function OpenTradesStrip({ positions }: { positions: PositionItem[] }) {
  if (positions.length === 0) return null

  return (
    <div className="space-y-3">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
        Open now ({positions.length})
      </h3>
      {positions.map((p) => (
        <OpenTradeCard key={p.position_id} position={p} />
      ))}
    </div>
  )
}
