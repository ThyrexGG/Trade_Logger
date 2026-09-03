import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getGoldBaseline,
  getHistoricalCoverage,
  getPairRanking,
  getStrategies,
} from '../api/strategyResearch'
import type {
  GoldBaselineResponse,
  HistoricalCoverageResponse,
  PairRankingResponse,
  StrategiesResponse,
} from '../types/strategyResearch'
import type { LoadState } from './useWatchlist'

/**
 * One batched read of the Phase 69/70 research surface — historical coverage,
 * strategy definitions, the persisted pair-ranking artifact, and the Gold
 * baseline. `Promise.allSettled`, not a fan-out. Read-only.
 */
export function useStrategyDiscovery() {
  const [coverage, setCoverage] = useState<HistoricalCoverageResponse | null>(null)
  const [strategies, setStrategies] = useState<StrategiesResponse | null>(null)
  const [ranking, setRanking] = useState<PairRankingResponse | null>(null)
  const [gold, setGold] = useState<GoldBaselineResponse | null>(null)
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
      getHistoricalCoverage(s),
      getStrategies(s),
      getPairRanking(s),
      getGoldBaseline(s),
    ]).then((res) => {
      if (disposed || s.aborted) return
      const [cov, str, rank, g] = res
      if (cov.status === 'fulfilled') setCoverage(cov.value)
      if (str.status === 'fulfilled') setStrategies(str.value)
      if (rank.status === 'fulfilled') setRanking(rank.value)
      if (g.status === 'fulfilled') setGold(g.value)

      const anyOk = res.some((r) => r.status === 'fulfilled')
      if (anyOk) {
        setState('ready')
        hasData.current = true
        setError(null)
      } else {
        const first = res.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined
        setError(String(first?.reason?.message ?? first?.reason ?? 'request failed'))
        if (!hasData.current) setState('error')
      }
    })

    return () => {
      disposed = true
      controller.abort()
    }
  }, [nonce])

  return { coverage, strategies, ranking, gold, state, error, refetch }
}
