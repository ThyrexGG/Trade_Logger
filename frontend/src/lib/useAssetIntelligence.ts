import { useCallback, useEffect, useRef, useState } from 'react'
import { getAssetIntelligence } from '../api/intelligence'
import type { AssetIntelligence } from '../types/intelligence'
import type { LoadState } from './useWatchlist'

interface UseAssetIntelligenceResult {
  state: LoadState
  data: AssetIntelligence | null
  error: string | null
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 60_000
const cache = new Map<string, AssetIntelligence>()

/**
 * Fetches the canonical Phase-67 evidence fusion snapshot for one asset. Race-
 * safe: a stale response for a previously-selected symbol is discarded. Cached
 * per (symbol, asOf) so navigation is instant. Read-only — nothing here can
 * execute anything.
 */
export function useAssetIntelligence(
  symbol: string | null,
  asOf?: string,
): UseAssetIntelligenceResult {
  const key = symbol ? `${symbol}::${asOf ?? 'live'}` : null
  const [state, setState] = useState<LoadState>(symbol ? 'loading' : 'error')
  const [data, setData] = useState<AssetIntelligence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const requestId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    if (!symbol || !key) {
      setState('error')
      setData(null)
      return
    }

    const cached = cache.get(key)
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

      getAssetIntelligence(symbol, { asOf, signal: controller.signal })
        .then((payload) => {
          if (id !== requestId.current || payload.asset !== symbol.toUpperCase()) return
          cache.set(key, payload)
          setData(payload)
          setError(null)
          setState('ready')
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted || id !== requestId.current) return
          const message = err instanceof Error ? err.message : 'Unknown error'
          setError(message)
          if (!cache.has(key)) {
            setData(null)
            setState('error')
          }
        })
        .finally(() => {
          if (id === requestId.current) setRefreshing(false)
        })
    }

    load()
    // A historical (as-of) snapshot is immutable — no polling.
    if (asOf) {
      return () => inFlight.current?.abort()
    }
    const timer = window.setInterval(() => {
      if (!document.hidden) load()
    }, REFRESH_MS)
    return () => {
      window.clearInterval(timer)
      inFlight.current?.abort()
    }
  }, [symbol, key, asOf, nonce])

  return { state, data, error, refreshing, refetch }
}
