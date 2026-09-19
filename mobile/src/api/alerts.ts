import type { AlertCreateRequest, AlertItem, AlertsResponse } from '../types/alerts'
import { apiDelete, apiGet, apiPost } from './client'

/** GET /api/alerts — the alert list plus the symbols the server accepts. */
export function getAlerts(signal?: AbortSignal): Promise<AlertsResponse> {
  return apiGet<AlertsResponse>('/api/alerts', signal)
}

/** POST /api/alerts — create one alert (the server validates the symbol). */
export function createAlert(body: AlertCreateRequest, signal?: AbortSignal): Promise<{ alert: AlertItem }> {
  return apiPost<{ alert: AlertItem }>('/api/alerts', body, signal)
}

/** DELETE /api/alerts/{id} */
export function deleteAlert(id: number, signal?: AbortSignal): Promise<{ deleted: boolean }> {
  return apiDelete<{ deleted: boolean }>(`/api/alerts/${id}`, signal)
}
