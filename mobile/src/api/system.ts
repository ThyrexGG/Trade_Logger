import type { SyncStatusResponse } from '../types/system'
import { apiGet, apiPost, apiPut } from './client'

/** POST /api/system/sync/run — pull the latest trades & positions from the broker now (blocks a few seconds). */
export function runSyncNow(signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiPost<SyncStatusResponse>('/api/system/sync/run', {}, signal)
}

/** GET /api/system/sync — includes whether the server's background auto-sync is on for this user. */
export function getSyncStatus(signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiGet<SyncStatusResponse>('/api/system/sync', signal)
}

/** PUT /api/system/sync — turn the server's background auto-sync (every ~2 min) on or off for this user. */
export function setSyncAuto(autoEnabled: boolean, signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiPut<SyncStatusResponse>('/api/system/sync', { auto_enabled: autoEnabled }, signal)
}
