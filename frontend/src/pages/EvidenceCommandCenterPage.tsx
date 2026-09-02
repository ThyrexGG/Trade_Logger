import { Link } from 'react-router-dom'
import { useEvidenceState } from '../lib/useEvidence'
import { EvidenceTabs } from '../components/evidence/EvidenceTabs'
import { SafetyBanner } from '../components/evidence/SafetyBanner'
import { EvidenceHeader } from '../components/evidence/EvidenceHeader'
import { EvidenceReadout } from '../components/evidence/EvidenceReadout'
import { EvidenceWarnings } from '../components/evidence/EvidenceWarnings'
import { MilestoneTimeline } from '../components/evidence/MilestoneTimeline'
import { HoldoutComparison } from '../components/evidence/HoldoutComparison'
import { SectionError } from '../components/evidence/primitives'
import { timeAgo } from '../lib/format'

/**
 * Forward Evidence Command Center (`/evidence`). One coordinated request to
 * `/api/forward-evidence/state`; every section renders authoritative values
 * only. Designed for a 3-second executive glance at evidence health.
 */
export function EvidenceCommandCenterPage() {
  const view = useEvidenceState()
  const { state, data, error, refreshing, fetchedAt, refetch } = view

  return (
    <div className="w-full space-y-4 px-4 py-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[11px] text-muted">
        {refreshing ? <span aria-live="polite">Refreshing…</span> : null}
        {fetchedAt ? (
          <span title={new Date(fetchedAt).toLocaleString()}>
            fetched {timeAgo(fetchedAt)}
          </span>
        ) : null}
        <button
          type="button"
          onClick={refetch}
          className="rounded border border-border px-2 py-1 text-xs text-primary hover:bg-surface-hover"
        >
          Refresh
        </button>
      </div>

      <EvidenceTabs />

      <EvidenceHeader state={state} data={data} error={error} />
      <SafetyBanner safety={data?.safety} />

      {state === 'error' && !data ? (
        <div className="rounded-lg border border-border bg-surface p-4">
          <SectionError
            message={error ?? 'The evidence service could not be reached.'}
            onRetry={refetch}
          />
        </div>
      ) : null}

      {data ? (
        <>
          {state === 'error' && error ? (
            <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
              Showing last good evidence — refresh failed: {error}
            </p>
          ) : null}

          <EvidenceReadout data={data} />

          <div className="grid gap-4 xl:grid-cols-2">
            <EvidenceWarnings data={data} />
            <MilestoneTimeline data={data} />
          </div>

          <HoldoutComparison data={data} />

          <p className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border-subtle pt-3 text-[11px] text-muted">
            <span>
              Forward evidence is research/validation context — it never
              authorizes live trading.
            </span>
            <Link
              to="/evidence/statistics"
              className="text-secondary hover:text-primary"
            >
              Statistical surveillance →
            </Link>
            <Link
              to="/evidence/governance"
              className="text-secondary hover:text-primary"
            >
              Governance & provenance →
            </Link>
          </p>
        </>
      ) : null}
    </div>
  )
}
