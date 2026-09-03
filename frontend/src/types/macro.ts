/**
 * Macro / Market Intelligence contracts (`/api/macro/*`, Stage 18). Read-only.
 * Every response carries provenance so demo/seeded data is never shown as real.
 */

export interface MacroEnvelope {
  data_provider: string
  provider_is_live: boolean
  provenance: 'live' | 'seed_demo' | 'unavailable' | string
  provider_state?:
    | 'LIVE' | 'LIVE_STALE' | 'SEED_DEMO' | 'NONE' | 'PROVIDER_UNAVAILABLE'
    | 'PENDING' | 'NOT_CONFIGURED' | 'CONFLICT' | 'STALE' | string
  provider_status?: {
    provider?: string
    provider_state?: string
    configured?: boolean
    records_registered?: number
    coverage?: Record<string, string[]> | string[]
    series_errors?: Record<string, string>
    last_error?: string | null
    hydrated_age_sec?: number | null
    cache_ttl_sec?: number
  }
  /** Phase 66 — per-economy × per-category evidence state. */
  coverage?: Record<string, Record<string, string>>
  conflicts?: MacroConflict[]
  cot_status?: ProviderHealth | null
  forecast_status?: ProviderHealth | null
  sentiment_status?: ProviderHealth | null
  available: boolean
  disclaimer?: string | null
  timestamp: string
}

export interface MacroConflict {
  identity: [string, string, string]
  country: string
  metric: string
  period: string
  field: string
  state: 'CONFLICT'
  selected_source: string
  selected_value: number
  claims: { source: string; value: number; rank: number }[]
}

export interface ProviderHealth {
  provider?: string
  provider_state?: string
  configured?: boolean
  records_registered?: number
  coverage?: string[] | Record<string, string[]>
  last_success?: string | null
  last_failure?: string | null
  last_error?: string | null
  latency_ms?: number | null
  hydrated_age_sec?: number | null
  cache_ttl_sec?: number
  backoff_until_sec?: number | null
  reason?: string
  forecasts?: number
  observations?: number
}

export interface ProviderInfo {
  key: string
  name: string
  capabilities: string[]
  configured: boolean
  is_live: boolean
  health: ProviderHealth
}

export interface MacroProvidersResponse {
  available: boolean
  as_of: string
  base_provider?: string | null
  provider_state?: string | null
  providers: ProviderInfo[]
  capabilities: Record<
    string,
    { declared_by: string[]; configured_by: string[]; available: boolean; categories: string[] }
  >
  coverage: Record<string, Record<string, string>>
  conflicts: MacroConflict[]
  precedence: { rank: number; matches: string[] }[]
  disclaimer?: string | null
  timestamp: string
}

export interface MacroSurpriseLite {
  state: string
  surprise: number | null
  surprise_pct: number | null
  normalized_surprise: number | null
  direction_bias: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | string
  policy_bias: 'HAWKISH' | 'DOVISH' | 'NEUTRAL' | string
  confidence: string
  indicator_resolved?: string | null
  category?: string
  vs_previous?: number | null
}

export interface MacroEvent {
  event_id: string
  timestamp: string | null
  country: string | null
  currency: string | null
  event: string
  indicator: string | null
  category: string | null
  impact: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string
  actual: number | null
  forecast: number | null
  previous: number | null
  revised_previous: number | null
  unit: string | null
  source: string | null
  provider: string
  status: string
  provenance: string
  surprise: MacroSurpriseLite
}

export interface MacroEventsResponse extends MacroEnvelope {
  window?: string
  range?: { start: string; end: string }
  count: number
  total_matched: number
  truncated: boolean
  events: MacroEvent[]
  filters_applied?: Record<string, string>
}

export interface MacroSurpriseRow extends MacroSurpriseLite {
  event: string
  indicator: string | null
  currency: string | null
  country: string | null
  timestamp: string
  impact: string
  actual: number | null
  forecast: number | null
  previous: number | null
  unit: string | null
  source: string | null
  provenance: string
}

export interface MacroSurprisesResponse extends MacroEnvelope {
  count: number
  positive: number
  negative: number
  neutral: number
  surprises: MacroSurpriseRow[]
}

export interface MacroFactorGroup {
  score: number | null
  direction: string | null
  confidence: string | null
  supporting: string[]
  conflicting: string[]
  state?: string
  reason?: string
}

export interface MacroCurrency extends MacroEnvelope {
  currency: string
  state?: string
  reason?: string
  score?: number | null
  classification?: string | null
  confidence?: number | null
  direction?: string | null
  surprise_score?: number | null
  surprise_momentum?: string | null
  factor_groups?: Record<string, MacroFactorGroup>
  supporting_events?: { event: string; surprise_state: string; direction: string }[]
}

export interface MacroCurrenciesResponse extends MacroEnvelope {
  currencies: MacroCurrency[]
  strongest: { currency: string; score: number; direction: string }[]
  weakest: { currency: string; score: number; direction: string }[]
  insufficient_evidence: string[]
}

export interface MacroAsset extends MacroEnvelope {
  asset: string
  label?: string
  state?: string
  reason?: string
  macro_bias?: string | null
  score?: number | null
  bias_label?: string | null
  confidence?: number | null
  drivers?: Record<string, unknown>
  supporting_factors?: { factor: string; score: number; note?: string }[]
  opposing_factors?: { factor: string; score: number; note?: string }[]
  evidence_count?: number
  method?: string
}

export interface MacroAssetsResponse extends MacroEnvelope {
  assets: MacroAsset[]
}

export interface MacroOverviewResponse extends MacroEnvelope {
  macro_regime: string
  macro_regime_note?: string | null
  strongest_currencies: { currency: string; score: number; direction: string }[]
  weakest_currencies: { currency: string; score: number; direction: string }[]
  insufficient_currencies: string[]
  upcoming_high_impact: MacroEvent[]
  latest_surprises: MacroSurpriseRow[]
  data_freshness?: { as_of: string; note?: string | null }
  confidence?: number
}

// --- Macro Scorecard (Phase 64) ---------------------------------------
export interface MacroScorecardIndicator {
  indicator: string
  name: string
  family: string
  actual: number | null
  forecast: number | null
  previous: number | null
  unit?: string | null
  surprise: number | null
  z_score?: number | null
  surprise_state?: string
  direction?: string
  implication?: string
  release_time?: string | null
  freshness?: string
  currency_impact?: string
  equity_impact?: string
}

export interface MacroScorecardCategory {
  category: string
  score: number | null
  gauge: number | null
  direction: string
  state: string
  reason?: string
  next_dependency?: string
  model_prior?: number | null
  engine_direction?: string | null
  confidence?: string | null
  basis?: string
  base?: { economy: string; score: number; direction: string } | null
  quote?: { economy: string; score: number; direction: string } | null
  supporting?: string[]
  conflicting?: string[]
  context?: string[]
  indicators?: MacroScorecardIndicator[]
}

export interface MacroScorecardResponse extends MacroEnvelope {
  instrument: string
  state: string
  model_version?: string
  composite_score: number | null
  gauge: number | null
  bias: string | null
  direction?: string | null
  confidence?: number | null
  economic_strength?: number | null
  surprise_score?: number | null
  surprise_momentum?: string | null
  scope_note?: string | null
  primary_country?: string
  categories: MacroScorecardCategory[]
  strongest_category?: string | null
  weakest_category?: string | null
  sub_scores?: Record<string, number | null>
  reason?: string | null
  next_dependency?: string | null
  release_count?: number
}

export interface MacroScorecardHistoryPoint {
  timestamp: string
  composite_score: number | null
  direction?: string
  growth?: number | null
  inflation?: number | null
  jobs?: number | null
  cot?: number | null
  data_quality?: number | null
  fingerprint?: string
}

export interface MacroScorecardHistoryResponse extends MacroEnvelope {
  instrument: string
  state: string
  points: MacroScorecardHistoryPoint[]
  count: number
  note?: string | null
}

export interface MacroHeatmapResponse extends MacroEnvelope {
  country: string
  country_name?: string
  central_bank?: string | null
  state: string
  aggregate_score: number | null
  aggregate_direction?: string | null
  indicators: MacroScorecardIndicator[]
  categories: { category: string; score: number | null; gauge: number | null; direction: string; state?: string }[]
  reason?: string | null
  next_dependency?: string | null
}

export interface MacroHeatmapIndexResponse extends MacroEnvelope {
  countries: { country: string; release_count: number; state: string }[]
}
