/**
 * Daily Command Center contracts (`/api/command-center/overview`, Stage 15A).
 * Read-only aggregate — every section is a re-shaped slice of an already
 * authoritative source. No section is recomputed in the browser.
 */

export interface CCSessionClock {
  utc_time: string
  current_session: string
  next_session: string
  next_session_in_min: number | null
}

export interface CCSafety {
  automation_enabled: boolean
  live_broker_transmission: string
  kill_switch_engaged: boolean | null
  overall_status: string
}

export interface CCDailyPerformance {
  date: string
  net_pnl: number
  trades: number
  wins: number
  losses: number
  win_rate: number
  gross_profit: number
  gross_loss: number
}

export interface CCAccountSummary {
  all_time_net_pnl: number
  all_time_trades: number
  all_time_win_rate: number
  profit_factor: number
  max_drawdown_pct: number
  official_balance: number | null
  derived_balance: number
}

export interface CCSymbolExposure {
  symbol: string
  count: number
  floating_pnl: number
}

export interface CCPositions {
  total_open: number
  total_floating_pnl: number
  long_count: number
  short_count: number
  by_symbol: CCSymbolExposure[]
}

export interface CCTriggeredAlert {
  id: number
  symbol: string
  condition: string
  target_price: number
  triggered_at: string | null
}

export interface CCAlerts {
  active: number
  triggered: number
  triggered_recent: CCTriggeredAlert[]
}

export interface CCMarketContext {
  primary_regime: string
  regime_confidence_pct: number
  breadth_bullish_pct: number
  breadth_bearish_pct: number
  strongest_asset: string
  weakest_asset: string
  usd_strength_state: string
  data_quality: number
}

export interface CCResearchState {
  decision_state: string
  sample_n: number
  headline: string
}

export interface CCNote {
  note_id: string
  created_at: string
  category: string
  note_text: string
  session_context: string | null
}

export interface CCWatchHighlight {
  symbol: string
  last_price: number | null
  bias: string | null
  score: number | null
}

export interface CommandCenterOverviewResponse {
  as_of: string
  session: CCSessionClock
  safety: CCSafety
  daily_performance: CCDailyPerformance | null
  account_summary: CCAccountSummary | null
  positions: CCPositions | null
  alerts: CCAlerts | null
  market_context: CCMarketContext | null
  research_state: CCResearchState | null
  research_notes: CCNote[]
  watchlist_highlights: CCWatchHighlight[]
  sections_degraded: string[]
  source: string
  live_broker_transmission: string
  timestamp: string
}
