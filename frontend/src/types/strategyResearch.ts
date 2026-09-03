/** Phase 69/70 — strategy research (historical data foundation + discovery). */

export interface SafetyBarrier {
  live_automation_enabled: boolean
  live_broker_transmission: string
}

export interface HistoricalCoverageRow {
  asset: string
  timeframe: string
  count: number
  first_iso: string | null
  last_iso: string | null
}

export interface DataSufficiency {
  state: string
  asset: string
  timeframe: string
  have_bars: number
  need_bars: number
  reasons: string[]
  next_dependency: string | null
  gap_analysis?: Record<string, unknown>
}

export interface HistoricalCoverageResponse {
  generated_at: string
  universe: string[]
  timeframes: string[]
  data_capable_timeframes: string[]
  available: HistoricalCoverageRow[]
  sufficiency: DataSufficiency[]
  notes: Record<string, string>
  safety_barrier: SafetyBarrier
}

export interface GoldMetric {
  name: string
  value: number | null
  unit: string
  reconstructable: boolean
  source_doc: string
  note: string
}

export interface GoldBaselineResponse {
  strategy_id: string
  strategy_version: string
  frozen_contract_hash: string
  contract_hash_matches_canonical: boolean
  edge_status: string
  edge_status_reason: string
  edge_status_rules: Record<string, string>
  previous_discovery: {
    strategy_name: string
    timeframe_stack: string
    execution_timeframe: string
    session_policy: string
    entry_rule: string
    stop_rule: string
    target_rule: string
    holdout_sample_n: number
    data_source: string
    verdict: string
    unverifiable: string[]
    metrics: GoldMetric[]
  }
  revalidated_metrics: {
    timeframe_substitution?: string
    approximation_strategy_id?: string
    '1h'?: Record<string, number> | null
    '1h_bootstrap_ci'?: Record<string, unknown> | null
    '1h_scorecard'?: string | null
    '1d'?: Record<string, number> | null
    '1d_scorecard'?: string | null
    comparison?: {
      metric: string
      old: number | null
      new: number | null
      unit: string
      difference: number | null
      interpretation: string
    }[]
  } | null
  wfo_status: string
  monte_carlo_status: string
  parameter_robustness: string
  regime_compatibility: string
  next_dependency: string
  generated_at: string
  safety_barrier: SafetyBarrier
}

export interface StrategyDefinition {
  id: string
  registry_name: string
  version: string
  family: string
  instrument_scope: string
  entry_conditions: string
  exit_conditions: string
  stop_model: string
  target_model: string
  filters: string
  parameter_schema: Record<string, { default: number; grid: number[]; kind: string }>
}

export interface StrategiesResponse {
  generated_at: string
  strategies: StrategyDefinition[]
  timeframe_stack: Record<string, [string, string]>
  execution_assumptions: Record<string, unknown>
  safety_barrier: SafetyBarrier
}

export interface LeaderboardRow {
  rank: number
  asset: string
  strategy_id: string
  strategy_family: string
  oos_expectancy_r: number | null
  oos_profit_factor: number | null
  oos_win_rate_pct: number | null
  oos_trades: number | null
  oos_ci: string | null
  research_ranking_score: number | null
  scorecard: string | null
  wfo_stability: number | null
}

export interface PairRankingResponse {
  state: 'NOT_COMPUTED' | 'AVAILABLE'
  reason?: string
  generated_at: string
  timeframe?: string
  deep?: boolean
  verdict?: string
  leaderboard: LeaderboardRow[]
  candidates: Record<string, unknown>[]
  pair_stability?: Record<string, { class: string; positive_instruments: string[] }>
  store_coverage?: HistoricalCoverageRow[]
  execution_assumptions?: Record<string, unknown>
  safety_barrier: SafetyBarrier
}
