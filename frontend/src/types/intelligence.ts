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
