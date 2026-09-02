import { useCallback, useEffect, useRef, useState } from 'react'
import { getMacroAssets, getMacroCurrencies, getMacroEvents, getMacroOverview } from '../api/macro'
import type {
  MacroAssetsResponse,
  MacroCurrenciesResponse,
  MacroEventsResponse,
  MacroOverviewResponse,
} from '../types/macro'
import type { LoadState } from './useWatchlist'

interface MacroData {
  overview: MacroOverviewResponse | null
  currencies: MacroCurrenciesResponse | null
  assets: MacroAssetsResponse | null
  events: MacroEventsResponse | null
}

interface UseMacroResult extends MacroData {
  state: LoadState
  error: string | null
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 120_000

/**
 * One batched fetch of the four macro resources (overview / currencies / assets /
 * events) via Promise.allSettled — not a per-section fan-out. Slow 2-min
 * hidden-paused refresh; AbortController; last-good retained.
 */
export function useMacroIntelligence(): UseMacroResult {
  const [data, setData] = useState<MacroData>({ overview: null, currencies: null, assets: null, events: null })
  const [state, setState] = useState<LoadState>('loading')
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
      const s = controller.signal
      if (hasData.current) setRefreshing(true)

      Promise.allSettled([
        getMacroOverview(s),
        getMacroCurrencies(s),
        getMacroAssets(s),
        getMacroEvents({ window: 'all', limit: 300 }, s),
      ]).then((res) => {
        if (disposed || s.aborted) return
        const [ov, cur, as, ev] = res
        setData((prev) => ({
          overview: ov.status === 'fulfilled' ? ov.value : prev.overview,
          currencies: cur.status === 'fulfilled' ? cur.value : prev.currencies,
          assets: as.status === 'fulfilled' ? as.value : prev.assets,
          events: ev.status === 'fulfilled' ? ev.value : prev.events,
        }))
        const anyOk = res.some((r) => r.status === 'fulfilled')
        const firstErr = res.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined
        if (anyOk) {
          setState('ready')
          hasData.current = true
          setError(firstErr ? String(firstErr.reason?.message ?? firstErr.reason) : null)
        } else {
          setError(firstErr ? String(firstErr.reason?.message ?? firstErr.reason) : 'Macro service unavailable')
          if (!hasData.current) setState('error')
        }
        setRefreshing(false)
      })
    }

    load()
    const timer = window.setInterval(() => { if (!document.hidden) load() }, REFRESH_MS)
    return () => {
      disposed = true
      window.clearInterval(timer)
      controller?.abort()
    }
  }, [nonce])

  return { ...data, state, error, refreshing, refetch }
}
