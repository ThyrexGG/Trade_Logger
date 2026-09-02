import type { ReactNode } from 'react'
import type { ForwardEvidenceState } from '../../types/evidence'
import { EvidenceStatusTag, HashChip, SectionCard } from './primitives'

function PopulationCard({
  title,
  tone,
  rows,
}: {
  title: string
  tone: 'historical' | 'forward'
  rows: Array<[string, ReactNode]>
}) {
  return (
    <div
      className={`rounded border px-3 py-2.5 ${
        tone === 'historical'
          ? 'border-info/30 bg-info/5'
          : 'border-border bg-surface-elevated/40'
      }`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wider text-secondary">
        {title}
      </p>
      <dl className="mt-2 space-y-1.5">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3">
            <dt className="text-[11px] text-muted">{k}</dt>
            <dd className="font-mono text-[11px] tabular-nums text-primary">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

/**
 * Dataset integrity — makes the historical / forward separation explicit and
 * surfaces the engine's isolation verdict and dataset fingerprint. Populations
 * are never merged in this view.
 */
export function DatasetIntegrity({ data }: { data: ForwardEvidenceState }) {
  const ds = data.dataset
  const h = data.historical_baseline

  return (
    <SectionCard
      title="Dataset integrity"
      action={
        <EvidenceStatusTag
          value={ds.is_isolated ? 'ISOLATION VERIFIED' : 'ISOLATION FAILURE'}
          tone={ds.is_isolated ? 'positive' : 'negative'}
          size="sm"
        />
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <PopulationCard
          title="Historical holdout"
          tone="historical"
          rows={[
            ['Sample N', h.sample_size],
            ['Type', 'HISTORICAL_HOLDOUT'],
            ['State', h.status],
          ]}
        />
        <PopulationCard
          title={`Forward · ${ds.mode}`}
          tone="forward"
          rows={[
            ['Clean N', ds.clean_n],
            ['Total records', ds.total_records],
            ['Quarantined', ds.quarantined_count],
          ]}
        />
      </div>

      <dl className="mt-3 space-y-1.5 border-t border-border-subtle pt-3 text-xs">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Forward dataset fingerprint</dt>
          <dd>
            <HashChip value={ds.dataset_fingerprint} chars={16} />
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Contract hash on dataset</dt>
          <dd>
            <HashChip value={ds.contract_hash} chars={16} />
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] text-muted">Canonical dataset status</dt>
          <dd className="font-mono text-[11px] text-primary">{ds.status}</dd>
        </div>
      </dl>

      <p className="mt-3 text-[11px] text-muted">
        Only the historical holdout and the PAPER forward population are exposed
        by the current evidence API — shadow / live populations are not reported
        through this endpoint.
      </p>
    </SectionCard>
  )
}
