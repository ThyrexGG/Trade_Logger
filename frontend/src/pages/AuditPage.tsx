import { Link } from 'react-router-dom'
import { useAudit } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import { AuditSummary, AuditView } from '../components/operations/AuditView'
import {
  OpsSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/operations/primitives'

/**
 * Operational audit (`/operations/audit`). Read-only over the
 * `execution_orders` execution trail. Immutable records — no acknowledge /
 * resolve / delete. Distinct from Evidence Governance (Stage 9).
 */
export function AuditPage() {
  const { state, data, error, refreshing, refetch } = useAudit()

  return (
    <PageContainer
      title="Operational Audit"
      description="Immutable execution-order audit trail. Read-only — audit records are evidence and are never modified here."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <Link to="/evidence/governance" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Evidence Governance
          </Link>
          <Link to="/operations/system" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            System
          </Link>
          <button type="button" onClick={refetch} className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Refresh
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <OpsSafetyBanner />

        {state === 'loading' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={8} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={error ?? 'The audit service could not be reached.'} onRetry={refetch} />
          </div>
        ) : data ? (
          <>
            {state === 'error' && error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                Showing last good audit trail — refresh failed: {error}
              </p>
            ) : null}
            <AuditSummary data={data} />
            <AuditView data={data} />
          </>
        ) : null}

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          This is the operational execution audit — not the Stage 9 Evidence
          Governance state. Not exposed by the current API: a general
          safety-event log, actor identity, severity classification, and
          server-side audit search / pagination (the latest {data?.total_returned ?? 200} of{' '}
          {data?.total_records ?? '—'} records are loaded and filtered client-side).
        </p>
      </div>
    </PageContainer>
  )
}
