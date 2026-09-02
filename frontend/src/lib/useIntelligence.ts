import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from 'react'
import {
  getEconomicHeatmap,
  getIntelligenceSummary,
  getOpportunityMap,
} from '../api/intelligence'
import type {
  EconomicHeatmapResponse,
  IntelligenceSummary,
  OpportunityMapResponse,
} from '../types/intelligence'
import type { LoadState } from './useWatchlist'

export interface Section<T> {
  state: LoadState
  data: T | null
  error: string | null
}

interface CommandCenter {
  summary: Section<IntelligenceSummary>
  opportunity: Section<OpportunityMapResponse>
  heatmap: Section<EconomicHeatmapResponse>
  refreshing: boolean
  refetch: () => void
}

const REFRESH_MS = 60_000

// Module-level cache so navigating away and back is instant (a background
// refresh still runs). Not a substitute for the backend cache.
const cache: {
  summary: IntelligenceSummary | null
  opportunity: OpportunityMapResponse | null
  heatmap: EconomicHeatmapResponse | null
} = { summary: null, opportunity: null, heatmap: null }

const initSection = <T>(cached: T | null): Section<T> =>
  cached
    ? { state: 'ready', data: cached, error: null }
    : { state: 'loading', data: null, error: null }

/**
 * Coordinated fetch of the three command-center endpoints via Promise.allSettled
 * — each section loads and fails independently, so one dead endpoint never
 * blanks the page. The fetch group runs once on mount, on an explicit refetch,
 * and on a slow interval (paused while the tab is hidden). Exactly three
 * requests per cycle — no per-section or per-render refetching.
 */
export function useIntelligenceCommandCenter(): CommandCenter {
  const [summary, setSummary] = useState<Section<IntelligenceSummary>>(() =>
    initSection(cache.summary),
  )
  const [opportunity, setOpportunity] = useState<Section<OpportunityMapResponse>>(
    () => initSection(cache.opportunity),
  )
  const [heatmap, setHeatmap] = useState<Section<EconomicHeatmapResponse>>(() =>
    initSection(cache.heatmap),
  )
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const controllerRef = useRef<AbortController | null>(null)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    const settle = <T>(
      setter: Dispatch<SetStateAction<Section<T>>>,
      store: (v: T) => void,
      signal: AbortSignal,
    ) => ({
      ok: (data: T) => {
        if (signal.aborted) return
        store(data)
        setter({ state: 'ready', data, error: null })
      },
      fail: (err: unknown) => {
        if (signal.aborted) return
        const message = err instanceof Error ? err.message : 'Unknown error'
        setter((prev) =>
          prev.data
            ? { ...prev, error: message }
            : { state: 'error', data: null, error: message },
        )
      },
    })

    const load = () => {
      controllerRef.current?.abort()
      const controller = new AbortController()
      controllerRef.current = controller
      const signal = controller.signal
      if (cache.summary || cache.opportunity || cache.heatmap) {
        setRefreshing(true)
      }

      const s = settle<IntelligenceSummary>(
        setSummary,
        (v) => (cache.summary = v),
        signal,
      )
      const o = settle<OpportunityMapResponse>(
        setOpportunity,
        (v) => (cache.opportunity = v),
        signal,
      )
      const h = settle<EconomicHeatmapResponse>(
        setHeatmap,
        (v) => (cache.heatmap = v),
        signal,
      )

      Promise.allSettled([
        getIntelligenceSummary(signal).then(s.ok, s.fail),
        getOpportunityMap(signal).then(o.ok, o.fail),
        getEconomicHeatmap(signal).then(h.ok, h.fail),
      ]).finally(() => {
        if (!signal.aborted) setRefreshing(false)
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
      controllerRef.current?.abort()
    }
  }, [nonce])

  return { summary, opportunity, heatmap, refreshing, refetch }
}
