import { useCallback, useEffect, useRef, useState } from 'react'
import { getMarketSnapshot } from '../api/market'
import type { MarketSnapshot } from '../types/market'
import type { LoadState } from './useWatchlist'

interface UseMarketSnapshotResult {
  state: LoadState
  data: MarketSnapshot | null
  error: string | null
  /** Showing a cached snapshot while a fresh one loads for the same symbol. */
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 10_000

/**
 * Fetches GET /api/market/snapshot/{symbol} for the selected symbol only.
 *
 * Race-safe: every fetch bumps a request id and carries an AbortController; a
 * result is applied only if it is the newest request AND still matches the
 * selected symbol, so rapid switching (USDJPY -> EURUSD -> GBPUSD) can never
 * show stale data. A small in-memory cache makes re-selecting a symbol instant
 * while the background refresh runs.
 */
export function useMarketSnapshot(symbol: string | null): UseMarketSnapshotResult {
  const [state, setState] = useState<LoadState>(symbol ? 'loading' : 'error')
  const [data, setData] = useState<MarketSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)

  const cache = useRef<Map<string, MarketSnapshot>>(new Map())
  const requestId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    if (!symbol) {
      setState('error')
      setData(null)
      return
    }

    const cached = cache.current.get(symbol)
    if (cached) {
      setData(cached)
      setState('ready')
      setRefreshing(true)
    } else {
      setData(null)
      setState('loading')
      setRefreshing(false)
    }
    setError(null)

    const load = () => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      const id = ++requestId.current
      if (cache.current.has(symbol)) setRefreshing(true)

      getMarketSnapshot(symbol, controller.signal)
        .then((payload) => {
          if (id !== requestId.current || payload.symbol !== symbol) return
          cache.current.set(symbol, payload)
          setData(payload)
          setError(null)
          setState('ready')
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted || id !== requestId.current) return
          setError(err instanceof Error ? err.message : 'Unknown error')
          if (!cache.current.has(symbol)) {
            setData(null)
            setState('error')
          }
        })
        .finally(() => {
          if (id === requestId.current) setRefreshing(false)
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
  }, [symbol, nonce])

  return { state, data, error, refreshing, refetch }
}
