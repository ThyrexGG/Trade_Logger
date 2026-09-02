import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import type { AlertCondition, AlertItem, AlertsResponse } from '../../types/alerts'
import { createAlert, deleteAlert } from '../../api/alerts'
import { SectionCard } from '../intelligence/primitives'
import { OpsMetric, OpsStatusTag, OpsUnavailable } from '../operations/primitives'
import { formatUsd, parseNumberInput, timeAgo } from '../../lib/format'

const CONDITIONS: { value: AlertCondition; label: string }[] = [
  { value: 'ABOVE', label: 'Rises to / above (≥)' },
  { value: 'BELOW', label: 'Falls to / below (≤)' },
]

export function AlertsSummary({ data }: { data: AlertsResponse }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <OpsMetric label="Total alerts" value={data.total} />
      <OpsMetric label="Active" value={data.active} tone={data.active > 0 ? 'info' : 'neutral'} />
      <OpsMetric label="Triggered" value={data.triggered} tone={data.triggered > 0 ? 'warning' : 'neutral'} />
      <OpsMetric label="Updated" value={timeAgo(data.timestamp) ?? '—'} />
    </div>
  )
}

/**
 * Price-alert create + list. Monitoring only — no order / execution control.
 * Create and delete each fire one request and then `onChanged()` (a single
 * authoritative refetch); there is no optimistic client-side alert state.
 */
export function AlertsPanel({
  data,
  onChanged,
}: {
  data: AlertsResponse
  onChanged: () => void
}) {
  const [symbol, setSymbol] = useState('')
  const [price, setPrice] = useState('')
  const [condition, setCondition] = useState<AlertCondition>('ABOVE')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [rowError, setRowError] = useState<string | null>(null)

  const parsedPrice = useMemo(() => parseNumberInput(price), [price])
  const symbolClean = symbol.trim().toUpperCase()
  const canSubmit =
    !submitting && symbolClean.length > 0 && parsedPrice !== null && parsedPrice > 0

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit || parsedPrice === null) return
    setSubmitting(true)
    setFormError(null)
    setFlash(null)
    try {
      const res = await createAlert({
        symbol: symbolClean,
        target_price: parsedPrice,
        condition,
        notes: notes.trim() || undefined,
      })
      setFlash(
        `Alert set: ${res.alert.symbol} ${res.alert.condition} ${formatUsd(res.alert.target_price)}`,
      )
      setSymbol('')
      setPrice('')
      setNotes('')
      setCondition('ABOVE')
      onChanged()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not create the alert')
    } finally {
      setSubmitting(false)
    }
  }

  async function remove(alert: AlertItem) {
    if (deletingId !== null) return
    setDeletingId(alert.id)
    setRowError(null)
    setFlash(null)
    try {
      await deleteAlert(alert.id)
      setFlash(`Deleted alert #${alert.id} (${alert.symbol})`)
      onChanged()
    } catch (err) {
      setRowError(err instanceof Error ? err.message : `Could not delete alert #${alert.id}`)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <SectionCard title="New price alert">
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1.4fr)]">
            <label className="block text-[11px] text-muted">
              Symbol
              <input
                list="alert-supported-symbols"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                disabled={submitting}
                placeholder="XAUUSD"
                autoComplete="off"
                className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs uppercase text-primary placeholder:text-muted focus:border-accent focus:outline-none"
              />
              <datalist id="alert-supported-symbols">
                {data.supported_symbols.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </label>
            <label className="block text-[11px] text-muted">
              Target price
              <input
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                disabled={submitting}
                inputMode="decimal"
                placeholder="2500.00"
                className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs tabular-nums text-primary placeholder:text-muted focus:border-accent focus:outline-none"
              />
            </label>
            <label className="block text-[11px] text-muted">
              Condition
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value as AlertCondition)}
                disabled={submitting}
                className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
              >
                {CONDITIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="block text-[11px] text-muted">
            Note (optional)
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={submitting}
              maxLength={500}
              placeholder="e.g. 4H resistance / breakout watch"
              className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
            />
          </label>

          {formError ? (
            <p className="rounded border border-negative/30 bg-negative/10 px-2 py-1 text-[11px] text-negative" role="alert">
              {formError}
            </p>
          ) : null}

          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded border border-accent/40 bg-accent/10 px-3 py-1 text-[11px] text-accent disabled:opacity-40"
            >
              {submitting ? 'Setting…' : 'Set alert'}
            </button>
            <span className="font-mono text-[10px] text-muted">
              Notification only · no order is placed
            </span>
          </div>
        </form>
      </SectionCard>

      {flash ? (
        <p className="rounded border border-positive/30 bg-positive/10 px-2 py-1 text-[11px] text-positive" role="status">
          {flash}
        </p>
      ) : null}

      <SectionCard
        title="Your price alerts"
        action={<span className="font-mono text-[11px] text-muted">{data.source} · {data.total}</span>}
      >
        {rowError ? (
          <p className="mb-2 rounded border border-negative/30 bg-negative/10 px-2 py-1 text-[11px] text-negative" role="alert">
            {rowError}
          </p>
        ) : null}

        {data.alerts.length === 0 ? (
          <OpsUnavailable>
            No price alerts yet. Set a target above — the background sync
            daemon checks active alerts against live prices and notifies on a
            cross.
          </OpsUnavailable>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[11px]">
              <thead className="border-b border-border text-muted">
                <tr>
                  <th className="px-2 py-1.5 text-left font-medium">Symbol</th>
                  <th className="px-2 py-1.5 text-left font-medium">Condition</th>
                  <th className="px-2 py-1.5 text-right font-medium">Target</th>
                  <th className="px-2 py-1.5 text-left font-medium">Status</th>
                  <th className="px-2 py-1.5 text-left font-medium">Note</th>
                  <th className="px-2 py-1.5 text-left font-medium">Created</th>
                  <th className="px-2 py-1.5 text-right font-medium" />
                </tr>
              </thead>
              <tbody>
                {data.alerts.map((a) => (
                  <tr key={a.id} className="border-b border-border-subtle/60 align-top">
                    <td className="px-2 py-1.5 font-mono font-semibold text-primary">{a.symbol}</td>
                    <td className="px-2 py-1.5 font-mono text-secondary">
                      {a.condition === 'ABOVE' ? '≥ above' : '≤ below'}
                    </td>
                    <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">
                      {formatUsd(a.target_price)}
                    </td>
                    <td className="px-2 py-1.5">
                      <OpsStatusTag value={a.status} size="sm" />
                    </td>
                    <td className="px-2 py-1.5 max-w-[16rem] text-secondary">
                      {a.notes ?? <span className="text-muted">—</span>}
                    </td>
                    <td className="px-2 py-1.5 font-mono text-muted">
                      {a.created_at ? a.created_at.slice(0, 16).replace('T', ' ') : '—'}
                      {a.status === 'TRIGGERED' && a.triggered_at
                        ? ` · fired ${a.triggered_at.slice(0, 16).replace('T', ' ')}`
                        : ''}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <button
                        type="button"
                        onClick={() => remove(a)}
                        disabled={deletingId !== null}
                        className="rounded border border-border px-1.5 py-0.5 text-[10px] text-secondary hover:border-negative/40 hover:text-negative disabled:opacity-40"
                      >
                        {deletingId === a.id ? 'Deleting…' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-[11px] text-muted">
          Source: <code>price_alerts</code>. <code>id</code>, <code>status</code>,
          <code> created_at</code> and <code>triggered_at</code> are
          server-maintained. Symbols are validated against the canonical registry.
          Alert evaluation and notification dispatch run in the existing
          <code> auto_sync</code> daemon, unchanged. Nothing here places, modifies
          or transmits an order.
        </p>
      </SectionCard>
    </div>
  )
}
