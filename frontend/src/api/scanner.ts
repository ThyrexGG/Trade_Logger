import { apiGet } from './client'
import type { KillzoneScanResponse } from '../types/scanner'

/** GET /api/scanner/killzone — candidate liquidity-sweep + MSS events, pattern-flagging only. */
export function scanKillzone(
  symbol: string,
  ltf: string,
  signal?: AbortSignal,
): Promise<KillzoneScanResponse> {
  const params = new URLSearchParams({ symbol, ltf })
  return apiGet<KillzoneScanResponse>(`/api/scanner/killzone?${params.toString()}`, { signal })
}
