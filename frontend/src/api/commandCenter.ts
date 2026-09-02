import { apiGet } from './client'
import type { CommandCenterOverviewResponse } from '../types/commandCenter'

/** GET /api/command-center/overview — aggregated read-only "what matters today". */
export function getCommandCenterOverview(
  signal?: AbortSignal,
): Promise<CommandCenterOverviewResponse> {
  return apiGet<CommandCenterOverviewResponse>('/api/command-center/overview', { signal })
}
