import type { AnalyticsPerformanceResponse } from '../../types/analytics'
import { SectionCard, Sparkline } from '../research/primitives'
import { OpsMetric, OpsUnavailable } from '../operations/primitives'
import { formatPercent, formatUsd } from '../../lib/format'

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}

function tone(v: number): 'positive' | 'negative' | 'neutral' {
  return v > 0 ? 'positive' : v < 0 ? 'negative' : 'neutral'
}

function holdTime(mins: number): string {
  if (!Number.isFinite(mins) || mins <= 0) return '—'
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = Math.floor(mins % 60)
  return d > 0 ? `${d}d ${h}h ${m}m` : `${h}h ${m}m`
}

/** Horizontal P&L bar row — width encodes |net_profit| against the row max. */
function PnlBar({ label, value, max, sub }: { label: string; value: number; max: number; sub?: string }) {
  const pct = max > 0 ? (Math.abs(value) / max) * 100 : 0
  return (
    <div className="flex items-center gap-2 py-1 text-[11px]">
      <span className="w-24 shrink-0 truncate font-mono text-secondary" title={label}>{label}</span>
      <div className="relative h-3 flex-1 rounded bg-surface-elevated/40">
        <div
          className={`absolute inset-y-0 rounded ${value >= 0 ? 'bg-positive/50 left-1/2' : 'bg-negative/50 right-1/2'}`}
          style={{ width: `${pct / 2}%` }}
        />
        <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
      </div>
      <span className={`w-24 shrink-0 text-right font-mono tabular-nums ${value > 0 ? 'text-positive' : value < 0 ? 'text-negative' : 'text-secondary'}`}>
        {signedUsd(value)}
      </span>
      {sub ? <span className="w-14 shrink-0 text-right font-mono text-muted">{sub}</span> : null}
    </div>
  )
}

export function AnalyticsView({ data }: { data: AnalyticsPerformanceResponse }) {
  const m = data.metrics
  const pr = data.period_returns

  if (data.matched_trades === 0) {
    return (
      <SectionCard title="Performance">
        <OpsUnavailable>
          No closed trades match the current filters. Adjust the account, symbol
          or date range above.
        </OpsUnavailable>
      </SectionCard>
    )
  }

  const balance = data.official_balance ?? m.final_balance
  const symMax = Math.max(1, ...data.symbol_breakdown.map((r) => Math.abs(r.net_profit)))
  const tagMax = Math.max(1, ...data.tag_breakdown.map((r) => Math.abs(r.net_profit)))
  const dayMax = Math.max(1, ...data.daily_pnl.map((d) => Math.abs(d.net_profit)))

  const scores = [
    { label: 'Profitability', v: clamp(50 + m.gain_pct * 2) },
    { label: 'Win rate', v: clamp(m.win_rate) },
    { label: 'Risk / reward', v: clamp(m.profit_factor * 25) },
    { label: 'Capital protection', v: clamp(100 - m.max_drawdown_pct * 3) },
    { label: 'Consistency (SQN)', v: clamp(m.sqn * 25) },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <OpsMetric
          label={data.official_balance != null ? 'Account balance (broker)' : 'Account balance (derived)'}
          value={formatUsd(balance)}
          sub={`${m.gain_pct >= 0 ? '+' : ''}${formatPercent(m.gain_pct)} · ${signedUsd(m.total_net_pnl)}`}
          tone={tone(m.total_net_pnl)}
        />
        <OpsMetric
          label="Profit factor"
          value={m.profit_factor.toFixed(2)}
          sub={`W ${formatUsd(m.total_gross_profit)} · L ${formatUsd(m.total_gross_loss)}`}
        />
        <OpsMetric
          label="Max drawdown"
          value={formatPercent(m.max_drawdown_pct)}
          sub={`peak ${formatUsd(m.peak_balance)} · ${formatUsd(m.max_drawdown_usd)}`}
          tone={m.max_drawdown_pct >= 10 ? 'negative' : m.max_drawdown_pct >= 5 ? 'warning' : 'neutral'}
        />
        <OpsMetric
          label="Win rate"
          value={formatPercent(m.win_rate)}
          sub={`${m.winning_trades}W / ${m.losing_trades}L · ${m.total_trades} total`}
          tone={m.win_rate >= 50 ? 'positive' : 'neutral'}
        />
        <OpsMetric label="System quality (SQN)" value={m.sqn.toFixed(2)} sub={m.sqn > 2.5 ? 'excellent' : m.sqn > 1.5 ? 'good' : m.sqn > 0 ? 'average' : 'negative edge'} tone={tone(m.sqn)} />
        <OpsMetric label="Expectancy / trade" value={signedUsd(m.expectancy)} sub={`avg W ${formatUsd(m.avg_win)} · avg L ${formatUsd(m.avg_loss)}`} tone={tone(m.expectancy)} />
        <OpsMetric label="Avg holding time" value={holdTime(m.avg_duration_minutes)} sub="per closed trade" />
        <OpsMetric
          label="Best / worst trade"
          value={`${signedUsd(m.best_trade)} / ${signedUsd(m.worst_trade)}`}
          sub={`W/L ratio ${m.win_loss_ratio.toFixed(2)}`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <SectionCard
          title="Account balance curve"
          action={
            <span className="font-mono text-[11px] text-muted">
              {data.equity_curve.length} pts{data.equity_curve_sampled ? ' · sampled' : ''}
            </span>
          }
        >
          {data.equity_curve.length < 2 ? (
            <OpsUnavailable>Not enough closed trades to plot a curve.</OpsUnavailable>
          ) : (
            <div className="text-primary">
              <Sparkline points={data.equity_curve.map((p) => ({ time: p.time, equity: p.equity }))} />
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[11px]">
                <span className="text-muted">Total P&L <span className={m.total_net_pnl >= 0 ? 'text-positive' : 'text-negative'}>{signedUsd(m.total_net_pnl)}</span></span>
                <span className="text-muted">Balance <span className="text-primary">{formatUsd(balance)}</span></span>
                <span className="text-muted">Peak <span className="text-primary">{formatUsd(m.peak_balance)}</span></span>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Period returns">
          <div className="grid grid-cols-2 gap-2">
            <PeriodCell label="Avg daily" pct={pr.avg_daily_pct} />
            <PeriodCell label="This week" pct={pr.weekly_pct} usd={pr.weekly_pnl} />
            <PeriodCell label="This month" pct={pr.monthly_pct} usd={pr.monthly_pnl} />
            <PeriodCell label="Annualized" pct={pr.annualized_pct} />
          </div>
          <p className="mt-2 text-[10px] text-muted">Weekly / monthly windows are relative to now (matches the legacy page).</p>
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Net P&L by symbol">
          {data.symbol_breakdown.length === 0 ? (
            <OpsUnavailable>No symbols in range.</OpsUnavailable>
          ) : (
            <div>
              {data.symbol_breakdown.map((r) => (
                <PnlBar key={r.symbol} label={r.symbol} value={r.net_profit} max={symMax} sub={`${r.trades}t ${r.win_rate.toFixed(0)}%`} />
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="Net P&L by strategy tag">
          {data.tag_breakdown.length === 0 ? (
            <OpsUnavailable>No tagged trades in range.</OpsUnavailable>
          ) : (
            <div>
              {data.tag_breakdown.map((r) => (
                <PnlBar key={r.setup_tag} label={r.setup_tag} value={r.net_profit} max={tagMax} sub={`${r.trades}t`} />
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <SectionCard title="Direction split">
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <DirCell label="Long" s={m.long_stats} />
            <DirCell label="Short" s={m.short_stats} />
          </div>
        </SectionCard>

        <SectionCard title="Performance index">
          <div className="space-y-1.5">
            {scores.map((s) => (
              <div key={s.label} className="flex items-center gap-2 text-[11px]">
                <span className="w-32 shrink-0 text-secondary">{s.label}</span>
                <div className="h-2 flex-1 rounded bg-surface-elevated/40">
                  <div className="h-2 rounded bg-accent/50" style={{ width: `${s.v}%` }} />
                </div>
                <span className="w-8 shrink-0 text-right font-mono tabular-nums text-muted">{s.v.toFixed(0)}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] text-muted">Presentation-only 0–100 scores derived from the metrics above (the legacy page draws these as a radar).</p>
        </SectionCard>
      </div>

      <SectionCard
        title="Daily P&L"
        action={<span className="font-mono text-[11px] text-muted">{data.daily_pnl.length} trading days</span>}
      >
        {data.daily_pnl.length === 0 ? (
          <OpsUnavailable>No daily P&L in range.</OpsUnavailable>
        ) : (
          <div className="overflow-x-auto">
            <div className="flex min-w-full items-end gap-0.5" style={{ height: 96 }}>
              {data.daily_pnl.map((d) => {
                const h = (Math.abs(d.net_profit) / dayMax) * 44
                return (
                  <div key={d.date} className="flex flex-1 flex-col items-center justify-center" style={{ minWidth: 6 }} title={`${d.date}: ${signedUsd(d.net_profit)} (${d.trades}t)`}>
                    <div className="flex h-11 w-full items-end justify-center">
                      {d.net_profit >= 0 ? <div className="w-full bg-positive/60" style={{ height: Math.max(1, h) }} /> : null}
                    </div>
                    <div className="h-px w-full bg-border" />
                    <div className="flex h-11 w-full items-start justify-center">
                      {d.net_profit < 0 ? <div className="w-full bg-negative/60" style={{ height: Math.max(1, h) }} /> : null}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

function clamp(v: number): number {
  return Math.max(0, Math.min(100, v))
}

function PeriodCell({ label, pct, usd }: { label: string; pct: number; usd?: number }) {
  const t = pct > 0 ? 'text-positive' : pct < 0 ? 'text-negative' : 'text-secondary'
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-0.5 font-mono text-sm tabular-nums ${t}`}>{pct >= 0 ? '+' : ''}{pct.toFixed(2)}%</p>
      {usd != null ? <p className="font-mono text-[10px] text-muted">{signedUsd(usd)}</p> : null}
    </div>
  )
}

function DirCell({ label, s }: { label: string; s: { trades: number; win_rate: number; pnl: number } }) {
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-0.5 font-mono text-sm tabular-nums ${s.pnl > 0 ? 'text-positive' : s.pnl < 0 ? 'text-negative' : 'text-secondary'}`}>
        {signedUsd(s.pnl)}
      </p>
      <p className="font-mono text-[10px] text-muted">{s.trades} trades · {s.win_rate.toFixed(1)}% win</p>
    </div>
  )
}
