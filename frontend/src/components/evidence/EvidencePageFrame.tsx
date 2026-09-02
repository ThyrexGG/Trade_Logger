import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { EvidenceView } from '../../lib/useEvidence'
import type { ForwardEvidenceState } from '../../types/evidence'
import { EvidenceTabs } from './EvidenceTabs'
import { SafetyBanner } from './SafetyBanner'
import { SectionError, SkeletonRows } from './primitives'
import { timeAgo } from '../../lib/format'

interface Props {
  title: string
  description: string
  view: EvidenceView
  /** Rendered once the state has loaded at least once. */
  children: (data: ForwardEvidenceState) => ReactNode
  crossLinks?: ReactNode
}

/**
 * Shared chrome for every evidence route: tabs, safety banner, freshness +
 * refresh control, and top-level loading / error handling. Section-level
 * failures are handled inside the child sections, not here.
 */
export function EvidencePageFrame({
  title,
  description,
  view,
  children,
  crossLinks,
}: Props) {
  const { state, data, error, refreshing, fetchedAt, refetch } = view

  return (
    <div className="w-full space-y-4 px-4 py-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-primary">{title}</h1>
          <p className="mt-0.5 max-w-2xl text-sm text-secondary">{description}</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted">
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
      </div>

      <EvidenceTabs />
      <SafetyBanner safety={data?.safety} />

      {state === 'loading' && !data ? (
        <div className="space-y-4">
          <div className="h-28 animate-pulse rounded-lg border border-border bg-surface" />
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={6} />
          </div>
        </div>
      ) : state === 'error' && !data ? (
        <div className="rounded-lg border border-border bg-surface p-4">
          <SectionError
            message={error ?? 'The evidence service could not be reached.'}
            onRetry={refetch}
          />
        </div>
      ) : data ? (
        <>
          {state === 'error' && error ? (
            <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
              Showing last good evidence — refresh failed: {error}
            </p>
          ) : null}
          {children(data)}
        </>
      ) : null}

      <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border-subtle pt-3 text-[11px] text-muted">
        <span>Research / validation context — no execution is possible from this area.</span>
        {crossLinks ?? (
          <Link to="/research/intelligence" className="text-secondary hover:text-primary">
            Market Intelligence →
          </Link>
        )}
      </div>
    </div>
  )
}
