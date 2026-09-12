import { getCommandCenterOverview } from '../api/commandCenter'
import type { CommandCenterOverviewResponse } from '../types/commandCenter'
import { useCachedResource, type CachedResource } from './dataCache'

type UseCommandCenterResult = Omit<CachedResource<CommandCenterOverviewResponse>, 'setLocal'>

/**
 * One aggregated GET, module-cached: coming back to the Command Center within
 * the reuse window renders the last snapshot instantly, refreshed quietly in
 * the background. Slow 60s poll otherwise — "today's" state drifts slowly.
 */
const REFRESH_MS = 60_000

export function useCommandCenter(): UseCommandCenterResult {
  return useCachedResource('command-center', (signal) => getCommandCenterOverview(signal), {
    refreshMs: REFRESH_MS,
    revalidateOn: ['tl:synced'],
  })
}
