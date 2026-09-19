import type { SyncStatusResponse } from '../types/system'
import { apiPost } from './client'

/** POST /api/system/sync/run — pull the latest trades & positions from the broker now (blocks a few seconds). */
export function runSyncNow(signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiPost<SyncStatusResponse>('/api/system/sync/run', {}, signal)
}
