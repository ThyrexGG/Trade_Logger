import type { ForwardEvidenceState } from '../../types/evidence'
import { EvidenceStatusTag, SectionCard } from './primitives'

function strField(obj: Record<string, unknown>, key: string): string | null {
  const v = obj[key]
  return typeof v === 'string' && v ? v : null
}

/** Strategy & evidence identity: frozen contract hash, mode, dataset type. */
export function StrategyIdentity({ data }: { data: ForwardEvidenceState }) {
  const datasetType =
    strField(data.holdout.historical, 'dataset_type') ?? 'HISTORICAL_HOLDOUT'

  return (
    <SectionCard
      title="Strategy identity"
      action={
        <EvidenceStatusTag
          value={data.contract_valid ? 'CONTRACT VALID' : 'CONTRACT MISMATCH'}
          tone={data.contract_valid ? 'positive' : 'negative'}
          size="sm"
        />
      }
    >
      <dl className="space-y-2.5 text-xs">
        <div>
          <dt className="text-[10px] uppercase tracking-wider text-muted">
            Strategy contract SHA-256 (frozen)
          </dt>
          <dd className="mt-0.5 break-all font-mono text-[11px] text-secondary">
            {data.strategy_contract_hash}
          </dd>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">Symbol</dt>
            <dd className="mt-0.5 font-mono text-primary">{data.symbol}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">
              Validation mode
            </dt>
            <dd className="mt-0.5 font-mono text-primary">{data.mode}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">
              Historical dataset
            </dt>
            <dd className="mt-0.5 font-mono text-primary">{datasetType}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">
              Baseline status
            </dt>
            <dd className="mt-0.5 font-mono text-primary">
              {data.historical_baseline.status}
            </dd>
          </div>
        </div>
      </dl>
      <p className="mt-3 text-[11px] text-muted">
        Strategy name/version and full provenance chain are not exposed by the
        current evidence API — only the frozen contract hash and validity flag.
      </p>
    </SectionCard>
  )
}
