import { useCallback, useEffect, useRef, useState } from 'react'
import { getAnalyticsPerformance } from '../api/analytics'
import type { AnalyticsPerformanceResponse, AnalyticsQuery } from '../types/analytics'

// Last good result per filter set, so coming back to the tab (or flipping between
// filters already seen) paints instantly while a fresh copy loads behind it.
const cache = new Map<string, AnalyticsPerformanceResponse>()

function keyOf(q: AnalyticsQuery): string {
  return JSON.stringify([q.account ?? 'ALL', q.start ?? null, q.end ?? null, q.initial_balance ?? null])
}

export interface UseAnalytics {
  data: AnalyticsPerformanceResponse | null
  /** nothing to show yet */
  loading: boolean
  /** fetching in the background (pull-to-refresh or a filter change) */
  refreshing: boolean
  error: string | null
  refresh: () => void
}

/** Fetches /api/analytics/performance whenever the filters change (debounced, so typing a balance is one request). */
export function useAnalytics(query: AnalyticsQuery): UseAnalytics {
  const key = keyOf(query)
  const [data, setData] = useState<AnalyticsPerformanceResponse | null>(() => cache.get(key) ?? null)
  const [loading, setLoading] = useState(!cache.has(key))
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryRef = useRef(query)
  queryRef.current = query
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback((k: string) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setRefreshing(true)
    getAnalyticsPerformance(queryRef.current, controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) return
        cache.set(k, payload)
        setData(payload)
        setError(null)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Could not load analytics.')
      })
      .finally(() => {
        if (controller.signal.aborted) return
        setLoading(false)
        setRefreshing(false)
      })
  }, [])

  useEffect(() => {
    const cached = cache.get(key)
    if (cached) {
      setData(cached)
      setLoading(false)
    } else {
      setLoading(true)
    }
    const timer = setTimeout(() => load(key), 300)
    return () => {
      clearTimeout(timer)
      inFlight.current?.abort()
    }
  }, [key, load])

  const refresh = useCallback(() => load(key), [key, load])
  return { data, loading, refreshing, error, refresh }
}

export function clearAnalyticsCache(): void {
  cache.clear()
}
