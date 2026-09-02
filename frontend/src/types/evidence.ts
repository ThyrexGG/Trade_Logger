/**
 * Response contracts for the Forward Evidence & Governance adapter
 * (`/api/forward-evidence/*`).
 *
 * Every field here is computed by the authoritative Phase 49 statistical
 * monitoring engine and serialized verbatim by the FastAPI adapter. The React
 * layer performs NO statistical, milestone or governance calculation — it only
 * renders these values.
 */

export interface HistoricalBaseline {
  sample_size: number
  expected_r: number
  win_rate_pct: number
  profit_factor: number
  status: string
}

export interface ForwardMetrics {
  trades_n: number
  win_rate_pct: number
  expectancy_r: number
  average_r: number
  median_r: number
  profit_factor: number
  cumulative_r: number
  max_drawdown_r: number
  std_dev_r: number
  win_count: number
  loss_count: number
  breakeven_count: number
  win_streak: number
  loss_streak: number
  outcomes: Record<string, number>
  maturity_tier: string
  maturity_label: string
  interpretation: string
}

/** A [lower, upper] confidence interval, or null when the engine did not emit it. */
export type Interval = [number, number] | null

export interface Uncertainty {
  sample_n: number
  statistical_status: string
  status_badge: string
  win_rate_statement: string
  expectancy_statement: string
  ci_90_wr: Interval
  ci_95_wr: Interval
  ci_99_wr: Interval
  ci_90_exp: Interval
  ci_95_exp: Interval
  ci_99_exp: Interval
  prohibited_claim: string
  valid_statement: string
}

/** Historical / forward blocks are loosely shaped by the engine — read defensively. */
export interface HoldoutComparison {
  historical: Record<string, unknown>
  forward: Record<string, unknown>
  deltas: Record<string, number>
  comparison_verdict: string
  explanation: string
  pooling_prevention_check: string
}

export interface AlphaDecay {
  forward_n: number
  decay_state: string
  loss_clustering_detected: boolean
  expectancy_deterioration: boolean
  max_drawdown_expansion: boolean | null
  action_required: string
  summary: string
}

export interface MilestoneRoadmapEntry {
  target_n: number
  status_label: string
  trades_remaining: number
  is_reached: boolean
}

export interface MilestoneProgress {
  current_n: number
  next_milestone: number
  trades_remaining: number
  completion_pct_toward_next: number
  milestone_roadmap: MilestoneRoadmapEntry[]
}

export interface DecisionState {
  decision_state: string
  rationale: string
  research_action: string
}

export interface DatasetProvenance {
  symbol: string
  mode: string
  total_records: number
  clean_n: number
  quarantined_count: number
  dataset_fingerprint: string
  contract_hash: string
  is_isolated: boolean
  status: string
}

export interface SafetyBarrier {
  live_automation_enabled: boolean
  broker_transmission: string
  status: string
}

export interface ForwardEvidenceState {
  symbol: string
  mode: string
  sample_n: number
  win_rate_pct: number
  profit_factor: number
  expected_r: number
  next_milestone: number
  decision_state: string
  wilson_ci_lower_pct: number
  wilson_ci_upper_pct: number
  historical_baseline: HistoricalBaseline
  strategy_contract_hash: string
  contract_valid: boolean
  live_broker_transmission: string
  metrics: ForwardMetrics
  uncertainty: Uncertainty
  holdout: HoldoutComparison
  alpha_decay: AlphaDecay
  milestones: MilestoneProgress
  decision: DecisionState
  dataset: DatasetProvenance
  safety: SafetyBarrier
  timestamp: string
}

/** Reads a numeric field from a loosely-typed engine sub-object. */
export function numField(
  obj: Record<string, unknown>,
  key: string,
): number | null {
  const v = obj[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}
