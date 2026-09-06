import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { ForwardEvidenceState } from '../../types/evidence'
import { useCarryForward } from '../../lib/useCarryForward'
import { EvidenceStatusTag, SectionCard, evidenceTone } from './primitives'

function Progress({ value, max }: { value: number; max: number }) {
  return (
    <div className="mt-1 h-1.5 overflow-hidden rounded bg-surface-elevated/40">
      <div
        className="h-1.5 bg-accent/50"
        style={{ width: `${Math.min(100, max > 0 ? (value / max) * 100 : 0)}%` }}
      />
    </div>
  )
}

function TrackerCard({
  name,
  scope,
  status,
  tone,
  reason,
  children,
  href,
}: {
  name: string
  scope: string
  status: string
  tone?: 'positive' | 'negative' | 'warning' | 'neutral' | 'info'
  reason?: string
  children?: ReactNode
  href: string
}) {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-elevated/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-primary">{name}</p>
          <p className="text-[10px] uppercase tracking-wider text-muted">{scope}</p>
        </div>
        <EvidenceStatusTag value={status} tone={tone} size="sm" />
      </div>
      {children ? <div className="mt-2">{children}</div> : null}
      {reason ? <p className="mt-2 text-[11px] leading-snug text-secondary">{reason}</p> : null}
      <Link
        to={href}
        className="mt-2 inline-block text-[11px] text-secondary hover:text-primary"
      >
        Open →
      </Link>
    </div>
  )
}

/**
 * Zone-level overview: live-vs-backtest forward tracking for every edge the
 * project follows. Each tracker has its own engine and detail page; this is
 * the "are any of them diverging?" glance.
 */
export function ForwardTrackers({ data }: { data: ForwardEvidenceState | null }) {
  const carry = useCarryForward()
  const cf = carry.data

  const led = cf?.ledger
  const gates = cf?.design_note?.verdict_gates
  const weeks = led?.forward_evidence.n_weeks ?? 0
  const confirmAt = gates?.confirm_at_weeks ?? 26
  const assessAt = gates?.insufficient_below_weeks ?? 12

  const goldState = data?.decision.decision_state ?? data?.decision_state
  const goldN = data?.metrics.trades_n ?? data?.sample_n ?? 0

  return (
    <SectionCard title="Forward trackers">
      <p className="mb-3 text-[11px] text-muted">
        Backtest says X — is live-forward delivering X? One card per edge; each
        links to its detail and its own engine.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <TrackerCard
          name="Crypto funding carry"
          scope="delta-neutral · Phase 98"
          status={cf?.verdict ?? (carry.state === 'error' ? 'UNAVAILABLE' : 'LOADING')}
          tone={
            cf?.verdict?.includes('TRACKING') || cf?.verdict?.includes('CONFIRM')
              ? 'positive'
              : cf?.verdict?.includes('DIVERG')
                ? 'negative'
                : 'neutral'
          }
          reason={cf?.verdict_reason}
          href="/research/crypto-carry"
        >
          {led ? (
            <div>
              <p className="text-[10px] text-muted">
                week {weeks} · assess at {assessAt} · confirm at {confirmAt} · anchor{' '}
                {led.go_live_anchor}
              </p>
              <Progress value={weeks} max={confirmAt} />
            </div>
          ) : null}
        </TrackerCard>

        <TrackerCard
          name="XAUUSD directional"
          scope="frozen contract · Phase 49"
          status={goldState ?? (data ? 'UNKNOWN' : 'LOADING')}
          tone={goldState ? evidenceTone(goldState) : 'neutral'}
          reason={
            data?.decision.rationale ??
            'The original Gold directional strategy. Research found no robust edge; this harness has no forward observations yet.'
          }
          href="/evidence/forward"
        >
          <p className="text-[10px] text-muted">
            forward observations: <span className="font-mono text-secondary">{goldN}</span>
            {data?.historical_baseline
              ? ` · baseline E[R] ${data.historical_baseline.expected_r} over ${data.historical_baseline.sample_size}`
              : ''}
          </p>
        </TrackerCard>
      </div>
    </SectionCard>
  )
}
