import { apiGet } from './client'
import type { IntradayCopilotResponse } from '../types/intradayCopilot'

/**
 * GET /api/research/intraday-copilot — Phase 100 persisted artifact: the
 * latest-bar structural-condition scan for the FX + gold intraday universe,
 * sample forward-outcome base rates, and the setup-skill tracker. Read-only.
 */
export function getIntradayCopilot(signal?: AbortSignal): Promise<IntradayCopilotResponse> {
  return apiGet<IntradayCopilotResponse>('/api/research/intraday-copilot', { signal })
}
