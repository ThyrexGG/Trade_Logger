/**
 * Response contracts for the Strategy Lab & Backtesting adapter
 * (`/api/research/*`).
 *
 * Every value originates in the authoritative Python research code
 * (`backtester`, `research_engine`, the `strategies` registry). React performs
 * no backtest, indicator, optimization or Monte-Carlo calculation — it only
 * renders these values. Research-only: no broker, no live execution.
 */

export interface StrategyInfo {
  name: string
  version: string
  description: string
}

export interface ResearchDefaults {
  train_split: number
  val_split: number
  holdout_split: number
  struct_tf: string
  bias_tf: string
  spread_pips: number
  slippage_pips: number
  commission_pct: number
  random_seed: number
}

export interface BacktestDefaults {
  strategy: string
  risk_pct: number
  sl_atr: number
  tp_atr: number
  capital: number
  slippage: number
  commission_pct: number
  fixed_spread: number
  train_split: number
}

export interface TimeframeSpec {
  timeframe: string
  period: string
  interval: string
  struct_tf: string
  bias_tf: string
}

export interface ResearchMethodology {
  execution_model: string
  lookahead_protection: boolean
  lookahead_note: string
  data_source: string
  timezone: string
  slippage_model: string
  commission_model: string
  spread_model: string
  split_model: string
  notes: string[]
}

export interface StrategyLabResponse {
  contract_hash: string
  strategies: StrategyInfo[]
  research_defaults: ResearchDefaults
  backtest_defaults: BacktestDefaults
  supported_symbols: string[]
  timeframes: TimeframeSpec[]
  methodology: ResearchMethodology
  mode: string
  live_broker_transmission: string
  timestamp: string
}

export type BacktestMode = 'standard' | 'walk_forward'

export interface BacktestRunRequest {
  symbol: string
  timeframe: string
  strategy: string
  mode: BacktestMode
  risk_pct: number
  sl_atr: number
  tp_atr: number
  capital: number
  slippage: number
  commission_pct: number
  fixed_spread: number
  train_split: number
  include_monte_carlo: boolean
}

export interface BacktestMetricsBlock {
  total_trades: number
  win_rate_pct: number | null
  profit_factor: number | null
  max_drawdown_pct: number | null
  wfo_flag: string | null
  raw: Record<string, string>
}

export interface BacktestTrade {
  entry_time: string | null
  exit_time: string | null
  direction: string | null
  position_size: number | null
  entry_price: number | null
  exit_price: number | null
  stop_loss: number | null
  take_profit: number | null
  gross_pnl: number | null
  commission: number | null
  pnl: number | null
  equity: number | null
  is_oos: boolean | null
  session: string | null
  liquidity_type: string | null
  confluence_score: number | null
}

export interface EquityPoint {
  time: string
  equity: number
}

export interface MonteCarloBlock {
  iterations: number
  risk_of_ruin_pct: number
  confidence_95_dd_pct: number
  median_dd_pct: number
  note: string
}

export interface BacktestConfigEcho {
  symbol: string
  timeframe: string
  strategy: string
  mode: string
  risk_pct: number
  sl_atr: number
  tp_atr: number
  capital: number
  slippage: number
  commission_pct: number
  fixed_spread: number
  train_split: number
}

export interface BacktestRunResponse {
  status: 'complete' | 'failed'
  mode: string
  config: BacktestConfigEcho
  config_id: string
  error: string | null
  ran_at: string
  duration_sec: number
  metrics: BacktestMetricsBlock | null
  metrics_is: BacktestMetricsBlock | null
  metrics_oos: BacktestMetricsBlock | null
  final_capital: string | null
  final_capital_value: number | null
  trades: BacktestTrade[]
  trades_total: number
  trades_truncated: boolean
  equity_curve: EquityPoint[]
  equity_curve_total: number
  equity_curve_sampled: boolean
  monte_carlo: MonteCarloBlock | null
  wfo_flag: string | null
  live_broker_transmission: string
}
