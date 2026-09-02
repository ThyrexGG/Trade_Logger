import { useEvidenceState } from '../lib/useEvidence'
import { EvidencePageFrame } from '../components/evidence/EvidencePageFrame'
import { StatisticalSurveillance } from '../components/evidence/StatisticalSurveillance'
import { EvidenceWarnings } from '../components/evidence/EvidenceWarnings'
import { MilestoneTimeline } from '../components/evidence/MilestoneTimeline'
import { HoldoutComparison } from '../components/evidence/HoldoutComparison'

/** Statistical surveillance (`/evidence/statistics`). */
export function EvidenceStatisticsPage() {
  const view = useEvidenceState()

  return (
    <EvidencePageFrame
      title="Statistical Surveillance"
      description="Sample depth, evidence maturity, Wilson-score and bootstrap confidence intervals, and the engine's statistical warnings. React performs no statistical calculation."
      view={view}
    >
      {(data) => (
        <div className="space-y-4">
          <StatisticalSurveillance data={data} />
          <div className="grid gap-4 xl:grid-cols-2">
            <EvidenceWarnings data={data} />
            <MilestoneTimeline data={data} />
          </div>
          <HoldoutComparison data={data} />
          <p className="text-[11px] text-muted">
            Confidence intervals: Wilson score for win rate, non-parametric
            bootstrap for expectancy — both computed by the authoritative engine.
            Distribution series / per-trade R history are not exposed by the
            current evidence API and are not synthesized here.
          </p>
        </div>
      )}
    </EvidencePageFrame>
  )
}
