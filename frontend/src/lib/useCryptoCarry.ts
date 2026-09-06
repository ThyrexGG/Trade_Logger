import { useEffect, useState } from 'react'
import {
  getCarryForward,
  getFundingCarry,
  getPortfolioConstruction,
} from '../api/cryptoCarry'
import type {
  CarryForwardResponse,
  FundingCarryResponse,
  PortfolioConstructionResponse,
} from '../types/cryptoCarry'
import type { LoadState } from './useWatchlist'

/**
 * One read of the three crypto funding-carry artifacts (Phases 96 / 97 / 98).
 * Each is applied to state as it resolves; the page is usable as soon as the
 * forward-evidence call (the fast one) lands.
 */
export function useCryptoCarry() {
  const [forward, setForward] = useState<CarryForwardResponse | null>(null)
  const [book, setBook] = useState<PortfolioConstructionResponse | null>(null)
  const [edge, setEdge] = useState<FundingCarryResponse | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    const c = new AbortController()
    let ok = false
    let settled = 0
    const done = (good: boolean, e?: unknown) => {
      if (c.signal.aborted) return
      settled += 1
      if (good) {
        ok = true
        setState('ready')
        setError(null)
      } else if (!ok) {
        setError(e instanceof Error ? e.message : 'Failed to load')
        if (settled === 3) setState('error')
      }
    }
    getCarryForward(c.signal).then((v) => { if (!c.signal.aborted) setForward(v); done(true) }, (e) => done(false, e))
    getPortfolioConstruction(c.signal).then((v) => { if (!c.signal.aborted) setBook(v); done(true) }, (e) => done(false, e))
    getFundingCarry(c.signal).then((v) => { if (!c.signal.aborted) setEdge(v); done(true) }, (e) => done(false, e))
    return () => c.abort()
  }, [nonce])

  return { forward, book, edge, state, error, refetch: () => setNonce((n) => n + 1) }
}
