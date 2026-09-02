/**
 * Response for GET /api/positions, mirroring api/schemas.py
 * (PositionItem / PositionsResponse). Read-only.
 */

export interface PositionItem {
  position_id: string
  symbol: string
  direction: string
  volume: number
  entry_price: number
  current_price: number
  sl: number
  tp: number
  floating_pnl: number
  unrealized_r: string
  mae: string
  mfe: string
  account_id: string
}

export interface PositionsResponse {
  positions: PositionItem[]
  total_open: number
  total_floating_pnl: number
  timestamp: string
}
