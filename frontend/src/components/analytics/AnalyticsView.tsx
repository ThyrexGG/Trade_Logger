import type { AnalyticsPerformanceResponse } from '../../types/analytics'
import { SectionCard, Sparkline } from '../research/primitives'
import { OpsMetric, OpsUnavailable } from '../operations/primitives'
import { ColorLegend } from '../common/Sentiment'
import { InfoTip } from '../common/InfoTip'
import { formatPercent, formatUsd } from '../../lib/format'
import { MonthlyCalendar } from './MonthlyCalendar'
import { RadarChart } from './RadarChart'
import { SplitBar } from './SplitBar'

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
  const initialBalance = data.filters_applied.initial_balance || 10000
  const symMax = Math.max(1, ...data.symbol_breakdown.map((r) => Math.abs(r.net_profit)))
  const tagMax = Math.max(1, ...data.tag_breakdown.map((r) => Math.abs(r.net_profit)))

  const scores = [
    { label: 'Profitability', v: clamp(50 + m.gain_pct * 2) },
    { label: 'Win rate', v: clamp(m.win_rate) },
    { label: 'Risk / reward', v: clamp(m.profit_factor * 25) },
    { label: 'Capital protection', v: clamp(100 - m.max_drawdown_pct * 3) },
    { label: 'Consistency', v: clamp(m.sqn * 25) },
  ]
  const longN = m.long_stats.trades
  const shortN = m.short_stats.trades

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
        <OpsMetric label={<InfoTip text="System Quality Number — expectancy ÷ std-dev of results, ×√N. <1 hard to trade, 1.6–2 good, 2.5+ excellent.">System quality (SQN)</InfoTip>} value={m.sqn.toFixed(2)} sub={m.sqn > 2.5 ? 'excellent' : m.sqn > 1.5 ? 'good' : m.sqn > 0 ? 'average' : 'negative edge'} tone={tone(m.sqn)} />
        <OpsMetric label={<InfoTip text="Average profit (or loss) per trade in account currency. Positive means the strategy makes money on average.">Expectancy / trade</InfoTip>} value={signedUsd(m.expectancy)} sub={`avg W ${formatUsd(m.avg_win)} · avg L ${formatUsd(m.avg_loss)}`} tone={tone(m.expectancy)} />
        <OpsMetric label="Avg holding time" value={holdTime(m.avg_duration_minutes)} sub="per closed trade" />
        <OpsMetric
          label="Best / worst trade"
          value={`${signedUsd(m.best_trade)} / ${signedUsd(m.worst_trade)}`}
          sub={`W/L ratio ${m.win_loss_ratio.toFixed(2)}`}
        />
      </div>

      <SectionCard title="Calendar" info="Daily net P&L on a month grid. Green = up day, red = down. Click any day to see the trades that closed on it. The summary chips are that month's totals.">
        <MonthlyCalendar
          daily={data.daily_pnl}
          initialBalance={initialBalance}
          account={data.filters_applied.account}
          symbols={data.filters_applied.symbols}
        />
      </SectionCard>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <SectionCard
          title="Account balance curve"
          info="Equity over time, one point per closed trade. Below it: average win vs average loss, and the long/short trade split."
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
              <div className="mt-3 space-y-2 border-t border-border-subtle pt-3">
                <SplitBar
                  leftLabel="Avg win"
                  rightLabel="Avg loss"
                  left={Math.abs(m.avg_win)}
                  right={Math.abs(m.avg_loss)}
                  leftValue={signedUsd(m.avg_win)}
                  rightValue={signedUsd(-Math.abs(m.avg_loss))}
                />
                <SplitBar
                  leftLabel="Long"
                  rightLabel="Short"
                  left={longN}
                  right={shortN}
                  leftValue={`${longN}`}
                  rightValue={`${shortN}`}
                />
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Period returns" info="Return over rolling windows relative to now: average day, this week, this month, and the annualised figure. Percentages are of the starting balance.">
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
        <SectionCard title="Net P&L by symbol" info="Which instruments made or lost money over the filtered period, with trade count and win rate. Bars extend right for profit, left for loss.">
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

        <SectionCard title="Net P&L by strategy tag" info="Same P&L breakdown but grouped by the setup tag you assigned in the journal. Untagged trades are grouped together.">
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
        <SectionCard title="Direction split" info="Long vs short: how many trades, win rate and net P&L on each side. A big skew can mean a directional bias worth examining.">
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <DirCell label="Long" s={m.long_stats} />
            <DirCell label="Short" s={m.short_stats} />
          </div>
        </SectionCard>

        <SectionCard title="Performance index" info="Five 0-100 presentation scores derived from the metrics above (profitability, win rate, risk-reward, capital protection, consistency). Not a grade - a shape to eyeball. Green >=60, red <=40.">
          <div className="text-accent">
            <RadarChart axes={scores.map((s) => ({ label: s.label, value: s.v }))} />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-muted sm:grid-cols-3">
            {scores.map((s) => (
              <span key={s.label} className="tabular-nums">
                {s.label}{' '}
                <span className={s.v >= 60 ? 'text-positive' : s.v <= 40 ? 'text-negative' : 'text-secondary'}>
                  {s.v.toFixed(0)}
                </span>
              </span>
            ))}
          </div>
          <p className="mt-1 text-[10px] text-muted">
            Presentation-only 0–100 index scores. <span className="text-positive">60+ green</span> ·{' '}
            <span className="text-negative">40− red</span>.
          </p>
        </SectionCard>
      </div>

      <ColorLegend
        className="border-t border-border-subtle pt-2"
        items={[
          { tone: 'up', label: 'profit / above target' },
          { tone: 'down', label: 'loss / below target' },
          { tone: 'flat', label: 'flat / n-a' },
        ]}
      />
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
