/** Mirrors api/schemas.py Alert* — price-target alerts (monitoring only, nothing is ever traded). */
export type AlertCondition = 'ABOVE' | 'BELOW'

export interface AlertItem {
  id: number
  symbol: string
  target_price: number
  condition: AlertCondition
  status: string
  account_id: string
  notes: string | null
  created_at: string | null
  triggered_at: string | null
}

export interface AlertsResponse {
  alerts: AlertItem[]
  total: number
  active: number
  triggered: number
  supported_symbols: string[]
  timestamp: string
}

export interface AlertCreateRequest {
  symbol: string
  target_price: number
  condition: AlertCondition
  notes?: string
}
