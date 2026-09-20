import type { ConnectionsEnvelope, CreateConnectionInput } from '../types/connections'
import { apiDelete, apiGet, apiPost, apiPostSlow } from './client'

/** GET /api/connections — metadata only; the server never returns a stored secret. */
export function listConnections(signal?: AbortSignal): Promise<ConnectionsEnvelope> {
  return apiGet<ConnectionsEnvelope>('/api/connections', signal)
}

export function createConnection(body: CreateConnectionInput, signal?: AbortSignal): Promise<ConnectionsEnvelope> {
  return apiPost<ConnectionsEnvelope>('/api/connections', body, signal)
}

export function deleteConnection(id: string, signal?: AbortSignal): Promise<ConnectionsEnvelope> {
  return apiDelete<ConnectionsEnvelope>(`/api/connections/${encodeURIComponent(id)}`, signal)
}

/** Logs in to Capital.com with the stored credentials and reads the account. Writes nothing. */
export function testConnection(id: string, signal?: AbortSignal): Promise<ConnectionsEnvelope> {
  return apiPostSlow<ConnectionsEnvelope>(`/api/connections/${encodeURIComponent(id)}/test`, {}, signal)
}

/** One history / balance / positions pull for this connection. Can take a while on a long history. */
export function syncConnection(id: string, signal?: AbortSignal): Promise<ConnectionsEnvelope> {
  return apiPostSlow<ConnectionsEnvelope>(`/api/connections/${encodeURIComponent(id)}/sync`, {}, signal)
}
