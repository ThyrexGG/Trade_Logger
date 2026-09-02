import { apiDelete, apiGet, apiPost } from './client'
import type {
  AlertCreateRequest,
  AlertCreateResponse,
  AlertDeleteResponse,
  AlertsResponse,
} from '../types/alerts'

/** GET /api/alerts — authoritative price-alert list + supported symbols. */
export function getAlerts(signal?: AbortSignal): Promise<AlertsResponse> {
  return apiGet<AlertsResponse>('/api/alerts', { signal })
}

/** POST /api/alerts — create one validated price alert. */
export function createAlert(
  body: AlertCreateRequest,
  signal?: AbortSignal,
): Promise<AlertCreateResponse> {
  return apiPost<AlertCreateResponse>('/api/alerts', body, { signal })
}

/** DELETE /api/alerts/{id} — remove one alert (404 if unknown). */
export function deleteAlert(
  alertId: number,
  signal?: AbortSignal,
): Promise<AlertDeleteResponse> {
  return apiDelete<AlertDeleteResponse>(`/api/alerts/${alertId}`, { signal })
}
