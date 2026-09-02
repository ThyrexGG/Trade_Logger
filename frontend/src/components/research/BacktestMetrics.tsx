import type { BacktestMetricsBlock } from '../../types/research'
import { MetricCard, SectionCard } from './primitives'

function pct(v: number | null, digits = 1): string {
  return v === null || !Number.isFinite(v) ? '—' : `${v.toFixed(digits)}%`
}
function num(v: number | null, digits = 2): string {
  return v === null || !Number.isFinite(v) ? '—' : v.toFixed(digits)
}

function Block({ title, m }: { title: string; m: BacktestMetricsBlock | null }) {
  if (!m) {
    return (
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-secondary">
          {title}
        </p>
        <p className="rounded border border-dashed border-border-subtle px-3 py-3 text-center text-[11px] text-muted">
          No trades in this segment.
        </p>
      </div>
    )
  }
  return (
    <div>
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-secondary">
        {title}
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricCard label="Trades" value={m.total_trades || '—'} />
        <MetricCard label="Win rate" value={pct(m.win_rate_pct)} />
        <MetricCard
          label="Profit factor"
          value={num(m.profit_factor)}
          tone={
            m.profit_factor === null
              ? undefined
              : m.profit_factor >= 1
                ? 'positive'
                : 'negative'
          }
        />
        <MetricCard
          label="Max drawdown"
          value={pct(m.max_drawdown_pct)}
          tone={m.max_drawdown_pct === null ? undefined : 'negative'}
        />
      </div>
    </div>
  )
}

/**
 * Backtest performance metrics — overall plus explicit in-sample /
 * out-of-sample blocks. Every value is the authoritative backtester output;
 * nothing is derived here. Missing metrics show "—", never 0.
 */
export function BacktestMetrics({
  overall,
  is,
  oos,
  finalCapital,
}: {
  overall: BacktestMetricsBlock | null
  is: BacktestMetricsBlock | null
  oos: BacktestMetricsBlock | null
  finalCapital: string | null
}) {
  return (
    <SectionCard
      title="Performance metrics"
      action={
        finalCapital ? (
          <span className="font-mono text-xs text-secondary">
            Final capital {finalCapital}
          </span>
        ) : null
      }
    >
      <div className="space-y-4">
        <Block title="Overall" m={overall} />
        <div className="grid gap-4 border-t border-border-subtle pt-3 lg:grid-cols-2">
          <Block title="In-sample (train)" m={is} />
          <Block title="Out-of-sample (test)" m={oos} />
        </div>
      </div>
      <p className="mt-3 text-[11px] text-muted">
        In-sample and out-of-sample are kept separate — they are never combined
        into a single record. Sharpe / Sortino / average win / average loss /
        exposure are not exposed by the current backtester API.
      </p>
    </SectionCard>
  )
}
