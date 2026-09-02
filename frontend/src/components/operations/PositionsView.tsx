import { Link } from 'react-router-dom'
import type { PositionItem, PositionsResponse } from '../../types/positions'
import { OpsMetric, OpsStatusTag, OpsUnavailable, SectionCard } from './primitives'
import { formatLots, formatPrice, formatUsd, timeAgo } from '../../lib/format'

function rTone(r: string): 'positive' | 'negative' | 'neutral' {
  if (r === 'N/A' || !r) return 'neutral'
  return r.trim().startsWith('-') ? 'negative' : 'positive'
}

function PnlCell({ value }: { value: number }) {
  return (
    <span
      className={`font-mono tabular-nums ${
        value > 0 ? 'text-positive' : value < 0 ? 'text-negative' : 'text-secondary'
      }`}
    >
      {value > 0 ? '+' : ''}
      {formatUsd(value).replace('$', '')}
    </span>
  )
}

function Card({ p }: { p: PositionItem }) {
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-3 py-2.5">
      <div className="flex items-center justify-between">
        <span className="font-mono font-semibold text-primary">{p.symbol}</span>
        <OpsStatusTag
          value={p.direction}
          tone={p.direction.includes('BUY') || p.direction.includes('LONG') ? 'positive' : 'negative'}
          size="sm"
        />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1.5 text-[11px]">
        <div><span className="text-muted">Size</span><br /><span className="font-mono text-primary">{formatLots(p.volume)}</span></div>
        <div><span className="text-muted">Entry</span><br /><span className="font-mono text-primary">{formatPrice(p.entry_price)}</span></div>
        <div><span className="text-muted">Current</span><br /><span className="font-mono text-primary">{formatPrice(p.current_price)}</span></div>
        <div><span className="text-muted">P&L</span><br /><PnlCell value={p.floating_pnl} /></div>
        <div><span className="text-muted">R</span><br /><span className={`font-mono ${rTone(p.unrealized_r) === 'negative' ? 'text-negative' : rTone(p.unrealized_r) === 'positive' ? 'text-positive' : 'text-secondary'}`}>{p.unrealized_r}</span></div>
        <div><span className="text-muted">Account</span><br /><span className="font-mono text-secondary">{p.account_id}</span></div>
        <div><span className="text-muted">MAE</span><br /><span className="font-mono text-secondary">{p.mae}</span></div>
        <div><span className="text-muted">MFE</span><br /><span className="font-mono text-secondary">{p.mfe}</span></div>
        <div><span className="text-muted">SL / TP</span><br /><span className="font-mono text-secondary">{formatPrice(p.sl)} / {formatPrice(p.tp)}</span></div>
      </div>
      <div className="mt-2 flex gap-3 text-[11px]">
        <Link to={`/workspace/market?symbol=${encodeURIComponent(p.symbol)}`} className="text-secondary hover:text-primary">Market →</Link>
        <Link to={`/workspace/risk?symbol=${encodeURIComponent(p.symbol)}`} className="text-secondary hover:text-primary">Risk →</Link>
      </div>
    </div>
  )
}

export function PositionsSummary({ data }: { data: PositionsResponse }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <OpsMetric label="Open positions" value={data.total_open} />
      <OpsMetric
        label="Total floating P&L"
        value={`${data.total_floating_pnl >= 0 ? '+' : ''}${formatUsd(data.total_floating_pnl).replace('$', '')}`}
        tone={data.total_floating_pnl > 0 ? 'positive' : data.total_floating_pnl < 0 ? 'negative' : 'neutral'}
      />
      <OpsMetric label="Updated" value={timeAgo(data.timestamp) ?? '—'} />
      <OpsMetric label="Transmission" value={<OpsStatusTag value="BLOCKED" tone="negative" size="sm" />} />
    </div>
  )
}

/**
 * Full read-only positions table (desktop) / cards (mobile). Every field is a
 * `/api/positions` value — R / MAE / MFE come pre-computed from the backend.
 * No close / modify / reverse control exists.
 */
export function PositionsView({ data }: { data: PositionsResponse }) {
  if (data.positions.length === 0) {
    return (
      <SectionCard title="Open positions">
        <OpsUnavailable>
          No open positions. (The positions endpoint responded — this is an empty
          book, not an error.)
        </OpsUnavailable>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      title="Open positions"
      action={<span className="font-mono text-[11px] text-muted">{data.positions.length} open</span>}
    >
      {/* desktop */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-xs">
          <thead className="border-b border-border text-muted">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Symbol</th>
              <th className="px-2 py-1.5 text-left font-medium">Side</th>
              <th className="px-2 py-1.5 text-right font-medium">Size</th>
              <th className="px-2 py-1.5 text-right font-medium">Entry</th>
              <th className="px-2 py-1.5 text-right font-medium">Current</th>
              <th className="px-2 py-1.5 text-right font-medium">SL / TP</th>
              <th className="px-2 py-1.5 text-right font-medium">P&L</th>
              <th className="px-2 py-1.5 text-right font-medium">R</th>
              <th className="px-2 py-1.5 text-right font-medium">MAE</th>
              <th className="px-2 py-1.5 text-right font-medium">MFE</th>
              <th className="px-2 py-1.5 text-left font-medium">Account</th>
              <th className="px-2 py-1.5" />
            </tr>
          </thead>
          <tbody>
            {data.positions.map((p) => (
              <tr key={p.position_id} className="border-b border-border-subtle/60">
                <td className="px-2 py-1.5 font-mono font-semibold text-primary">{p.symbol}</td>
                <td className="px-2 py-1.5">
                  <span className={`font-mono ${p.direction.includes('BUY') || p.direction.includes('LONG') ? 'text-positive' : 'text-negative'}`}>
                    {p.direction}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right font-mono tabular-nums text-secondary">{formatLots(p.volume)}</td>
                <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">{formatPrice(p.entry_price)}</td>
                <td className="px-2 py-1.5 text-right font-mono tabular-nums text-primary">{formatPrice(p.current_price)}</td>
                <td className="px-2 py-1.5 text-right font-mono tabular-nums text-muted">
                  {formatPrice(p.sl)} / {formatPrice(p.tp)}
                </td>
                <td className="px-2 py-1.5 text-right"><PnlCell value={p.floating_pnl} /></td>
                <td className={`px-2 py-1.5 text-right font-mono tabular-nums ${rTone(p.unrealized_r) === 'negative' ? 'text-negative' : rTone(p.unrealized_r) === 'positive' ? 'text-positive' : 'text-secondary'}`}>
                  {p.unrealized_r}
                </td>
                <td className="px-2 py-1.5 text-right font-mono tabular-nums text-muted">{p.mae}</td>
                <td className="px-2 py-1.5 text-right font-mono tabular-nums text-muted">{p.mfe}</td>
                <td className="px-2 py-1.5 font-mono text-secondary">{p.account_id}</td>
                <td className="px-2 py-1.5 whitespace-nowrap text-right">
                  <Link to={`/workspace/market?symbol=${encodeURIComponent(p.symbol)}`} className="text-[11px] text-secondary hover:text-primary">Market</Link>
                  <span className="text-muted"> · </span>
                  <Link to={`/workspace/risk?symbol=${encodeURIComponent(p.symbol)}`} className="text-[11px] text-secondary hover:text-primary">Risk</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* mobile */}
      <div className="space-y-2 md:hidden">
        {data.positions.map((p) => (
          <Card key={p.position_id} p={p} />
        ))}
      </div>

      <p className="mt-3 text-[11px] text-muted">
        Read-only operational state — no close / modify / reverse action exists.
        R, MAE and MFE are computed by the backend. A per-position detail
        endpoint is not exposed by the current API.
      </p>
    </SectionCard>
  )
}
