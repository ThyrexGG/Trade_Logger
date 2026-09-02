import { Link } from 'react-router-dom'
import type {
  IntelligenceSummary,
  OpportunityMapResponse,
} from '../../types/intelligence'
import type { Section } from '../../lib/useIntelligence'
import { SectionCard, SkeletonRows, type IntelTone } from './primitives'

interface Item {
  id: string
  priority: number // 1 = highest
  tone: IntelTone
  title: string
  detail: string
  symbol?: string
}

/**
 * Prioritised readout of the current authoritative state. Every line is a
 * direct field-for-field presentation of `summary` / `opportunity-map` — no
 * narrative is generated and no conclusion is inferred.
 */
export function WhatMattersNow({
  summary,
  opportunity,
}: {
  summary: Section<IntelligenceSummary>
  opportunity: Section<OpportunityMapResponse>
}) {
  const s = summary.data
  const opp = opportunity.data

  if ((summary.state === 'loading' && !s) || (opportunity.state === 'loading' && !opp)) {
    return (
      <SectionCard title="What matters right now">
        <SkeletonRows rows={4} />
      </SectionCard>
    )
  }

  const items: Item[] = []

  if (s) {
    const dqTone: IntelTone =
      s.overall_data_quality >= 85
        ? 'positive'
        : s.overall_data_quality >= 70
          ? 'warning'
          : 'negative'
    if (s.overall_data_quality < 85) {
      items.push({
        id: 'dq',
        priority: 1,
        tone: dqTone,
        title: `Data quality ${s.overall_data_quality}/100 — ${s.quality_rating}`,
        detail: 'Intelligence is gated on data quality by the backend.',
      })
    }

    items.push({
      id: 'regime',
      priority: 2,
      tone:
        s.regime_confidence_pct < 50
          ? 'warning'
          : s.primary_regime.toUpperCase().includes('RISK_ON')
            ? 'positive'
            : 'neutral',
      title: `Regime: ${s.primary_regime} · ${s.secondary_regime}`,
      detail: `${s.regime_confidence_pct.toFixed(0)}% confidence · breadth ${s.breadth_bullish_pct.toFixed(0)}% bullish / ${s.breadth_bearish_pct.toFixed(0)}% bearish`,
    })

    items.push({
      id: 'strongest',
      priority: 3,
      tone: 'positive',
      title: `Strongest asset: ${s.strongest_asset}`,
      detail: 'Highest relative context strength across the scanned universe.',
      symbol: s.strongest_asset,
    })
    items.push({
      id: 'weakest',
      priority: 3,
      tone: 'negative',
      title: `Weakest asset: ${s.weakest_asset}`,
      detail: 'Lowest relative context strength across the scanned universe.',
      symbol: s.weakest_asset,
    })

    if (s.usd_strength_state && s.usd_strength_state.toUpperCase() !== 'NEUTRAL') {
      items.push({
        id: 'usd',
        priority: 2,
        tone: 'warning',
        title: `USD strength: ${s.usd_strength_state}`,
        detail: `USD strength score ${s.usd_strength_score > 0 ? '+' : ''}${s.usd_strength_score.toFixed(1)}`,
      })
    }
  }

  if (opp && opp.ranked_assets.length > 0) {
    const eligible = opp.ranked_assets.filter((a) => a.ranking_eligible)
    const top = (eligible[0] ?? opp.ranked_assets[0])
    items.push({
      id: 'top-opp',
      priority: 1,
      tone: 'positive',
      title: `Top-ranked opportunity: ${top.symbol}`,
      detail: `Edge ${top.edge_score > 0 ? '+' : ''}${top.edge_score.toFixed(1)} · ${top.context_state} · driver: ${top.dominant_driver}`,
      symbol: top.symbol,
    })

    const conflicts = opp.ranked_assets.filter((a) =>
      a.conflict_state.toUpperCase().includes('CONFLICT'),
    )
    if (conflicts.length > 0) {
      items.push({
        id: 'conflicts',
        priority: 1,
        tone: 'warning',
        title: `${conflicts.length} asset${conflicts.length > 1 ? 's' : ''} with factor conflict`,
        detail: conflicts
          .slice(0, 6)
          .map((a) => a.symbol)
          .join(', '),
      })
    }
  }

  items.sort((a, b) => a.priority - b.priority)

  const toneBorder: Record<IntelTone, string> = {
    positive: 'border-l-positive',
    negative: 'border-l-negative',
    warning: 'border-l-warning',
    neutral: 'border-l-border',
  }

  return (
    <SectionCard title="What matters right now">
      {items.length === 0 ? (
        <p className="text-sm text-muted">
          No prioritised items — the executive summary returned no notable state.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((it) => {
            const body = (
              <div
                className={`border-l-2 pl-3 ${toneBorder[it.tone]}`}
              >
                <p className="text-sm font-medium text-primary">{it.title}</p>
                <p className="text-xs text-muted">{it.detail}</p>
              </div>
            )
            return (
              <li key={it.id}>
                {it.symbol ? (
                  <Link
                    to={`/research/intelligence/asset/${encodeURIComponent(it.symbol)}`}
                    className="block rounded transition-colors hover:bg-surface-elevated"
                  >
                    {body}
                  </Link>
                ) : (
                  body
                )}
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3 border-t border-border-subtle pt-2 text-[11px] text-muted">
        Contextual intelligence — not an order signal.
      </p>
    </SectionCard>
  )
}
