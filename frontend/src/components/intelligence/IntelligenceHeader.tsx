import type { ReactNode } from 'react'
import type { IntelligenceSummary } from '../../types/intelligence'
import type { Section } from '../../lib/useIntelligence'
import { formatSignedScore } from '../../lib/format'
import { DataQualityBadge, FreshnessBadge, IntelTag } from './primitives'

function Metric({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <div className="mt-0.5 text-sm text-primary">{children}</div>
    </div>
  )
}

/** Compact executive intelligence header — regime, breadth, USD, quality. */
export function IntelligenceHeader({
  section,
}: {
  section: Section<IntelligenceSummary>
}) {
  const s = section.data

  if (section.state === 'loading' && !s) {
    return (
      <div className="h-20 animate-pulse rounded-lg border border-border bg-surface" />
    )
  }
  if (section.state === 'error' && !s) {
    return (
      <div className="rounded-lg border border-border bg-surface px-4 py-3 text-sm text-negative">
        Executive summary unavailable — {section.error}
      </div>
    )
  }
  if (!s) return null

  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-lg font-semibold text-primary">
            Market Intelligence
          </h1>
          <IntelTag value={s.primary_regime} />
          <IntelTag value={s.secondary_regime} />
          <span className="font-mono text-xs text-secondary">
            {s.regime_confidence_pct.toFixed(0)}% confidence
          </span>
        </div>
        <FreshnessBadge timestamp={s.timestamp} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 xl:grid-cols-6">
        <Metric label="Strongest">
          <span className="font-mono text-positive">{s.strongest_asset}</span>
        </Metric>
        <Metric label="Weakest">
          <span className="font-mono text-negative">{s.weakest_asset}</span>
        </Metric>
        <Metric label="Breadth (bull / neut / bear)">
          <span className="font-mono text-xs tabular-nums">
            <span className="text-positive">
              {s.breadth_bullish_pct.toFixed(0)}%
            </span>{' '}
            /{' '}
            <span className="text-secondary">
              {s.breadth_neutral_pct.toFixed(0)}%
            </span>{' '}
            /{' '}
            <span className="text-negative">
              {s.breadth_bearish_pct.toFixed(0)}%
            </span>
          </span>
        </Metric>
        <Metric label="USD strength">
          <span className="font-mono text-xs">
            {formatSignedScore(s.usd_strength_score)}{' '}
            <span className="text-muted">{s.usd_strength_state}</span>
          </span>
        </Metric>
        <Metric label="Data quality">
          <DataQualityBadge score={s.overall_data_quality} rating={s.quality_rating} />
        </Metric>
        <Metric label="Execution">
          <span className="font-mono text-[11px] text-negative">
            🔒 {s.live_broker_transmission}
          </span>
        </Metric>
      </div>
    </div>
  )
}
