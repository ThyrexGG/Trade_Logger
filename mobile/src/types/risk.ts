/**
 * Request/response for POST /api/risk/preview, mirroring api/schemas.py
 * (RiskPreviewRequest / RiskPreviewResponse). Calculation-only; the
 * authoritative sizing math lives in risk_gateway.py.
 *
 * The contract has NO risk-$ field (percentage only), NO stop-loss-pips field
 * (price only), and NO standalone pip-value field in the response.
 */

export interface RiskPreviewRequest {
  symbol: string
  side: 'BUY' | 'SELL'
  entry_price: number
  stop_loss: number
  take_profit_1?: number | null
  take_profit_2?: number | null
  requested_risk_pct: number
  account_balance: number
}

export interface RiskPreviewResponse {
  symbol: string
  side: string
  entry_price: number
  stop_loss: number
  take_profit_1: number
  take_profit_2: number
  account_balance: number
  target_risk_usd: number
  calculated_lot_size: number
  actual_risk_usd: number
  actual_risk_pct: number
  reward_tp1_usd: number
  reward_tp1_pct: number
  reward_tp2_usd: number
  reward_tp2_pct: number
  risk_reward_ratio: string
  estimated_margin_usd: number
  is_valid: boolean
  warnings: string[]
  errors: string[]
  live_broker_transmission: string
}
