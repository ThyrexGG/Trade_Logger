/** Subset of the GET/POST /api/system/sync payload the app reads. */
export interface SyncRunResult {
  ok: boolean
  errors: string[]
  [key: string]: unknown
}

export interface SyncStatusResponse {
  cycle_in_progress: boolean
  last_run: SyncRunResult | null
  ran?: SyncRunResult | SyncRunResult[]
  generated_at: string
}
