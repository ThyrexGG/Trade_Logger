import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDayTrades } from '../../api/analytics'
import type { DayTrade } from '../../types/analytics'
import { formatSignedAmount } from '../../lib/format'
import { prettyDate } from './homeMath'

function fmtTime(iso: string): string {
  return iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'
}

/** The trades behind one heatmap square, opened by clicking it. */
export function DayTradesPanel({ iso, account, onClose }: { iso: string; account: string; onClose: () => void }) {
  const [trades, setTrades] = useState<DayTrade[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ref.current?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
  }, [iso])

  useEffect(() => {
    const ctl = new AbortController()
    setTrades(null)
    setError(null)
    getDayTrades(iso, { account }, ctl.signal)
      .then((r) => setTrades(r.trades))
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load that day.')
      })
    return () => ctl.abort()
  }, [iso, account])

  const total = trades?.reduce((s, t) => s + t.net_profit, 0) ?? 0

  return (
    <div ref={ref} className="tl-day-panel">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-primary">{prettyDate(iso, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>
          {trades ? (
            <div className={`font-mono text-xs ${total >= 0 ? 'text-positive' : 'text-negative'}`}>
              {formatSignedAmount(total)} · {trades.length} trade{trades.length === 1 ? '' : 's'}
            </div>
          ) : null}
        </div>
        <button type="button" onClick={onClose} className="rounded border border-border px-2 py-0.5 text-xs text-secondary hover:bg-surface-hover">
          Close
        </button>
      </div>

      {error ? (
        <p className="mt-3 text-xs text-negative">{error}</p>
      ) : !trades ? (
        <div className="mt-3 space-y-2">
          {[0, 1].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded-md bg-surface-elevated" />
          ))}
        </div>
      ) : (
        <ul className="mt-3 divide-y divide-border-subtle">
          {trades.map((t, i) => (
            <li key={t.trade_id} className="tl-day-row flex items-center gap-3 py-2 text-sm" style={{ animationDelay: `${i * 45}ms` }}>
              <span className={`w-12 shrink-0 text-[11px] font-semibold uppercase ${t.direction.toUpperCase().startsWith('B') || t.direction.toUpperCase() === 'LONG' ? 'text-positive' : 'text-negative'}`}>
                {t.direction}
              </span>
              <span className="min-w-0 flex-1 truncate font-medium text-primary">
                {t.symbol}
                {t.setup_tag ? <span className="ml-2 rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] text-secondary">{t.setup_tag}</span> : null}
              </span>
              <span className="hidden font-mono text-xs text-muted sm:inline">
                {fmtTime(t.entry_time)} → {fmtTime(t.exit_time)}
              </span>
              <span className={`w-24 text-right font-mono ${t.net_profit >= 0 ? 'text-positive' : 'text-negative'}`}>{formatSignedAmount(t.net_profit)}</span>
              <Link to={`/workspace/journal?trade=${encodeURIComponent(t.trade_id)}`} className="text-xs text-accent hover:underline">
                Journal
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
