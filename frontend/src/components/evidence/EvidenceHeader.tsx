import type { ForwardEvidenceState } from '../../types/evidence'
import type { LoadState } from '../../lib/useWatchlist'
import {
  EvidenceMetric,
  EvidenceStatusTag,
  FreshnessBadge,
  HashChip,
  evidenceTone,
} from './primitives'

function signed(n: number, p = 2): string {
  return `${n > 0 ? '+' : ''}${n.toFixed(p)}`
}

/**
 * Executive evidence header — answers "is the forward evidence healthy,
 * credible and progressing?" in one glance. All values authoritative.
 */
export function EvidenceHeader({
  state,
  data,
  error,
}: {
  state: LoadState
  data: ForwardEvidenceState | null
  error: string | null
}) {
  if (state === 'loading' && !data) {
    return <div className="h-28 animate-pulse rounded-lg border border-border bg-surface" />
  }
  if (state === 'error' && !data) {
    return (
      <div className="rounded-lg border border-border bg-surface px-4 py-3 text-sm text-negative">
        Forward evidence unavailable — {error}
      </div>
    )
  }
  if (!data) return null

  const m = data.metrics
  const hasSample = m.trades_n > 0

  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-lg font-semibold text-primary">Forward Evidence</h1>
          <EvidenceStatusTag value={data.decision.decision_state} />
          <span className="font-mono text-[11px] text-muted">
            {data.symbol} · {data.mode}
          </span>
        </div>
        <FreshnessBadge timestamp={data.timestamp} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        <EvidenceMetric
          label="Forward sample"
          value={`N = ${m.trades_n}`}
          sub={m.maturity_label}
        />
        <EvidenceMetric
          label="Observed E[R]"
          value={hasSample ? `${signed(m.expectancy_r)} R` : '—'}
          tone={hasSample ? (m.expectancy_r >= 0 ? 'positive' : 'negative') : 'neutral'}
          sub={hasSample ? undefined : 'no forward sample'}
        />
        <EvidenceMetric
          label="Observed win rate"
          value={hasSample ? `${m.win_rate_pct.toFixed(1)}%` : '—'}
        />
        <EvidenceMetric
          label="Profit factor"
          value={hasSample ? m.profit_factor.toFixed(2) : '—'}
        />
        <EvidenceMetric
          label="Cumulative R"
          value={hasSample ? signed(m.cumulative_r, 2) : '—'}
          tone={hasSample ? (m.cumulative_r >= 0 ? 'positive' : 'negative') : 'neutral'}
        />
        <EvidenceMetric
          label="Max drawdown R"
          value={hasSample ? m.max_drawdown_r.toFixed(2) : '—'}
        />
        <EvidenceMetric
          label="Uncertainty"
          value={
            <EvidenceStatusTag
              size="sm"
              value={data.uncertainty.status_badge}
              tone={evidenceTone(data.uncertainty.statistical_status)}
            />
          }
          mono={false}
        />
        <EvidenceMetric
          label="Alpha surveillance"
          value={
            <EvidenceStatusTag
              size="sm"
              value={data.alpha_decay.decay_state}
            />
          }
          mono={false}
        />
        <EvidenceMetric
          label="Next milestone"
          value={`N = ${data.milestones.next_milestone}`}
          sub={`${data.milestones.trades_remaining} to go · ${data.milestones.completion_pct_toward_next.toFixed(0)}%`}
        />
        <EvidenceMetric
          label="Dataset isolation"
          value={
            <EvidenceStatusTag
              size="sm"
              value={data.dataset.is_isolated ? 'ISOLATED' : 'COLLISION'}
              tone={data.dataset.is_isolated ? 'positive' : 'negative'}
            />
          }
          mono={false}
        />
        <EvidenceMetric
          label="Contract"
          value={
            <span className="inline-flex items-center gap-1.5">
              <EvidenceStatusTag
                size="sm"
                value={data.contract_valid ? 'VALID' : 'MISMATCH'}
                tone={data.contract_valid ? 'positive' : 'negative'}
              />
              <HashChip value={data.strategy_contract_hash} chars={8} />
            </span>
          }
          mono={false}
        />
        <EvidenceMetric
          label="Execution"
          value={<span className="font-mono text-[11px] text-blocked">🔒 {data.live_broker_transmission}</span>}
          mono={false}
        />
      </div>
    </div>
  )
}
