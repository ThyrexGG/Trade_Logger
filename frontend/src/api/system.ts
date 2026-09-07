import { apiGet, apiPost, apiPut } from './client'

export interface SyncRunResult {
  at: string
  source: string
  ok: boolean
  duration_sec: number
  mt5_ok: boolean
  capital_ok: boolean
  new_closed_trades: number
  errors: string[]
}

export interface SyncStatusResponse {
  auto_enabled: boolean
  loop_running: boolean
  cycle_in_progress: boolean
  interval_seconds: number
  last_run: SyncRunResult | null
  generated_at: string
  ran?: SyncRunResult
  /** run-if-stale only: set when no cycle was run */
  skipped?: boolean
  reason?: 'fresh' | 'in_progress' | 'auto_loop_on'
  heartbeat_age_sec?: number | null
  safety_barrier: { live_automation_enabled: boolean; live_broker_transmission: string }
}

/** GET /api/system/sync — state of the in-process broker-sync service. */
export function getSyncStatus(signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiGet<SyncStatusResponse>('/api/system/sync', { signal })
}

/** POST /api/system/sync/run — run one broker-sync cycle now (blocks a few seconds). */
export function runSyncNow(signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiPost<SyncStatusResponse>('/api/system/sync/run', {}, { signal })
}

/**
 * POST /api/system/sync/run-if-stale — run one cycle only if the last sync is
 * older than `maxAgeMinutes`. Deduplicated server-side across tabs / devices /
 * restarts. Called once on app load so a sleeping host still shows fresh data.
 */
export function runSyncIfStale(
  maxAgeMinutes = 15,
  signal?: AbortSignal,
): Promise<SyncStatusResponse> {
  return apiPost<SyncStatusResponse>(
    `/api/system/sync/run-if-stale?max_age_minutes=${maxAgeMinutes}`,
    {},
    { signal },
  )
}

/** PUT /api/system/sync — turn the background auto-sync loop on/off (persisted). */
export function setSyncAuto(autoEnabled: boolean, signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiPut<SyncStatusResponse>('/api/system/sync', { auto_enabled: autoEnabled }, { signal })
}
