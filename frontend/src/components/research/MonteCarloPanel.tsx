import type { MonteCarloBlock } from '../../types/research'
import { MetricCard, ResearchUnavailable, SectionCard } from './primitives'

/**
 * Monte-Carlo risk panel. Values come from `backtester.run_monte_carlo`
 * (trade-order reshuffle over the executed P&L series). No distribution is
 * synthesized here; if the engine returned nothing, that is stated.
 */
export function MonteCarloPanel({ mc }: { mc: MonteCarloBlock | null }) {
  return (
    <SectionCard
      title="Monte-Carlo risk"
      action={
        mc ? (
          <span className="font-mono text-[11px] text-muted">
            {mc.iterations.toLocaleString()} iterations
          </span>
        ) : null
      }
    >
      {!mc ? (
        <ResearchUnavailable>
          Monte-Carlo results are not available for this run (needs at least two
          executed trades).
        </ResearchUnavailable>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <MetricCard
              label="Risk of ruin"
              value={`${mc.risk_of_ruin_pct.toFixed(2)}%`}
              tone={mc.risk_of_ruin_pct > 0 ? 'warning' : 'positive'}
            />
            <MetricCard
              label="95% max drawdown"
              value={`${mc.confidence_95_dd_pct.toFixed(2)}%`}
              tone="negative"
            />
            <MetricCard
              label="Median max drawdown"
              value={`${mc.median_dd_pct.toFixed(2)}%`}
            />
          </div>
          <p className="mt-3 text-[11px] text-muted">{mc.note}</p>
          <p className="mt-1 text-[11px] text-muted">
            Full drawdown distribution / percentile series and expectancy ranges
            are not exposed by the current API.
          </p>
        </>
      )}
    </SectionCard>
  )
}
