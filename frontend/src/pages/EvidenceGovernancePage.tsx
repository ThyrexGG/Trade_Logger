import { useEvidenceState } from '../lib/useEvidence'
import { EvidencePageFrame } from '../components/evidence/EvidencePageFrame'
import { GovernancePanel } from '../components/evidence/GovernancePanel'
import { StrategyIdentity } from '../components/evidence/StrategyIdentity'
import { DatasetIntegrity } from '../components/evidence/DatasetIntegrity'
import { ProvenancePanel } from '../components/evidence/ProvenancePanel'

/** Governance + provenance (`/evidence/governance`). */
export function EvidenceGovernancePage() {
  const view = useEvidenceState()

  return (
    <EvidencePageFrame
      title="Governance & Provenance"
      description="Why this evidence can be trusted: strategy identity, dataset isolation, decision governance and evidence provenance. Read-only — viewing writes no audit record."
      view={view}
    >
      {(data) => (
        <div className="space-y-4">
          <GovernancePanel data={data} />
          <div className="grid gap-4 lg:grid-cols-2">
            <StrategyIdentity data={data} />
            <ProvenancePanel data={data} />
          </div>
          <DatasetIntegrity data={data} />
        </div>
      )}
    </EvidencePageFrame>
  )
}
