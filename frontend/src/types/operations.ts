/**
 * Response contracts for the Operations adapter (`/api/operations/*`) and the
 * reused positions endpoint.
 *
 * Journal = the authoritative `closed_trades` table. Audit = the
 * `execution_orders` operational execution trail. System = `/api/health`
 * values + `system_health.evaluate_system_health`. All read-only — React adds
 * no operational data and mutates nothing.
 */

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

export interface AuditOrderItem {
  execution_id: string
  signal_id: string | null
  symbol: string | null
  side: string | null
  requested_quantity: number | null
  requested_entry: number | null
  stop_loss: number | null
  take_profit: number | null
  broker: string | null
  mode: string | null
  state: string | null
  reconciliation_status: string | null
  created_at: string | null
  submitted_at: string | null
  resolved_at: string | null
  filled_at: string | null
  execution_latency_ms: number | null
  reject_reason: string | null
  last_error: string | null
}

export interface AuditResponse {
  events: AuditOrderItem[]
  total_returned: number
  total_records: number
  state_counts: Record<string, number>
  mode_counts: Record<string, number>
  decision_ledger_records: number
  latest_event_at: string | null
  source: string
  read_only: boolean
  live_broker_transmission: string
  timestamp: string
}

export interface ReconciliationHealth {
  status: string | null
  healthy: boolean | null
  reason: string | null
  last_heartbeat: string | null
  last_success: string | null
  consecutive_failures: number | null
  iterations_count: number | null
}

export interface SystemSafetyGate {
  overall_status: string
  automation_allowed: boolean
  reasons: string[]
  kill_switch_engaged: boolean | null
  emergency_halt_engaged: boolean | null
  database_connected: boolean | null
  unresolved_unknown_orders_count: number | null
  reconciliation: ReconciliationHealth | null
}

export interface OperationsSystemResponse {
  api_status: string
  app_name: string
  version: string
  live_automation_enabled: boolean
  live_broker_transmission: string
  safety_gate: SystemSafetyGate
  open_positions: number
  timestamp: string
}
