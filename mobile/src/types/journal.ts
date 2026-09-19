/** Mirrors api/schemas.py journal models (kept in sync by hand). */
export interface JournalTradeItem {
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
}

export interface JournalResponse {
  entries: JournalTradeItem[]
  total_trades: number
  wins: number
  losses: number
  total_net_profit: number
  accounts: string[]
  source: string
  writable: boolean
  timestamp: string
}

/** PATCH /api/operations/journal/{trade_id} body (M5). */
export interface JournalUpdateRequest {
  setup_tag?: string
  notes?: string
  chart_snapshot_url?: string
  rating?: number
}

export interface JournalUpdateResponse {
  entry: JournalTradeItem
  updated_fields: string[]
  writable: boolean
  source: string
  live_broker_transmission: string
  timestamp: string
}

/** Body of POST /api/operations/journal/trades (mirrors api/schemas.py ManualTradeIn). */
export interface ManualTradeRequest {
  account_id: string
  symbol: string
  direction: 'BUY' | 'SELL'
  volume: number
  entry_price: number
  exit_price: number
  commission: number
  swap: number
  gross_profit: number
  entry_time: string
  exit_time: string
  setup_tag?: string
  notes?: string
}
