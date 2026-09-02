import { useCallback, useEffect, useRef, useState } from 'react'
import { getCommandCenterOverview } from '../api/commandCenter'
import type { CommandCenterOverviewResponse } from '../types/commandCenter'
import type { LoadState } from './useWatchlist'

interface UseCommandCenterResult {
  state: LoadState
  data: CommandCenterOverviewResponse | null
  error: string | null
  refreshing: boolean
  refetch: () => void
}

/**
 * One aggregated GET. Slow 60s refresh (paused while the tab is hidden) —
 * "today's" state drifts slowly. AbortController + disposal guards; last-good
 * data kept during a refetch and on error.
 */
const REFRESH_MS = 60_000

export function useCommandCenter(): UseCommandCenterResult {
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<CommandCenterOverviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const hasData = useRef(false)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let disposed = false
    let controller: AbortController | null = null

    const load = () => {
      controller?.abort()
      controller = new AbortController()
      const signal = controller.signal
      if (hasData.current) setRefreshing(true)
      getCommandCenterOverview(signal)
        .then((payload) => {
          if (disposed || signal.aborted) return
          setData(payload)
          setError(null)
          setState('ready')
          hasData.current = true
        })
        .catch((err: unknown) => {
          if (disposed || signal.aborted) return
          setError(err instanceof Error ? err.message : 'Unknown error')
          if (!hasData.current) setState('error')
        })
        .finally(() => {
          if (!disposed && !signal.aborted) setRefreshing(false)
        })
    }

    load()
    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, REFRESH_MS)
    return () => {
      disposed = true
      window.clearInterval(timer)
      controller?.abort()
    }
  }, [nonce])

  return { state, data, error, refreshing, refetch }
}
