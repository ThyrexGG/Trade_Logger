/** Broker connections (`/api/connections`). The server never sends a secret back — only this metadata. */
export interface BrokerConnection {
  id: string
  broker: string
  label: string | null
  account_id: string | null
  is_demo: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  last_sync_at: string | null
  last_sync_ok: boolean | null
  last_error: string | null
}

export interface ConnectionsEnvelope {
  encryption_configured: boolean
  detail?: string
  connections?: BrokerConnection[]
  connection?: BrokerConnection
  ok?: boolean
  deleted?: string
}

export interface CreateConnectionInput {
  label: string
  account_id: string
  is_demo: boolean
  secret: { api_key: string; email: string; password: string }
}
