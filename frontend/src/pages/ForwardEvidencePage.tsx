import { Link } from 'react-router-dom'
import { useEvidenceState } from '../lib/useEvidence'
import { EvidencePageFrame } from '../components/evidence/EvidencePageFrame'
import { EvidenceReadout } from '../components/evidence/EvidenceReadout'
import { HoldoutComparison } from '../components/evidence/HoldoutComparison'
import { MilestoneTimeline } from '../components/evidence/MilestoneTimeline'
import { EvidenceWarnings } from '../components/evidence/EvidenceWarnings'
import { SectionCard, EvidenceStatusTag, evidenceTone } from '../components/evidence/primitives'

/** Forward validation detail (`/evidence/forward`). */
export function ForwardEvidencePage() {
  const view = useEvidenceState()

  return (
    <EvidencePageFrame
      title="Forward Validation"
      description="Genuine forward observation accumulation, decision state and outcome distribution. Every metric is produced by the authoritative Phase 49 engine."
      view={view}
      crossLinks={
        <>
          <Link to="/evidence/statistics" className="text-secondary hover:text-primary">
            Statistics →
          </Link>
          <Link to="/workspace/risk" className="text-secondary hover:text-primary">
            Risk Gateway →
          </Link>
        </>
      }
    >
      {(data) => {
        const m = data.metrics
        const hasSample = m.trades_n > 0
        return (
          <div className="space-y-4">
            <SectionCard
              title="Decision state"
              action={
                <EvidenceStatusTag
                  value={data.decision.decision_state}
                  tone={evidenceTone(data.decision.decision_state)}
                  size="sm"
                />
              }
            >
              <p className="text-sm text-secondary">{data.decision.rationale}</p>
              <p className="mt-1 text-xs text-muted">
                Research action: {data.decision.research_action}
              </p>
            </SectionCard>

            <EvidenceReadout data={data} />

            <SectionCard title="Outcome distribution">
              {hasSample ? (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {Object.entries(m.outcomes).map(([k, v]) => (
                    <div key={k}>
                      <p className="text-[10px] uppercase tracking-wider text-muted">
                        {k.replace(/_/g, ' ').replace(' pct', '')}
                      </p>
                      <p className="mt-0.5 font-mono text-sm tabular-nums text-primary">
                        {v.toFixed(1)}%
                      </p>
                    </div>
                  ))}
                  <div className="col-span-2 sm:col-span-4 mt-1 grid grid-cols-3 gap-3 border-t border-border-subtle pt-2">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted">
                        Std dev R
                      </p>
                      <p className="font-mono text-sm text-primary">
                        {m.std_dev_r.toFixed(3)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted">
                        Win streak
                      </p>
                      <p className="font-mono text-sm text-primary">{m.win_streak}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted">
                        Loss streak
                      </p>
                      <p className="font-mono text-sm text-primary">{m.loss_streak}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted">
                  No forward observations yet — outcome distribution will populate
                  once genuine trades are recorded.
                </p>
              )}
            </SectionCard>

            <div className="grid gap-4 xl:grid-cols-2">
              <EvidenceWarnings data={data} />
              <MilestoneTimeline data={data} />
            </div>

            <HoldoutComparison data={data} />
          </div>
        )
      }}
    </EvidencePageFrame>
  )
}
