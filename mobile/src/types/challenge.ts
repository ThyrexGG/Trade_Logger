/**
 * Prop-firm challenge tracker (`/api/challenge/*`). An estimate from the synced balance and closed trades —
 * never a substitute for the firm's own dashboard.
 */
export type ChallengePhase = '1' | '2' | 'funded'
export type ChallengeDrawdownMode = 'trailing' | 'static'

export interface ChallengeConfig {
  account_id: string
  firm: string
  account_size: number
  phase1_target_pct: number
  phase2_target_pct: number
  max_drawdown_pct: number
  daily_loss_pct: number
  min_profit_days: number
  profit_day_threshold_pct: number
  drawdown_mode: ChallengeDrawdownMode
  phase: ChallengePhase
  phase_start_balance: number
  phase_start_date: string
  created_at: string
  consistency_pct?: number
}

export interface ChallengeConfigInput {
  account_id: string
  firm?: string
  account_size: number
  phase1_target_pct?: number
  phase2_target_pct?: number
  max_drawdown_pct?: number
  daily_loss_pct?: number
  min_profit_days?: number
  profit_day_threshold_pct?: number
  drawdown_mode?: ChallengeDrawdownMode
  /** best day's allowed share of total profit, in %; 0 switches the rule off; left out = keep what is saved */
  consistency_pct?: number
  /** YYYY-MM-DD: count trades from this day (the day the account or phase started); left out = unchanged */
  start_date?: string
}

export interface ChallengeStatus {
  configured: boolean
  account_id: string
  config: ChallengeConfig | null

  current_balance: number | null
  phase: ChallengePhase | null
  phase_target_pct: number | null
  phase_start_balance: number | null
  phase_progress_pct: number | null
  phase_progress_ratio: number | null
  phase_gain_amount: number | null
  phase_target_amount: number | null

  drawdown_mode: ChallengeDrawdownMode | null
  peak_balance: number | null
  drawdown_floor_balance: number | null
  drawdown_used_pct: number | null
  drawdown_budget_used_ratio: number | null

  daily_loss_today_amount: number | null
  daily_loss_used_pct: number | null
  daily_loss_budget_used_ratio: number | null

  profit_days_count: number | null
  min_profit_days: number | null
  profit_day_dates: string[]

  /** date of the first trade on this account, for the "count from my first trade" shortcut */
  first_trade_date?: string | null

  // consistency rule: the best day may be at most N% of the phase's total profit (optional: older servers omit them)
  consistency_status?: 'off' | 'no_profit' | 'pass' | 'fail' | null
  consistency_limit_pct?: number | null
  consistency_best_day_pct?: number | null
  consistency_best_day_amount?: number | null
  consistency_best_day_date?: string | null
  consistency_total_profit?: number | null
  consistency_extra_needed?: number | null
  consistency_next_day_max?: number | null
  consistency_cap_at_target?: number | null

  disclaimer: string
  timestamp: string
}
