import type { ReactNode } from 'react'
import type { ForwardEvidenceState } from '../../types/evidence'
import { EvidenceStatusTag, SectionCard, evidenceTone } from './primitives'

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <div className="mt-0.5 text-sm text-primary">{value}</div>
    </div>
  )
}

/**
 * Governance state — "why can this evidence be trusted and what is currently
 * allowed?". Every rule/verdict shown is the engine's; none is reconstructed.
 */
export function GovernancePanel({ data }: { data: ForwardEvidenceState }) {
  const dec = data.decision
  return (
    <SectionCard
      title="Governance state"
      action={
        <EvidenceStatusTag
          value={dec.decision_state}
          tone={evidenceTone(dec.decision_state)}
          size="sm"
        />
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Research decision state"
          value={
            <EvidenceStatusTag
              value={dec.decision_state}
              tone={evidenceTone(dec.decision_state)}
            />
          }
        />
        <Field
          label="Dataset pooling check"
          value={
            <EvidenceStatusTag
              value={data.holdout.pooling_prevention_check}
              tone={evidenceTone(data.holdout.pooling_prevention_check)}
            />
          }
        />
        <Field
          label="Strategy contract"
          value={
            <EvidenceStatusTag
              value={data.contract_valid ? 'VALID & FROZEN' : 'HASH MISMATCH'}
              tone={data.contract_valid ? 'positive' : 'negative'}
            />
          }
        />
        <Field
          label="Safety barrier"
          value={
            <EvidenceStatusTag
              value={data.safety.status}
              tone={evidenceTone(data.safety.status)}
            />
          }
        />
      </div>

      <div className="mt-4 space-y-2 border-t border-border-subtle pt-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted">Rationale</p>
          <p className="mt-0.5 text-xs text-secondary">{dec.rationale || '—'}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted">
            Research action
          </p>
          <p className="mt-0.5 text-xs text-secondary">{dec.research_action || '—'}</p>
        </div>
      </div>

      <p className="mt-3 text-[11px] text-muted">
        Numeric governance thresholds (sample, milestone, drawdown and freshness
        requirements) are enforced inside the engine and not enumerated by the
        current evidence API.
      </p>
    </SectionCard>
  )
}
