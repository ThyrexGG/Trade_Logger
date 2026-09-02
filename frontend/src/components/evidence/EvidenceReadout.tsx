import type { ReactNode } from 'react'
import type { ForwardEvidenceState } from '../../types/evidence'
import { numField } from '../../types/evidence'
import {
  Delta,
  EvidenceStatusTag,
  SectionCard,
  evidenceTone,
} from './primitives'
import { timeAgo } from '../../lib/format'

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border-subtle/60 py-1.5 last:border-0">
      <span className="text-xs text-secondary">{label}</span>
      <span className="font-mono text-xs tabular-nums text-primary">{value}</span>
    </div>
  )
}

function signed(n: number | null, p = 2, unit = ''): string {
  if (n === null || !Number.isFinite(n)) return '—'
  return `${n > 0 ? '+' : ''}${n.toFixed(p)}${unit}`
}

/**
 * "What does the evidence say?" — a direct readout of the authoritative
 * forward result, the locked historical reference, and the backend-supplied
 * difference. No delta is computed here; only `holdout.deltas` is shown.
 */
export function EvidenceReadout({ data }: { data: ForwardEvidenceState }) {
  const m = data.metrics
  const h = data.historical_baseline
  const d = data.holdout.deltas
  const hasSample = m.trades_n > 0

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <SectionCard title="Current forward result">
        {hasSample ? (
          <div>
            <Row label="Observed sample" value={`N = ${m.trades_n}`} />
            <Row label="Expectancy" value={`${signed(m.expectancy_r)} R`} />
            <Row label="Win rate" value={`${m.win_rate_pct.toFixed(1)}%`} />
            <Row label="Profit factor" value={m.profit_factor.toFixed(2)} />
            <Row label="Cumulative R" value={signed(m.cumulative_r)} />
            <Row label="Max drawdown R" value={m.max_drawdown_r.toFixed(2)} />
            <Row
              label="Wins / losses / BE"
              value={`${m.win_count} / ${m.loss_count} / ${m.breakeven_count}`}
            />
            <Row
              label="Latest evidence"
              value={timeAgo(data.timestamp) ?? '—'}
            />
          </div>
        ) : (
          <p className="text-sm text-muted">
            No forward observations recorded yet. {m.interpretation}
          </p>
        )}
      </SectionCard>

      <SectionCard title="Historical reference (locked holdout)">
        <div>
          <Row label="Historical N" value={h.sample_size} />
          <Row label="Historical E[R]" value={`${signed(h.expected_r, 3)} R`} />
          <Row label="Historical win rate" value={`${h.win_rate_pct.toFixed(1)}%`} />
          <Row label="Historical PF" value={h.profit_factor.toFixed(2)} />
          <Row label="Status" value={h.status} />
        </div>
        <p className="mt-2 text-[11px] text-muted">
          Baseline is unpooled and never mixed with forward observations.
        </p>
      </SectionCard>

      <SectionCard title="Difference (backend-supplied)">
        {hasSample ? (
          <div>
            <Row
              label="Expectancy Δ"
              value={<Delta value={numField(d as Record<string, unknown>, 'expectancy_delta')} unit=" R" precision={3} />}
            />
            <Row
              label="Win rate Δ"
              value={<Delta value={numField(d as Record<string, unknown>, 'win_rate_delta_pct')} unit=" pp" />}
            />
            <Row
              label="Profit factor Δ"
              value={<Delta value={numField(d as Record<string, unknown>, 'profit_factor_delta')} />}
            />
            <Row
              label="Drawdown divergence"
              value={<Delta value={numField(d as Record<string, unknown>, 'drawdown_divergence_r')} unit=" R" goodWhenPositive={false} />}
            />
          </div>
        ) : (
          <p className="text-sm text-muted">
            Deltas are not meaningful with no forward sample. The engine reports:{' '}
            <span className="text-secondary">{data.holdout.comparison_verdict}</span>
          </p>
        )}
        <div className="mt-3 border-t border-border-subtle pt-2">
          <EvidenceStatusTag
            value={data.holdout.comparison_verdict}
            tone={evidenceTone(data.holdout.comparison_verdict)}
            size="sm"
          />
          {data.holdout.explanation ? (
            <p className="mt-1.5 text-[11px] text-muted">{data.holdout.explanation}</p>
          ) : null}
          <p className="mt-1 text-[11px] text-muted">
            {data.holdout.pooling_prevention_check}
          </p>
        </div>
      </SectionCard>
    </div>
  )
}
