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
 * Read of the Phase 69/70 research surface — historical coverage, strategy
 * definitions, the persisted pair-ranking artifact, and the Gold baseline.
 *
 * Each of the four calls is applied to state the moment it resolves — a slow
 * or hanging call (historical coverage against a remote store can take tens of
 * seconds) never blocks the fast ones. The page becomes usable as soon as the
 * first result lands. Read-only.
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

    let settled = 0
    let anyOk = false
    const done = (ok: boolean, reason?: unknown) => {
      if (disposed || s.aborted) return
      settled += 1
      if (ok) {
        anyOk = true
        hasData.current = true
        setState('ready')
        setError(null)
      } else if (!anyOk) {
        setError(String((reason as Error)?.message ?? reason ?? 'request failed'))
        if (settled === 4 && !hasData.current) setState('error')
      }
    }

    getPairRanking(s).then((v) => { if (!disposed && !s.aborted) setRanking(v); done(true) }, (e) => done(false, e))
    getStrategies(s).then((v) => { if (!disposed && !s.aborted) setStrategies(v); done(true) }, (e) => done(false, e))
    getGoldBaseline(s).then((v) => { if (!disposed && !s.aborted) setGold(v); done(true) }, (e) => done(false, e))
    getHistoricalCoverage(s).then((v) => { if (!disposed && !s.aborted) setCoverage(v); done(true) }, (e) => done(false, e))

    return () => {
      disposed = true
      controller.abort()
    }
  }, [nonce])

  return { coverage, strategies, ranking, gold, state, error, refetch }
}
