import { useCallback, useEffect, useRef, useState } from 'react'
import { getAssetProfile } from '../api/intelligence'
import type { AssetProfile } from '../types/intelligence'
import type { LoadState } from './useWatchlist'

interface UseAssetProfileResult {
  state: LoadState
  data: AssetProfile | null
  error: string | null
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 60_000
const cache = new Map<string, AssetProfile>()

/**
 * Fetches one asset profile for the active symbol only — never for the whole
 * universe. Race-safe: a stale response for a previously-selected symbol is
 * discarded. Cached per symbol so back/forward navigation is instant.
 */
export function useAssetProfile(symbol: string | null): UseAssetProfileResult {
  const [state, setState] = useState<LoadState>(symbol ? 'loading' : 'error')
  const [data, setData] = useState<AssetProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const requestId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    if (!symbol) {
      setState('error')
      setData(null)
      return
    }

    const cached = cache.get(symbol)
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
      if (cache.has(symbol)) setRefreshing(true)

      getAssetProfile(symbol, controller.signal)
        .then((payload) => {
          if (id !== requestId.current || payload.symbol !== symbol) return
          cache.set(symbol, payload)
          setData(payload)
          setError(null)
          setState('ready')
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted || id !== requestId.current) return
          const message = err instanceof Error ? err.message : 'Unknown error'
          setError(message)
          if (!cache.has(symbol)) {
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
