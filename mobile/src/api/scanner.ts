import type { KillzoneScanResponse } from '../types/scanner'
import { apiGetSlow } from './client'

/** GET /api/scanner/killzone — candidate liquidity-sweep + MSS events. Pattern-flagging only, never a signal. */
export function scanKillzone(symbol: string, ltf: string, signal?: AbortSignal): Promise<KillzoneScanResponse> {
  const params = new URLSearchParams({ symbol, ltf })
  return apiGetSlow<KillzoneScanResponse>(`/api/scanner/killzone?${params.toString()}`, signal)
}
