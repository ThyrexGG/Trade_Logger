/**
 * Response shapes for GET /api/intelligence/*, mirroring api/schemas.py.
 * Kept in sync manually. Only fields the backend actually returns are declared.
 *
 * The intelligence API exposes: summary, opportunity-map, asset-profile/{symbol},
 * heatmap. It does NOT expose a dedicated cross-asset-regime endpoint, a
 * change-detection feed, or a correlation endpoint — those sections are derived
 * from `summary` where possible and otherwise omitted (never fabricated).
 */

export interface IntelligenceSummary {
  primary_regime: string
  secondary_regime: string
  regime_confidence_pct: number
  breadth_bullish_pct: number
  breadth_bearish_pct: number
  breadth_neutral_pct: number
  strongest_asset: string
  weakest_asset: string
  usd_strength_score: number
  usd_strength_state: string
  overall_data_quality: number
  quality_rating: string
  live_broker_transmission: string
  timestamp: string
}

export interface OpportunityMapItem {
  symbol: string
  asset_class: string
  edge_score: number
  macro_score: number
  agreement_pct: number
  data_quality_score: number
  context_state: string
  dominant_driver: string
  conflict_state: string
  ranking_eligible: boolean
}

export interface OpportunityMapResponse {
  total_assets: number
  ranked_assets: OpportunityMapItem[]
  timestamp: string
}

export interface CotEvidenceItem {
  points?: number
  reason?: string
  impact?: string
}

export interface CotSource {
  provider?: string
  status?: string
  timestamp?: string
  age_sec?: number
}

export interface CotSentiment {
  factor_name?: string
  score?: number
  direction?: string
  confidence?: string
  evidence?: CotEvidenceItem[]
  source?: CotSource
  data_available?: boolean
  cot_status?: string
  assigned_weight?: number
}

export interface AssetProfile {
  symbol: string
  overall_edge_score: number
  macro_context_score: number
  technical_score: number
  positioning_score: number
  data_quality_score: number
  factor_agreement_pct: number
  context_state: string
  dominant_drivers: string[]
  conflicts: string[]
  recent_surprises: Record<string, unknown>[]
  cot_sentiment: CotSentiment
  timestamp: string
}

/* ------------------------------------------------------------------------ *
 * Unified Evidence Fusion (Phase 67) — GET /api/intelligence/asset/{asset}
 * One canonical, timestamp-correct evidence object per asset. Category scores
 * are contextual intelligence, never an execution signal. INSUFFICIENT_EVIDENCE
 * (a source exists but not enough data) and PROVIDER_UNAVAILABLE (no source) are
 * distinct states and neither means "neutral".
 * ------------------------------------------------------------------------ */
export type EvidenceStateValue =
  | 'AVAILABLE'
  | 'INSUFFICIENT_EVIDENCE'
  | 'PROVIDER_UNAVAILABLE'
  | 'STALE'
  | 'CONFLICT'
  | 'NOT_APPLICABLE'

export type EvidenceDirectionValue = 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'UNKNOWN'

export type CrossCategoryStateValue =
  | 'AGREEMENT'
  | 'MIXED'
  | 'CONFLICT'
  | 'INSUFFICIENT_EVIDENCE'

export interface EvidenceItem {
  asset: string
  category: string
  metric: string
  state: EvidenceStateValue
  value: number | null
  unit: string | null
  direction: EvidenceDirectionValue
  strength: number | null
  confidence: number | null
  source: string | null
  source_id: string | null
  provenance: string | null
  as_of: string | null
  available_timestamp: string | null
  release_timestamp: string | null
  observation_timestamp: string | null
  vintage_timestamp: string | null
  /** candle-derived evidence (Phase 68) */
  timeframe: string | null
  latest_input_timestamp: string | null
  calculation_window: string | null
  age_seconds: number | null
  note: string | null
}

export interface EvidenceCategory {
  category: string
  state: EvidenceStateValue
  direction: EvidenceDirectionValue
  score: number | null
  confidence: number | null
  coverage: number | null
  freshness: string | null
  age_seconds: number | null
  evidence_count: number
  sources: string[]
  provenance: string | null
  reason: string | null
  next_dependency: string | null
  evidence: EvidenceItem[]
}

export interface CrossCategoryAssessment {
  state: CrossCategoryStateValue
  supporting_categories: string[]
  opposing_categories: string[]
  neutral_categories: string[]
  conflicting_categories: string[]
  dominant_direction: EvidenceDirectionValue
  agreement_ratio: number | null
  note: string | null
}

export interface EvidenceCoverage {
  per_category: Record<string, EvidenceStateValue>
  available_categories: number
  provider_unavailable_categories: number
  insufficient_categories: number
  total_categories: number
  coverage_ratio: number | null
}

export interface AssetIntelligence {
  asset: string
  as_of: string
  generated_at: string
  mode: 'LIVE' | 'HISTORICAL'
  timeframe: string | null
  categories: EvidenceCategory[]
  cross_category_state: CrossCategoryStateValue
  cross_category: CrossCategoryAssessment
  coverage: EvidenceCoverage
  conflicts: Record<string, unknown>[]
  data_gaps: Record<string, unknown>[]
  provenance: Record<string, unknown>[]
  provider_health: Record<string, unknown>
  model_version: string
  disclaimer: string
  safety_barrier: Record<string, unknown>
}

/** One economic-indicator cell in the heatmap matrix. */
export interface HeatmapIndicator {
  indicator_code?: string
  display_name?: string
  economy?: string
  category?: string
  actual?: number | null
  forecast?: number | null
  previous?: number | null
  raw_surprise?: number | null
  z_score?: number | null
  directional_interpretation?: string
  freshness?: string
  source?: string
  release_timestamp?: string
  badge_label?: string
  tint_color?: string
  tooltip_text?: string
}

/** The five macro categories are fixed by the backend schema (EconomyHeatmapRow). */
export const HEATMAP_CATEGORIES = [
  'growth',
  'inflation',
  'labor',
  'rates',
  'surprise',
] as const
export type HeatmapCategory = (typeof HEATMAP_CATEGORIES)[number]

export type EconomyHeatmapRow = {
  economy_code: string
  country_name: string
  flag: string
} & Record<HeatmapCategory, HeatmapIndicator>

export interface EconomicHeatmapResponse {
  matrix: EconomyHeatmapRow[]
  total_economies: number
  timestamp: string
}
