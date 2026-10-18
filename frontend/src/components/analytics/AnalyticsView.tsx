import type { AnalyticsPerformanceResponse } from '../../types/analytics'
import { SectionCard, Sparkline } from '../research/primitives'
import { OpsMetric, OpsUnavailable } from '../operations/primitives'
import { ColorLegend } from '../common/Sentiment'
import { InfoTip } from '../common/InfoTip'
import { formatPercent, formatUsd } from '../../lib/format'
import { InsightsSection } from './InsightsSection'
import { MoneySplitCard, TradingProfileCard } from './AnalyticsBreakdowns'
import { MonthlyCalendar } from './MonthlyCalendar'
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
  // Tags the trader typed themselves — the one-tap rule answers have their own card, and a lone "Untagged" row says nothing.
  const RULE_TAGS = ['untagged', 'by my rules', 'bent my rules', 'rushed']
  const ownTags = data.tag_breakdown.filter((r) => !RULE_TAGS.includes(r.setup_tag.trim().toLowerCase()))

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
      <div className="tl-figures">
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
        <OpsMetric
          label="Avg holding time"
          value={holdTime(m.avg_duration_minutes)}
          sub={data.insights?.open_unknown ? `${data.insights.open_unknown} without an open time left out` : 'per closed trade'}
        />
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

      {data.insights ? <InsightsSection insights={data.insights} /> : null}

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
              <Sparkline
                points={data.equity_curve.map((p) => ({
                  time: p.time,
                  equity: p.equity,
                  netProfit: p.net_profit,
                  symbol: p.symbol,
                }))}
              />
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

        <SectionCard
          title="Period returns"
          info="Return over rolling windows relative to now: average day, this week, this month, and the annualised figure. Percentages are of the starting balance."
          // fill the row's height beside the taller balance curve instead of leaving a hole under the cells
          className="flex flex-col [&>.tl-card-body]:flex [&>.tl-card-body]:flex-1 [&>.tl-card-body]:flex-col"
        >
          <div className="grid flex-1 auto-rows-fr grid-cols-2 gap-2">
            <PeriodCell label="Avg daily" pct={pr.avg_daily_pct} />
            <PeriodCell label="This week" pct={pr.weekly_pct} usd={pr.weekly_pnl} />
            <PeriodCell label="This month" pct={pr.monthly_pct} usd={pr.monthly_pnl} />
            <PeriodCell label="Annualized" pct={pr.annualized_pct} />
          </div>
          <p className="mt-2 text-[10px] text-muted">Weekly / monthly windows are relative to now (matches the legacy page).</p>
        </SectionCard>
      </div>

      <MoneySplitCard
        title="Where you make and lose money"
        info="Net profit or loss per market over the filtered period, split into the markets that are making you money and the ones losing it, with trade count and win rate."
        noun="market"
        rows={data.symbol_breakdown.map((r) => ({ label: r.symbol, net: r.net_profit, trades: r.trades, winRate: r.win_rate }))}
      />

      {ownTags.length ? (
        <MoneySplitCard
          title="Your own tags"
          info="The same split, grouped by tags you typed yourself in the journal. The one-tap answers (By my rules / Bent / Rushed) are in the rules card above; untagged trades are left out here."
          noun="tag"
          rows={ownTags.map((r) => ({ label: r.setup_tag, net: r.net_profit, trades: r.trades }))}
        />
      ) : null}

      <TradingProfileCard scores={scores} long={m.long_stats} short={m.short_stats} />

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
    <div className="flex flex-col justify-center rounded border border-border-subtle bg-surface-elevated/30 px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-1 font-mono text-lg tabular-nums ${t}`}>{pct >= 0 ? '+' : ''}{pct.toFixed(2)}%</p>
      {usd != null ? <p className="font-mono text-[10px] text-muted">{signedUsd(usd)}</p> : null}
    </div>
  )
}

