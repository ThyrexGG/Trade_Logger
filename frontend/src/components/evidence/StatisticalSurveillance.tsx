import type { ForwardEvidenceState, Interval } from '../../types/evidence'
import {
  EvidenceStatusTag,
  IntervalBar,
  SectionCard,
  evidenceTone,
} from './primitives'

function DepthRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between border-b border-border-subtle/60 py-1.5 last:border-0">
      <span className="text-xs text-secondary">{label}</span>
      <span className="font-mono text-xs tabular-nums text-primary">{value}</span>
    </div>
  )
}

function CIGroup({
  title,
  ci90,
  ci95,
  ci99,
  point,
  min,
  max,
  unit,
  precision,
}: {
  title: string
  ci90: Interval
  ci95: Interval
  ci99: Interval
  point: number | null
  min: number
  max: number
  unit: string
  precision: number
}) {
  // A degenerate [0, 0] interval is what the engine emits before the first
  // observation — that is "no sample", not a real interval, so treat it as
  // not exposed rather than drawing a misleading zero-width bar.
  const real = (v: Interval): Interval =>
    v && !(v[0] === 0 && v[1] === 0) ? v : null
  const rows: Array<[string, Interval]> = [
    ['90%', real(ci90)],
    ['95%', real(ci95)],
    ['99%', real(ci99)],
  ]
  const anyExposed = rows.some(([, v]) => v)
  return (
    <div>
      <p className="text-xs font-medium text-secondary">{title}</p>
      {!anyExposed ? (
        <p className="mt-1 text-xs text-muted">
          Confidence intervals are not exposed at this sample size.
        </p>
      ) : (
        <div className="mt-2 space-y-2.5">
          {rows.map(([lvl, v]) => (
            <div key={lvl}>
              <p className="text-[10px] uppercase tracking-wider text-muted">
                {lvl} interval
              </p>
              <IntervalBar
                interval={v}
                point={point}
                min={min}
                max={max}
                unit={unit}
                precision={precision}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Statistical surveillance: sample depth, evidence maturity, and the engine's
 * Wilson-score (win rate) and bootstrap (expectancy) confidence intervals.
 * React computes none of these — every number comes from `uncertainty`.
 */
export function StatisticalSurveillance({
  data,
}: {
  data: ForwardEvidenceState
}) {
  const m = data.metrics
  const u = data.uncertainty
  const obs = m.win_count + m.loss_count + m.breakeven_count
  const hasSample = m.trades_n > 0

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionCard
        title="Sample & evidence depth"
        action={
          <EvidenceStatusTag
            value={u.status_badge}
            tone={evidenceTone(u.statistical_status)}
            size="sm"
          />
        }
      >
        <DepthRow label="Forward N" value={m.trades_n} />
        <DepthRow label="Wins" value={m.win_count} />
        <DepthRow label="Losses" value={m.loss_count} />
        <DepthRow label="Breakeven" value={m.breakeven_count} />
        <DepthRow label="Scored observations" value={obs} />
        <DepthRow label="Maturity tier" value={m.maturity_tier} />
        <DepthRow
          label="Toward next milestone"
          value={`N ${data.milestones.current_n} → ${data.milestones.next_milestone} (${data.milestones.completion_pct_toward_next.toFixed(0)}%)`}
        />
        <p className="mt-3 text-[11px] text-muted">{m.interpretation}</p>
      </SectionCard>

      <SectionCard title="Confidence & uncertainty">
        <div className="space-y-4">
          <CIGroup
            title="Win rate — Wilson score interval"
            ci90={u.ci_90_wr}
            ci95={u.ci_95_wr}
            ci99={u.ci_99_wr}
            point={hasSample ? m.win_rate_pct : null}
            min={0}
            max={100}
            unit="%"
            precision={1}
          />
          <div className="border-t border-border-subtle" />
          <CIGroup
            title="Expectancy E[R] — bootstrap interval"
            ci90={u.ci_90_exp}
            ci95={u.ci_95_exp}
            ci99={u.ci_99_exp}
            point={hasSample ? m.expectancy_r : null}
            min={-3}
            max={3}
            unit=" R"
            precision={3}
          />
        </div>
        <div className="mt-4 space-y-1 border-t border-border-subtle pt-2 text-[11px] text-muted">
          <p>{u.win_rate_statement}</p>
          <p>{u.expectancy_statement}</p>
          {u.valid_statement ? (
            <p className="text-secondary">{u.valid_statement}</p>
          ) : null}
        </div>
      </SectionCard>
    </div>
  )
}
