import { useEffect, useState } from 'react'
import { getCarryForward } from '../api/cryptoCarry'
import type { CarryForwardResponse } from '../types/cryptoCarry'
import type { LoadState } from './useWatchlist'

// Shared across consumers for the session — it's a weekly-updated artifact.
let cached: CarryForwardResponse | null = null

/** Reads the Phase 98 crypto funding-carry forward-evidence artifact once. */
export function useCarryForward() {
  const [data, setData] = useState<CarryForwardResponse | null>(cached)
  const [state, setState] = useState<LoadState>(cached ? 'ready' : 'loading')

  useEffect(() => {
    if (cached) return
    const c = new AbortController()
    getCarryForward(c.signal)
      .then((r) => {
        cached = r
        setData(r)
        setState('ready')
      })
      .catch(() => {
        if (!c.signal.aborted) setState('error')
      })
    return () => c.abort()
  }, [])

  return { data, state }
}
