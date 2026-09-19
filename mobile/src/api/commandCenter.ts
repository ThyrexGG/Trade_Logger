import type { CommandCenterOverviewResponse } from '../types/commandCenter'
import { apiGetSlow } from './client'

/** GET /api/command-center/overview — today's P&L, open risk, alerts and market context in one request. */
export function getOverview(signal?: AbortSignal): Promise<CommandCenterOverviewResponse> {
  return apiGetSlow<CommandCenterOverviewResponse>('/api/command-center/overview', signal)
}
