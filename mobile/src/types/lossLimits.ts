/**
 * Loss-limit alerts (`/api/loss-limits`): a daily-loss limit (money) and a drawdown limit (% below the peak
 * balance) per account. Closed trades only. Notification only — nothing here stops a trade.
 */
export interface LossLimitStatus {
  account_id: string
  daily_loss_limit: number | null
  drawdown_limit_pct: number | null
  /** today's net P&L on this account (negative when losing) */
  today_net_pnl: number
  /** today's loss as a positive number (0 on a winning day) */
  today_loss: number
  daily_ratio: number | null
  starting_balance: number | null
  starting_balance_source: 'saved' | 'broker' | null
  peak_balance: number | null
  current_balance: number | null
  drawdown_pct: number | null
  drawdown_ratio: number | null
  drawdown_needs_balance: boolean
}

export interface LossLimitsResponse {
  accounts: LossLimitStatus[]
  warn_at_pct: number
  note: string
  timestamp: string
}

export interface LossLimitsInput {
  daily_loss: number | null
  drawdown_pct: number | null
}
