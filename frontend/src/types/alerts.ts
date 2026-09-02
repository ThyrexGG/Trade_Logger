/**
 * Price Alerts contracts (`/api/alerts`, Stage 13). Monitoring only — the API
 * has no order / execution / broker surface. `id`, `status`, `created_at` and
 * `triggered_at` are server-maintained and never sent by the client.
 */

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
  source: string
  live_broker_transmission: string
  timestamp: string
}

export interface AlertCreateRequest {
  symbol: string
  target_price: number
  condition: AlertCondition
  notes?: string
}

export interface AlertCreateResponse {
  alert: AlertItem
  live_broker_transmission: string
  timestamp: string
}

export interface AlertDeleteResponse {
  deleted: boolean
  alert_id: number
  timestamp: string
}
