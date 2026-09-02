import { useCallback, useEffect, useRef, useState } from 'react'
import { getWatchlist } from '../api/market'
import type { WatchlistItem } from '../types/market'

export type LoadState = 'loading' | 'ready' | 'error'

interface UseWatchlistResult {
  state: LoadState
  items: WatchlistItem[]
  /** Backend-provided response timestamp (ISO). Never synthesized here. */
  updatedAt: string | null
  error: string | null
  /** True when a background refresh is running over already-loaded data. */
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 20_000

/**
 * Loads GET /api/watchlist once, then refreshes on a modest interval (paused
 * while the tab is hidden). One request for the whole list — never per symbol.
 * A failed background refresh keeps the last good data and surfaces `error`.
 */
export function useWatchlist(): UseWatchlistResult {
  const [state, setState] = useState<LoadState>('loading')
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const inFlight = useRef<AbortController | null>(null)
  const hasData = useRef(false)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    const load = () => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      if (hasData.current) setRefreshing(true)

      getWatchlist(controller.signal)
        .then((payload) => {
          if (controller.signal.aborted) return
          setItems(payload.items)
          setUpdatedAt(payload.timestamp)
          setError(null)
          setState('ready')
          hasData.current = true
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          setError(err instanceof Error ? err.message : 'Unknown error')
          if (!hasData.current) setState('error')
        })
        .finally(() => {
          if (!controller.signal.aborted) setRefreshing(false)
        })
    }

    load()
    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, REFRESH_MS)
    const onVisible = () => {
      if (!document.hidden) load()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      inFlight.current?.abort()
    }
  }, [nonce])

  return { state, items, updatedAt, error, refreshing, refetch }
}
