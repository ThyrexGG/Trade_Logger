/**
 * Macro / Market Intelligence contracts (`/api/macro/*`, Stage 18). Read-only.
 * Every response carries provenance so demo/seeded data is never shown as real.
 */

export interface MacroEnvelope {
  data_provider: string
  provider_is_live: boolean
  provenance: 'live' | 'seed_demo' | 'unavailable' | string
  available: boolean
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
  score: number
  direction: string | null
  confidence: string | null
  supporting: string[]
  conflicting: string[]
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
