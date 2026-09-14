/**
 * Prop-firm challenge tracker contracts (`/api/challenge/*`, W13). Read/compute
 * over already-authoritative balance + closed-trade data; no execution path.
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

  disclaimer: string
  timestamp: string
}
