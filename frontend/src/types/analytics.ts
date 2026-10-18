/**
 * Analytics contracts (`/api/analytics/performance`, Stage 14). Read-only.
 * Every metric is produced by the backend `analytics.calculate_performance_metrics`;
 * the frontend only formats.
 */
import type { JournalLink } from './operations'

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
  wins: number
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
  /** Set only for one selected account: its synced balance minus all-time net P&L — a prefill guess, not a fact. */
  suggested_initial_balance: number | null
  /** The user's own saved value for this account, if they've set one — always wins over the suggestion above. */
  saved_initial_balance: number | null
}

/** One group of trades — a weekday, an hour, a holding-time range (api/insights.py). */
export interface InsightBucket {
  key: string
  label: string
  trades: number
  wins: number
  net_profit: number
}

/** Trades grouped by the one-tap journal answer. */
export interface RulesRow {
  tag: string
  trades: number
  wins: number
  net_profit: number
  avg_per_trade: number
}

export interface DayExtreme {
  date: string
  net_profit: number
}

export type StreakKind = 'win' | 'loss' | 'none'

export interface StreakStats {
  current_kind: StreakKind
  current_count: number
  longest_win: number
  longest_loss: number
  current_day_kind: StreakKind
  current_day_count: number
  longest_green_days: number
  longest_red_days: number
  green_days: number
  red_days: number
  best_day: DayExtreme | null
  worst_day: DayExtreme | null
}

export interface TradeInsights {
  /** IANA zone the weekday/hour buckets were computed in. */
  timezone: string
  by_weekday: InsightBucket[]
  by_hour: InsightBucket[]
  by_hold: InsightBucket[]
  /** trades whose open was never seen (no real open time / holding time) — left out of
   *  `by_weekday`, `by_hour` and `by_hold` rather than guessed */
  open_unknown: number
  rules: RulesRow[]
  streaks: StreakStats
}

export interface AnalyticsPerformanceResponse {
  metrics: PerformanceMetrics
  equity_curve: EquityAnchor[]
  equity_curve_sampled: boolean
  daily_pnl: DailyPnl[]
  symbol_breakdown: SymbolBreakdownRow[]
  tag_breakdown: TagBreakdownRow[]
  period_returns: PeriodReturns
  insights?: TradeInsights | null
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

export interface DayTrade {
  trade_id: string
  account_id: string
  symbol: string
  direction: string
  volume: number
  entry_price: number
  exit_price: number
  commission: number
  swap: number
  gross_profit: number
  net_profit: number
  entry_time: string
  exit_time: string
  duration_minutes: number
  setup_tag: string | null
  notes: string | null
  rating: number | null
  chart_snapshot_url: string | null
  screenshot_count?: number
  links?: JournalLink[]
}

export interface AnalyticsDayTradesResponse {
  date: string
  trades: DayTrade[]
  count: number
  wins: number
  net_profit: number
  live_broker_transmission: string
}
