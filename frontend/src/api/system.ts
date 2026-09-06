import { apiGet, apiPost, apiPut } from './client'

export interface MarketDataToggleResponse {
  live_market_data_enabled: boolean
  description: string
  generated_at: string
  safety_barrier: { live_automation_enabled: boolean; live_broker_transmission: string }
}

/** GET /api/system/market-data — current state of the live-MT5 quote switch. */
export function getMarketDataToggle(signal?: AbortSignal): Promise<MarketDataToggleResponse> {
  return apiGet<MarketDataToggleResponse>('/api/system/market-data', { signal })
}

/**
 * PUT /api/system/market-data — enable/disable live MT5 market data. When
 * disabled, the app never auto-launches the MetaTrader 5 terminal; quotes
 * come from Binance / Yahoo / cache instead.
 */
export function setMarketDataToggle(
  enabled: boolean,
  signal?: AbortSignal,
): Promise<MarketDataToggleResponse> {
  return apiPut<MarketDataToggleResponse>('/api/system/market-data', { enabled }, { signal })
}

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

/** PUT /api/system/sync — turn the background auto-sync loop on/off (persisted). */
export function setSyncAuto(autoEnabled: boolean, signal?: AbortSignal): Promise<SyncStatusResponse> {
  return apiPut<SyncStatusResponse>('/api/system/sync', { auto_enabled: autoEnabled }, { signal })
}
