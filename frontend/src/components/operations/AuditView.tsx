import { Fragment, useMemo, useState } from 'react'
import type { AuditOrderItem, AuditResponse } from '../../types/operations'
import { HashChip, OpsMetric, OpsStatusTag, OpsUnavailable, SectionCard, opsTone } from './primitives'
import { timeAgo } from '../../lib/format'

const PAGE = 60

function CountBar({ counts, title }: { counts: Record<string, number>; title: string }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1])
  return (
    <div>
      <p className="mb-1 text-[10px] uppercase tracking-wider text-muted">{title}</p>
      <div className="flex h-2 w-full overflow-hidden rounded bg-surface-elevated">
        {entries.map(([k, v]) => (
          <span
            key={k}
            className={
              opsTone(k) === 'negative' ? 'bg-negative/60'
                : opsTone(k) === 'warning' ? 'bg-warning/60'
                : opsTone(k) === 'positive' ? 'bg-positive/60'
                : opsTone(k) === 'info' ? 'bg-info/60' : 'bg-neutral/60'
            }
            style={{ width: `${(v / total) * 100}%` }}
            title={`${k}: ${v}`}
          />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-muted">
        {entries.map(([k, v]) => <span key={k}>{k} {v}</span>)}
      </div>
    </div>
  )
}

export function AuditSummary({ data }: { data: AuditResponse }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <OpsMetric label="Audit records" value={data.total_records.toLocaleString()} sub={`${data.total_returned} shown`} />
        <OpsMetric label="Latest event" value={timeAgo(data.latest_event_at ?? undefined) ?? '—'} />
        <OpsMetric label="Decision ledger" value={data.decision_ledger_records} sub="research-decision audit rows" />
        <OpsMetric label="Transmission" value={<OpsStatusTag value="BLOCKED" tone="negative" size="sm" />} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <CountBar counts={data.state_counts} title="By state" />
        <CountBar counts={data.mode_counts} title="By mode" />
      </div>
    </div>
  )
}

function Detail({ e }: { e: AuditOrderItem }) {
  const rows: Array<[string, string | number | null]> = [
    ['Signal', e.signal_id],
    ['Requested qty', e.requested_quantity],
    ['Requested entry', e.requested_entry],
    ['Stop / target', e.stop_loss !== null || e.take_profit !== null ? `${e.stop_loss ?? '—'} / ${e.take_profit ?? '—'}` : null],
    ['Broker', e.broker],
    ['Reconciliation', e.reconciliation_status],
    ['Created', e.created_at],
    ['Submitted', e.submitted_at],
    ['Resolved', e.resolved_at],
    ['Filled', e.filled_at],
    ['Latency (ms)', e.execution_latency_ms],
    ['Reject reason', e.reject_reason],
    ['Last error', e.last_error],
  ]
  return (
    <tr className="bg-surface-elevated/40">
      <td colSpan={6} className="px-3 py-2">
        <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
          {rows.filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => (
            <div key={k} className="flex gap-2 text-[11px]">
              <dt className="shrink-0 text-muted">{k}</dt>
              <dd className="break-all font-mono text-secondary">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </td>
    </tr>
  )
}

/**
 * Read-only operational execution audit trail — the `execution_orders` table.
 * Immutable historical records; each keeps its authoritative mode / state.
 * Client-side filtering only. No acknowledge / resolve / delete control.
 */
export function AuditView({ data }: { data: AuditResponse }) {
  const [state, setState] = useState('all')
  const [mode, setMode] = useState('all')
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE)
  const [open, setOpen] = useState<string | null>(null)

  const states = useMemo(() => Object.keys(data.state_counts).sort(), [data.state_counts])
  const modes = useMemo(() => Object.keys(data.mode_counts).sort(), [data.mode_counts])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return data.events.filter((e) => {
      if (state !== 'all' && e.state !== state) return false
      if (mode !== 'all' && e.mode !== mode) return false
      if (
        q &&
        !(e.symbol ?? '').toLowerCase().includes(q) &&
        !e.execution_id.toLowerCase().includes(q) &&
        !(e.reject_reason ?? '').toLowerCase().includes(q) &&
        !(e.signal_id ?? '').toLowerCase().includes(q)
      ) {
        return false
      }
      return true
    })
  }, [data.events, state, mode, query])

  const shown = filtered.slice(0, limit)

  if (data.events.length === 0) {
    return (
      <SectionCard title="Execution audit trail">
        <OpsUnavailable>
          No audit events — the <code>execution_orders</code> table is empty.
        </OpsUnavailable>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      title="Execution audit trail"
      action={<span className="font-mono text-[11px] text-muted">{data.source} · read-only</span>}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="aud-q">Search audit</label>
        <input
          id="aud-q"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setLimit(PAGE) }}
          placeholder="Symbol, id, reason…"
          autoComplete="off"
          className="w-48 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <select value={state} onChange={(e) => { setState(e.target.value); setLimit(PAGE) }} className="rounded border border-border bg-background px-2 py-1 text-xs text-primary" aria-label="Filter by state">
          <option value="all">All states</option>
          {states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={mode} onChange={(e) => { setMode(e.target.value); setLimit(PAGE) }} className="rounded border border-border bg-background px-2 py-1 text-xs text-primary" aria-label="Filter by mode">
          <option value="all">All modes</option>
          {modes.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <span className="ml-auto font-mono text-[11px] text-muted">{filtered.length} / {data.events.length}</span>
      </div>

      {filtered.length === 0 ? (
        <OpsUnavailable>No events match the current filter.</OpsUnavailable>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead className="border-b border-border text-muted">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium">Created</th>
                <th className="px-2 py-1.5 text-left font-medium">Symbol</th>
                <th className="px-2 py-1.5 text-left font-medium">Side</th>
                <th className="px-2 py-1.5 text-left font-medium">Mode</th>
                <th className="px-2 py-1.5 text-left font-medium">State</th>
                <th className="px-2 py-1.5 text-left font-medium">ID</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((e) => (
                <Fragment key={e.execution_id}>
                  <tr
                    tabIndex={0}
                    onClick={() => setOpen(open === e.execution_id ? null : e.execution_id)}
                    onKeyDown={(ev) => {
                      if (ev.key === 'Enter' || ev.key === ' ') {
                        ev.preventDefault()
                        setOpen(open === e.execution_id ? null : e.execution_id)
                      }
                    }}
                    className="cursor-pointer border-b border-border-subtle/60 hover:bg-surface-hover focus:bg-surface-hover focus:outline-none"
                  >
                    <td className="px-2 py-1.5 font-mono text-secondary">{(e.created_at ?? '').slice(0, 16).replace('T', ' ')}</td>
                    <td className="px-2 py-1.5 font-mono font-semibold text-primary">{e.symbol ?? '—'}</td>
                    <td className={`px-2 py-1.5 font-mono ${e.side === 'BUY' ? 'text-positive' : e.side === 'SELL' ? 'text-negative' : 'text-secondary'}`}>{e.side ?? '—'}</td>
                    <td className="px-2 py-1.5"><OpsStatusTag value={e.mode ?? '—'} size="sm" /></td>
                    <td className="px-2 py-1.5"><OpsStatusTag value={e.state ?? '—'} size="sm" /></td>
                    <td className="px-2 py-1.5"><HashChip value={e.execution_id} chars={12} /></td>
                  </tr>
                  {open === e.execution_id ? <Detail e={e} /> : null}
                </Fragment>
              ))}
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
        Source: <code>execution_orders</code> — the operational record of
        execution attempts. Each row keeps its authoritative mode (PAPER /
        SHADOW / LIVE) and state; historical LIVE rows are blocked or
        reconciled-not-executed attempts. Read-only — audit records cannot be
        acknowledged, resolved or deleted here.
        {data.decision_ledger_records === 0
          ? ' The research decision-audit ledger is currently empty (0 records).'
          : ` The research decision-audit ledger holds ${data.decision_ledger_records} records (not shown here — see Evidence Governance).`}
        {' '}Actor / severity fields are not part of this table.
      </p>
    </SectionCard>
  )
}
