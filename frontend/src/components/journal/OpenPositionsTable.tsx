import { Fragment, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { PositionItem, PositionUpdateRequest } from '../../types/positions'
import { formatSignedAmount } from '../../lib/format'
import { patchPosition } from '../../api/positions'
import { ChartSnapshot } from './ChartSnapshot'
import { ScreenshotStrip, type ScreenshotStripHandle } from './ScreenshotStrip'
import { StarRating } from './StarRating'
import { invalidateTagRecord } from './TagRecord'
import { AccountBadge } from '../common/AccountBadge'
import { groupByAccount } from '../../lib/accountLabel'

function Stars({ n }: { n: number | null | undefined }) {
  if (!n || n <= 0) return <span className="text-muted">—</span>
  return <span className="text-warning">{'★'.repeat(Math.min(5, n))}</span>
}

/** Same fold-out annotation editor the closed-trades table uses, pointed at
 * PATCH /api/positions/{id} instead of the journal endpoint. */
function OpenPositionEditor({
  position,
  onCancel,
}: {
  position: PositionItem
  onCancel: () => void
}) {
  const [setupTag, setSetupTag] = useState(position.setup_tag ?? '')
  const [notes, setNotes] = useState(position.notes ?? '')
  const [chartUrl, setChartUrl] = useState(position.chart_snapshot_url ?? '')
  const [rating, setRating] = useState<number>(position.rating ?? 0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const stripRef = useRef<ScreenshotStripHandle>(null)

  const norm = (s: string) => s.trim()
  const dirty =
    norm(setupTag) !== (position.setup_tag ?? '') ||
    notes !== (position.notes ?? '') ||
    norm(chartUrl) !== (position.chart_snapshot_url ?? '') ||
    rating !== (position.rating ?? 0)

  async function save() {
    if (saving || !dirty) return
    setSaving(true)
    setError(null)
    const body: PositionUpdateRequest = {}
    if (norm(setupTag) !== (position.setup_tag ?? '')) body.setup_tag = norm(setupTag)
    if (notes !== (position.notes ?? '')) body.notes = notes
    if (norm(chartUrl) !== (position.chart_snapshot_url ?? '')) body.chart_snapshot_url = norm(chartUrl)
    if (rating !== (position.rating ?? 0)) body.rating = rating
    try {
      await patchPosition(position.position_id, body)
      if ('setup_tag' in body) invalidateTagRecord()
      onCancel()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
      setSaving(false)
    }
  }

  return (
    <div
      className="space-y-2 rounded border border-accent/30 bg-surface-elevated/40 p-3"
      onPaste={(e) => {
        const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith('image/'))
        const file = item?.getAsFile()
        if (file) {
          e.preventDefault()
          stripRef.current?.upload(file)
        }
      }}
    >
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <label className="block text-[11px] text-muted">
          Setup tag
          <input
            value={setupTag}
            onChange={(e) => setSetupTag(e.target.value)}
            disabled={saving}
            maxLength={120}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
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
          {chartUrl.trim() ? (
            <span className="mt-1 block">
              <ChartSnapshot url={chartUrl} />
            </span>
          ) : null}
        </label>
      </div>
      <label className="block text-[11px] text-muted">
        Notes — what's the plan, how it's playing out so far
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
          <ScreenshotStrip ref={stripRef} tradeId={position.position_id} />
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
          Carries over to the closed trade automatically once this position closes
        </span>
      </div>
    </div>
  )
}

/** One account's slice of the table — no per-row Account column since the
 * group heading above it already says which account this is. */
function PositionsTableGroup({
  positions,
  editing,
  setEditing,
}: {
  positions: PositionItem[]
  editing: string | null
  setEditing: (id: string | null) => void
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-accent/30">
      <table className="w-full border-collapse text-[11px]">
        <thead className="border-b border-border text-muted">
          <tr>
            <th className="px-2 py-1.5 text-left font-medium">Status</th>
            <th className="px-2 py-1.5 text-left font-medium">Symbol</th>
            <th className="px-2 py-1.5 text-left font-medium">Dir</th>
            <th className="px-2 py-1.5 text-right font-medium">Vol</th>
            <th className="px-2 py-1.5 text-right font-medium">Entry</th>
            <th className="px-2 py-1.5 text-right font-medium">Current</th>
            <th className="px-2 py-1.5 text-right font-medium">Floating P&L</th>
            <th className="px-2 py-1.5 text-left font-medium">Setup / note</th>
            <th className="px-2 py-1.5 text-left font-medium">Rating</th>
            <th className="px-2 py-1.5 text-right font-medium">Edit</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const isEditing = editing === p.position_id
            return (
              <Fragment key={p.position_id}>
                <tr className={isEditing ? '' : 'border-b border-border-subtle/60'}>
                  <td className="whitespace-nowrap px-2 py-1.5">
                    <span className="inline-flex items-center gap-1.5 font-mono text-accent">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                      </span>
                      OPEN
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    <Link to={`/workspace/market?symbol=${encodeURIComponent(p.symbol)}`} className="font-mono font-semibold text-primary hover:text-accent">
                      {p.symbol}
                    </Link>
                  </td>
                  <td className={`px-2 py-1.5 font-mono ${p.direction.includes('BUY') || p.direction.includes('LONG') ? 'text-positive' : 'text-negative'}`}>
                    {p.direction}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums text-secondary">{p.volume}</td>
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">{p.entry_price}</td>
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">{p.current_price}</td>
                  <td className={`px-2 py-1.5 text-right font-mono tabular-nums ${p.floating_pnl > 0 ? 'text-positive' : p.floating_pnl < 0 ? 'text-negative' : 'text-secondary'}`}>
                    {formatSignedAmount(p.floating_pnl)}
                  </td>
                  <td className="max-w-[16rem] px-2 py-1.5 text-secondary">
                    {p.setup_tag ? <span className="mr-1 rounded bg-surface-elevated px-1 text-[10px] text-muted">{p.setup_tag}</span> : null}
                    {p.notes ?? (p.setup_tag ? '' : <span className="text-muted">—</span>)}
                    {p.screenshot_count ? <span className="ml-1 text-[10px] text-muted">📷 {p.screenshot_count}</span> : null}
                    {p.chart_snapshot_url ? (
                      <span className="ml-1 inline-block align-middle">
                        <ChartSnapshot url={p.chart_snapshot_url} compact />
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-1.5"><Stars n={p.rating} /></td>
                  <td className="px-2 py-1.5 text-right">
                    <button
                      type="button"
                      onClick={() => setEditing(isEditing ? null : p.position_id)}
                      className="rounded border border-border px-1.5 py-0.5 text-[10px] text-secondary hover:border-accent/40 hover:text-accent"
                    >
                      {isEditing ? 'Close' : 'Edit'}
                    </button>
                  </td>
                </tr>
                {isEditing ? (
                  <tr className="border-b border-border-subtle/60 bg-surface-elevated/20">
                    <td colSpan={10} className="p-0">
                      <div className="sticky left-0 w-[calc(100vw-2rem)] p-3 sm:w-auto sm:max-w-3xl">
                        <OpenPositionEditor position={p} onCancel={() => setEditing(null)} />
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
  )
}

/**
 * Compact, foldable table of currently-open trades — the Table-view
 * counterpart to OpenTradesStrip's big feed cards. Same columns as the
 * closed-trades table (JournalView) so the two sit together without a jarring
 * size mismatch; rows expand into the same kind of annotation editor.
 *
 * When more than one account is open at once (viewing "All accounts"), the
 * trades are split into one table per account instead of interleaved with an
 * Account column — easier to scan than picking the right badge out of a
 * shared list.
 */
export function OpenPositionsTable({ positions }: { positions: PositionItem[] }) {
  const [editing, setEditing] = useState<string | null>(null)
  if (positions.length === 0) return null
  const multiAccount = new Set(positions.map((p) => p.account_id)).size > 1

  if (!multiAccount) {
    return (
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Open now ({positions.length})</h3>
        <PositionsTableGroup positions={positions} editing={editing} setEditing={setEditing} />
      </div>
    )
  }

  const groups = groupByAccount(positions)
  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Open now ({positions.length})</h3>
      {groups.map((g) => (
        <div key={g.account} className="space-y-2">
          <h4 className="flex items-center gap-2 text-[11px] font-semibold text-secondary">
            <AccountBadge accountId={g.account} />
            <span className="font-normal text-muted">({g.items.length})</span>
          </h4>
          <PositionsTableGroup positions={g.items} editing={editing} setEditing={setEditing} />
        </div>
      ))}
    </div>
  )
}
