import { useCallback, useEffect, useRef, useState } from 'react'
import { getAnalyticsPerformance } from '../api/analytics'
import type { AnalyticsPerformanceResponse, AnalyticsQuery } from '../types/analytics'
import type { LoadState } from './useWatchlist'

interface UseAnalyticsResult {
  state: LoadState
  data: AnalyticsPerformanceResponse | null
  error: string | null
  refreshing: boolean
  refetch: () => void
}

const DEBOUNCE_MS = 300

/**
 * One aggregated GET per filter set. Filter changes are debounced (300ms) so a
 * multi-select or a date drag fires a single request, not a storm. Previous
 * request is aborted on every change; last-good data is kept during a refetch.
 * No polling — analytics only changes when new trades sync.
 */
export function useAnalytics(query: AnalyticsQuery): UseAnalyticsResult {
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<AnalyticsPerformanceResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const hasData = useRef(false)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  const key = JSON.stringify({
    account: query.account ?? 'ALL',
    symbols: [...(query.symbols ?? [])].sort(),
    start: query.start ?? null,
    end: query.end ?? null,
    initial_balance: query.initial_balance ?? null,
  })

  useEffect(() => {
    let disposed = false
    const controller = new AbortController()

    const timer = window.setTimeout(() => {
      if (hasData.current) setRefreshing(true)
      getAnalyticsPerformance(query, controller.signal)
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
    }, DEBOUNCE_MS)

    return () => {
      disposed = true
      window.clearTimeout(timer)
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce])

  return { state, data, error, refreshing, refetch }
}
