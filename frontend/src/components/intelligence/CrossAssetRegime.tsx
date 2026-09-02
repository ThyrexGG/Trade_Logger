import type { ReactNode } from 'react'
import type { IntelligenceSummary } from '../../types/intelligence'
import type { Section } from '../../lib/useIntelligence'
import { formatSignedScore } from '../../lib/format'
import {
  FreshnessBadge,
  IntelTag,
  SectionCard,
  SectionError,
  SkeletonRows,
} from './primitives'

/**
 * Cross-asset regime view. The intelligence API exposes regime state through
 * `/summary` only — there is no dedicated regime endpoint or transition-history
 * feed, so recent-change history is not shown (not fabricated).
 */
export function CrossAssetRegime({
  section,
  onRetry,
}: {
  section: Section<IntelligenceSummary>
  onRetry: () => void
}) {
  const s = section.data

  let body: ReactNode
  if (section.state === 'loading' && !s) {
    body = <SkeletonRows rows={3} />
  } else if (section.state === 'error' && !s) {
    body = <SectionError message={section.error} onRetry={onRetry} />
  } else if (!s) {
    body = null
  } else {
    const bull = s.breadth_bullish_pct
    const neut = s.breadth_neutral_pct
    const bear = s.breadth_bearish_pct
    body = (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <IntelTag value={s.primary_regime} label="primary" />
          <IntelTag value={s.secondary_regime} label="secondary" />
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Regime confidence
          </p>
          <div className="mt-1 flex items-center gap-2">
            <div className="h-2 flex-1 rounded bg-surface-elevated">
              <div
                className="h-2 rounded bg-info/70"
                style={{ width: `${Math.max(0, Math.min(100, s.regime_confidence_pct))}%` }}
              />
            </div>
            <span className="w-12 text-right font-mono text-xs tabular-nums text-primary">
              {s.regime_confidence_pct.toFixed(0)}%
            </span>
          </div>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">
            Market breadth
          </p>
          <div className="mt-1 flex h-3 overflow-hidden rounded bg-surface-elevated">
            <div className="bg-positive/60" style={{ width: `${bull}%` }} title={`Bullish ${bull.toFixed(0)}%`} />
            <div className="bg-neutral/50" style={{ width: `${neut}%` }} title={`Neutral ${neut.toFixed(0)}%`} />
            <div className="bg-negative/60" style={{ width: `${bear}%` }} title={`Bearish ${bear.toFixed(0)}%`} />
          </div>
          <div className="mt-1 flex justify-between font-mono text-[11px] tabular-nums">
            <span className="text-positive">{bull.toFixed(0)}% bull</span>
            <span className="text-secondary">{neut.toFixed(0)}% neut</span>
            <span className="text-negative">{bear.toFixed(0)}% bear</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 border-t border-border-subtle pt-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted">
              USD strength
            </p>
            <p className="mt-0.5 font-mono text-sm text-primary">
              {formatSignedScore(s.usd_strength_score)}{' '}
              <span className="text-muted">{s.usd_strength_state}</span>
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted">
              Leaders
            </p>
            <p className="mt-0.5 font-mono text-sm">
              <span className="text-positive">{s.strongest_asset}</span>
              <span className="mx-1 text-muted">/</span>
              <span className="text-negative">{s.weakest_asset}</span>
            </p>
          </div>
        </div>

        <p className="border-t border-border-subtle pt-2 text-[11px] text-muted">
          Regime transition history is not exposed by the current API.
        </p>
      </div>
    )
  }

  return (
    <SectionCard
      title="Cross-asset regime"
      action={s ? <FreshnessBadge timestamp={s.timestamp} /> : null}
    >
      {body}
    </SectionCard>
  )
}
