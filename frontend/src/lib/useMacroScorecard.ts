import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getMacroHeatmap,
  getMacroHeatmapIndex,
  getMacroScorecard,
  getMacroScorecardHistory,
} from '../api/macro'
import type {
  MacroHeatmapIndexResponse,
  MacroHeatmapResponse,
  MacroScorecardHistoryResponse,
  MacroScorecardResponse,
} from '../types/macro'
import type { LoadState } from './useWatchlist'

/**
 * One batched fetch of the scorecard + its history for the selected instrument
 * (Promise.allSettled, not a fan-out). Re-fetches when `instrument` changes.
 * AbortController + disposed guard; last-good retained on error.
 */
export function useMacroScorecard(instrument: string) {
  const [scorecard, setScorecard] = useState<MacroScorecardResponse | null>(null)
  const [history, setHistory] = useState<MacroScorecardHistoryResponse | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const hasData = useRef(false)

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let disposed = false
    const controller = new AbortController()
    const s = controller.signal
    if (!hasData.current) setState('loading')

    Promise.allSettled([
      getMacroScorecard(instrument, s),
      getMacroScorecardHistory(instrument, 90, s),
    ]).then((res) => {
      if (disposed || s.aborted) return
      const [sc, hi] = res
      if (sc.status === 'fulfilled') setScorecard(sc.value)
      if (hi.status === 'fulfilled') setHistory(hi.value)
      if (sc.status === 'fulfilled') {
        setState('ready')
        hasData.current = true
        setError(null)
      } else {
        setError(String(sc.reason?.message ?? sc.reason))
        if (!hasData.current) setState('error')
      }
    })

    return () => {
      disposed = true
      controller.abort()
    }
  }, [instrument, nonce])

  return { scorecard, history, state, error, refetch }
}

/** Heatmap index + the selected country's grid. */
export function useMacroHeatmap(country: string) {
  const [index, setIndex] = useState<MacroHeatmapIndexResponse | null>(null)
  const [heatmap, setHeatmap] = useState<MacroHeatmapResponse | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)
  const hasData = useRef(false)

  useEffect(() => {
    let disposed = false
    const controller = new AbortController()
    const s = controller.signal
    if (!hasData.current) setState('loading')

    Promise.allSettled([getMacroHeatmapIndex(s), getMacroHeatmap(country, s)]).then((res) => {
      if (disposed || s.aborted) return
      const [ix, hm] = res
      if (ix.status === 'fulfilled') setIndex(ix.value)
      if (hm.status === 'fulfilled') {
        setHeatmap(hm.value)
        setState('ready')
        hasData.current = true
        setError(null)
      } else {
        setError(String(hm.reason?.message ?? hm.reason))
        if (!hasData.current) setState('error')
      }
    })

    return () => {
      disposed = true
      controller.abort()
    }
  }, [country])

  return { index, heatmap, state, error }
}
