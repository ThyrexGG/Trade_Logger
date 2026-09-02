/**
 * Analytics contracts (`/api/analytics/performance`, Stage 14). Read-only.
 * Every metric is produced by the backend `analytics.calculate_performance_metrics`;
 * the frontend only formats.
 */

export interface SymbolPnl {
  symbol: string
  net_profit: number
}

export interface DirectionStats {
  trades: number
  win_rate: number
  pnl: number
}

export interface PerformanceMetrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  break_even_trades: number
  win_rate: number
  loss_rate: number
  total_net_pnl: number
  total_gross_profit: number
  total_gross_loss: number
  profit_factor: number
  avg_win: number
  avg_loss: number
  win_loss_ratio: number
  expectancy: number
  max_drawdown_usd: number
  max_drawdown_pct: number
  sqn: number
  gain_pct: number
  final_balance: number
  peak_balance: number
  avg_duration_minutes: number
  long_stats: DirectionStats
  short_stats: DirectionStats
  best_trade: number
  worst_trade: number
  best_symbols: SymbolPnl[]
  worst_symbols: SymbolPnl[]
}

export interface EquityAnchor {
  time: string
  equity: number
  net_profit: number
  symbol: string
}

export interface DailyPnl {
  date: string
  net_profit: number
  trades: number
}

export interface SymbolBreakdownRow {
  symbol: string
  net_profit: number
  trades: number
  wins: number
  win_rate: number
}

export interface TagBreakdownRow {
  setup_tag: string
  net_profit: number
  trades: number
}

export interface PeriodReturns {
  avg_daily_pct: number
  weekly_pct: number
  monthly_pct: number
  annualized_pct: number
  weekly_pnl: number
  monthly_pnl: number
}

export interface AnalyticsFiltersEcho {
  account: string
  symbols: string[]
  start: string | null
  end: string | null
  initial_balance: number
}

export interface AnalyticsAvailable {
  accounts: string[]
  symbols: string[]
  date_min: string | null
  date_max: string | null
}

export interface AnalyticsPerformanceResponse {
  metrics: PerformanceMetrics
  equity_curve: EquityAnchor[]
  equity_curve_sampled: boolean
  daily_pnl: DailyPnl[]
  symbol_breakdown: SymbolBreakdownRow[]
  tag_breakdown: TagBreakdownRow[]
  period_returns: PeriodReturns
  official_balance: number | null
  filters_applied: AnalyticsFiltersEcho
  available: AnalyticsAvailable
  matched_trades: number
  source: string
  live_broker_transmission: string
  timestamp: string
}

export interface AnalyticsQuery {
  account?: string
  symbols?: string[]
  start?: string
  end?: string
  initial_balance?: number
}
