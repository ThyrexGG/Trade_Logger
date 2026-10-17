import { apiDelete, apiGet, apiPatch, apiPost } from './client'

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

interface Envelope {
  encryption_configured: boolean
  safety_barrier: { live_automation_enabled: boolean; live_broker_transmission: string }
  detail?: string
  connections?: BrokerConnection[]
  connection?: BrokerConnection
  ok?: boolean
  deleted?: string
}

export interface ConnectionSecretInput {
  api_key: string
  email: string
  password: string
}

export interface CreateConnectionInput {
  label: string
  account_id: string
  is_demo: boolean
  secret: ConnectionSecretInput
}

export function listConnections(signal?: AbortSignal): Promise<Envelope> {
  return apiGet<Envelope>('/api/connections', { signal })
}

export function createConnection(body: CreateConnectionInput): Promise<Envelope> {
  return apiPost<Envelope>('/api/connections', body)
}

export function updateConnection(
  id: string,
  body: Partial<{ label: string; account_id: string; is_demo: boolean; is_active: boolean; secret: Partial<ConnectionSecretInput> }>,
): Promise<Envelope> {
  return apiPatch<Envelope>(`/api/connections/${id}`, body)
}

export function deleteConnection(id: string): Promise<Envelope> {
  return apiDelete<Envelope>(`/api/connections/${id}`)
}

export function testConnection(id: string): Promise<Envelope> {
  return apiPost<Envelope>(`/api/connections/${id}/test`, {})
}

export function syncConnection(id: string): Promise<Envelope> {
  return apiPost<Envelope>(`/api/connections/${id}/sync`, {})
}

/** One 30-day slice of the older-history import. The caller hands back
 *  `next_before` / `empty_days` to continue until `done`. */
export interface BackfillStepResult {
  ok: boolean
  detail?: string
  imported: number
  next_before: string | null
  empty_days: number
  done: boolean
  oldest_trade?: string | null
}

export function backfillConnection(
  id: string,
  body: { before: string | null; empty_days: number },
): Promise<BackfillStepResult> {
  return apiPost<BackfillStepResult>(`/api/connections/${id}/backfill`, body)
}
