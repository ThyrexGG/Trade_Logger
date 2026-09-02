import type { EquityPoint } from '../../types/research'
import { ResearchUnavailable, SectionCard, Sparkline } from './primitives'

/**
 * Equity curve rendered from the authoritative (time, equity) series only.
 * No smoothing, no synthetic points, no reconstruction from summary metrics.
 */
export function EquityCurve({
  points,
  total,
  sampled,
}: {
  points: EquityPoint[]
  total: number
  sampled: boolean
}) {
  return (
    <SectionCard
      title="Equity curve"
      action={
        <span className="font-mono text-[11px] text-muted">
          {total.toLocaleString()} points{sampled ? ' · down-sampled for display' : ''}
        </span>
      }
    >
      {points.length < 2 ? (
        <ResearchUnavailable>
          The backtest returned no usable equity series.
        </ResearchUnavailable>
      ) : (
        <div className="text-primary">
          <Sparkline points={points} />
        </div>
      )}
      <p className="mt-2 text-[11px] text-muted">
        Bar-close account equity from the backtester. The dashed line marks the
        starting capital.
      </p>
    </SectionCard>
  )
}
