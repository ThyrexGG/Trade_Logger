import { useCallback, useEffect, useRef, useState } from 'react'
import type { LoadState } from './useWatchlist'

interface CacheSlot {
  data: unknown
  error: string | null
  at: number
}

// One shared slot per resource key — module-level, so every mount, every
// page revisit, and every component reading the same key reuses the last
// fetch instead of showing a fresh skeleton. This is the app's caching
// layer: no server round-trip is needed to redraw a page you've already
// loaded once this session; a background refresh keeps it honest.
const cache = new Map<string, CacheSlot>()

export interface CachedResource<T> {
  state: LoadState
  data: T | null
  error: string | null
  /** True while a background refresh runs over data that's already on screen. */
  refreshing: boolean
  refetch: () => void
  /** Apply an authoritative payload locally (e.g. a PATCH response) without a refetch — optimistic UI with no wait. */
  setLocal: (updater: (prev: T | null) => T | null) => void
}

export interface UseCachedResourceOptions {
  /** Background refresh interval in ms. Omit for on-demand/debounce-only (no polling). */
  refreshMs?: number
  /** A cache hit younger than this serves a mount / key switch with no refetch. Default 12s. */
  mountReuseMs?: number
  /** Wait this long after `key` last changed before fetching — collapses a burst of filter changes into one request. Default 0 (fetch immediately). */
  debounceMs?: number
  /** Window event names that force an immediate background revalidate (e.g. a broker sync just landed new rows). */
  revalidateOn?: string[]
}

/**
 * Shared, module-cached, race-safe (AbortController) GET resource with
 * stale-while-revalidate semantics: a cache hit renders **instantly** — no
 * skeleton, no spinner — while a background refresh quietly confirms it's
 * still current; a genuine miss (nothing cached yet) shows the normal
 * loading state once. This is the one place this behaviour is implemented;
 * every hook that wants "don't make the user wait for the server" calls it
 * instead of hand-rolling its own fetch/state effect.
 */
export function useCachedResource<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: UseCachedResourceOptions = {},
): CachedResource<T> {
  const { refreshMs = 0, mountReuseMs = 12_000, debounceMs = 0, revalidateOn = [] } = options
  const slot = cache.get(key)
  const [data, setData] = useState<T | null>((slot?.data as T) ?? null)
  const [state, setState] = useState<LoadState>(slot?.data ? 'ready' : 'loading')
  const [error, setError] = useState<string | null>(slot?.error ?? null)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const hasData = useRef(Boolean(slot?.data))

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  const setLocal = useCallback(
    (updater: (prev: T | null) => T | null) => {
      setData((prev) => {
        const next = updater(prev)
        if (next != null) {
          const cur = cache.get(key)
          cache.set(key, { data: next, error: cur?.error ?? null, at: Date.now() })
          hasData.current = true
        }
        return next
      })
    },
    [key],
  )

  useEffect(() => {
    let disposed = false
    let controller: AbortController | null = null
    let debounceTimer: ReturnType<typeof setTimeout> | undefined

    // Switching to a DIFFERENT key that already has a fresh cached entry
    // (e.g. toggling a filter back to what it was a moment ago) should also
    // render instantly rather than waiting for this effect's own fetch.
    const primed = cache.get(key)
    if ((primed?.data ?? null) !== data) {
      setData((primed?.data as T) ?? null)
      setState(primed?.data ? 'ready' : 'loading')
      hasData.current = Boolean(primed?.data)
    }

    const load = () => {
      controller?.abort()
      controller = new AbortController()
      const signal = controller.signal
      if (hasData.current) setRefreshing(true)
      fetcher(signal)
        .then((payload) => {
          if (disposed || signal.aborted) return
          cache.set(key, { data: payload, error: null, at: Date.now() })
          setData(payload)
          setError(null)
          setState('ready')
          hasData.current = true
        })
        .catch((err: unknown) => {
          if (disposed || signal.aborted) return
          const message = err instanceof Error ? err.message : 'Unknown error'
          const prev = cache.get(key)
          cache.set(key, { data: prev?.data ?? null, error: message, at: Date.now() })
          setError(message)
          if (!hasData.current) setState('error')
        })
        .finally(() => {
          if (!disposed && !signal.aborted) setRefreshing(false)
        })
    }

    const fresh = primed?.data != null && Date.now() - primed.at < mountReuseMs
    const kickoff = () => {
      if (nonce > 0 || !fresh) load()
    }
    if (debounceMs > 0) {
      debounceTimer = setTimeout(kickoff, debounceMs)
    } else {
      kickoff()
    }

    const timer =
      refreshMs > 0
        ? window.setInterval(() => {
            if (!document.hidden) load()
          }, refreshMs)
        : undefined
    const onVisible = () => {
      const c = cache.get(key)
      if (!document.hidden && (!c || Date.now() - c.at > mountReuseMs)) load()
    }
    document.addEventListener('visibilitychange', onVisible)
    const revalidateHandlers = revalidateOn.map((evt) => {
      const handler = () => load()
      window.addEventListener(evt, handler)
      return { evt, handler }
    })

    return () => {
      disposed = true
      if (debounceTimer) clearTimeout(debounceTimer)
      if (timer) window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      revalidateHandlers.forEach(({ evt, handler }) => window.removeEventListener(evt, handler))
      controller?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce])

  return { state, data, error, refreshing, refetch, setLocal }
}
