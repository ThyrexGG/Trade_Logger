import type { ForwardEvidenceState } from '../../types/evidence'
import { HashChip, SectionCard } from './primitives'
import { timeAgo } from '../../lib/format'

/**
 * Evidence provenance — the identifying metadata attached to this evaluation.
 * Read-only: no audit record is created by viewing it.
 */
export function ProvenancePanel({ data }: { data: ForwardEvidenceState }) {
  const rel = timeAgo(data.timestamp)
  return (
    <SectionCard title="Provenance">
      <dl className="space-y-2 text-xs">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Evaluated at</dt>
          <dd className="font-mono text-[11px] text-primary" title={data.timestamp}>
            {new Date(data.timestamp).toLocaleString()}
            {rel ? <span className="ml-1 text-muted">({rel})</span> : null}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Symbol · mode</dt>
          <dd className="font-mono text-[11px] text-primary">
            {data.symbol} · {data.mode}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Strategy contract hash</dt>
          <dd>
            <HashChip value={data.strategy_contract_hash} chars={20} />
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Forward dataset fingerprint</dt>
          <dd>
            <HashChip value={data.dataset.dataset_fingerprint} chars={20} />
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-[11px] text-muted">
        Immutable audit / decision-history records are maintained by the
        governance store but are not served through the current evidence API.
        The Stage 3.5D read path deliberately performs no audit writes.
      </p>
    </SectionCard>
  )
}
