import type { BacktestRunResponse } from '../../types/research'
import { MetricCard, ResearchStatusTag, SectionCard, researchTone } from './primitives'

/**
 * Walk-Forward Optimization summary. The authoritative `run_walk_forward`
 * returns an aggregate stitched-OOS result + a robustness flag + Monte-Carlo;
 * it does not expose a per-window breakdown, which is stated plainly.
 */
export function WfoPanel({ result }: { result: BacktestRunResponse }) {
  const m = result.metrics
  return (
    <SectionCard
      title="Walk-forward optimization"
      action={
        result.wfo_flag ? (
          <ResearchStatusTag
            value={`WFO ${result.wfo_flag}`}
            tone={researchTone(result.wfo_flag)}
            size="sm"
          />
        ) : null
      }
    >
      {m ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <MetricCard label="Stitched OOS trades" value={m.total_trades || '—'} />
          <MetricCard
            label="OOS win rate"
            value={m.win_rate_pct === null ? '—' : `${m.win_rate_pct.toFixed(1)}%`}
          />
          <MetricCard
            label="OOS profit factor"
            value={m.profit_factor === null ? '—' : m.profit_factor.toFixed(2)}
            tone={
              m.profit_factor === null ? undefined : m.profit_factor >= 1 ? 'positive' : 'negative'
            }
          />
          <MetricCard
            label="OOS max drawdown"
            value={m.max_drawdown_pct === null ? '—' : `${m.max_drawdown_pct.toFixed(1)}%`}
            tone="negative"
          />
        </div>
      ) : null}
      <p className="mt-3 text-[11px] text-muted">
        Result is the concatenation of out-of-sample slices after an SL/TP grid
        search per window. Per-window train/test periods, selected parameters and
        per-window OOS performance are not exposed by the current API.
      </p>
    </SectionCard>
  )
}
