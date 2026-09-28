import { apiGet, apiPost } from './client'
import type { KillzoneBoardResponse, KillzoneScanResponse, KillzoneWatchConfig } from '../types/scanner'

/** GET /api/scanner/killzone — candidate liquidity-sweep + MSS events, pattern-flagging only. */
export function scanKillzone(
  symbol: string,
  ltf: string,
  signal?: AbortSignal,
): Promise<KillzoneScanResponse> {
  const params = new URLSearchParams({ symbol, ltf })
  return apiGet<KillzoneScanResponse>(`/api/scanner/killzone?${params.toString()}`, { signal })
}

/** GET /api/scanner/killzone/board — the same scan across several symbols at once. */
export function scanKillzoneBoard(
  symbols: string[],
  ltf: string,
  signal?: AbortSignal,
): Promise<KillzoneBoardResponse> {
  const params = new URLSearchParams({ symbols: symbols.join(','), ltf })
  return apiGet<KillzoneBoardResponse>(`/api/scanner/killzone/board?${params.toString()}`, { signal })
}

/** GET /api/scanner/killzone/watch-config — this tenant's saved push-alert config. */
export function getKillzoneWatchConfig(signal?: AbortSignal): Promise<KillzoneWatchConfig> {
  return apiGet<KillzoneWatchConfig>('/api/scanner/killzone/watch-config', { signal })
}

/** POST /api/scanner/killzone/watch-config — save which symbols to watch and the confluence bar to notify on. */
export function setKillzoneWatchConfig(config: KillzoneWatchConfig): Promise<KillzoneWatchConfig> {
  return apiPost<KillzoneWatchConfig>('/api/scanner/killzone/watch-config', config)
}
