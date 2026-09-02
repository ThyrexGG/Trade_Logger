import { useCallback, useEffect, useRef, useState } from 'react'
import { getAlerts } from '../api/alerts'
import type { AlertsResponse } from '../types/alerts'
import type { LoadState } from './useWatchlist'

interface UseAlertsResult {
  state: LoadState
  data: AlertsResponse | null
  error: string | null
  refreshing: boolean
  refetch: () => void
}

/**
 * Slow refresh only — alert rows change rarely (created/deleted here, or flipped
 * to TRIGGERED by the standalone `auto_sync` daemon). Paused while the tab is
 * hidden. The create/delete flows call `refetch()` directly, so this interval
 * is just a safety net for daemon-side status changes.
 */
const REFRESH_MS = 60_000

export function useAlerts(): UseAlertsResult {
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const inFlight = useRef<AbortController | null>(null)
  const hasData = useRef(false)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let disposed = false

    const load = () => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      if (hasData.current) setRefreshing(true)

      getAlerts(controller.signal)
        .then((payload) => {
          if (disposed || controller.signal.aborted) return
          setData(payload)
          setError(null)
          setState('ready')
          hasData.current = true
        })
        .catch((err: unknown) => {
          if (disposed || controller.signal.aborted) return
          setError(err instanceof Error ? err.message : 'Unknown error')
          if (!hasData.current) setState('error')
        })
        .finally(() => {
          if (!disposed && !controller.signal.aborted) setRefreshing(false)
        })
    }

    load()
    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, REFRESH_MS)
    return () => {
      disposed = true
      window.clearInterval(timer)
      inFlight.current?.abort()
    }
  }, [nonce])

  return { state, data, error, refreshing, refetch }
}
