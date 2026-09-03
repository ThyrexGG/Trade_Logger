import { useCallback, useEffect, useRef, useState } from 'react'
import { getTradeSetup, getTradeSetups } from '../api/tradeSetup'
import type { TradeSetup, TradeSetupListResponse } from '../types/tradeSetup'
import type { LoadState } from './useWatchlist'

/**
 * The compact setup list for every instrument + the full evaluation for the
 * selected one. `Promise.allSettled`, AbortController, last-good retained.
 */
export function useTradeSetup(asset: string) {
  const [list, setList] = useState<TradeSetupListResponse | null>(null)
  const [setup, setSetup] = useState<TradeSetup | null>(null)
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

    Promise.allSettled([getTradeSetups(s), getTradeSetup(asset, s)]).then((res) => {
      if (disposed || s.aborted) return
      const [l, one] = res
      if (l.status === 'fulfilled') setList(l.value)
      if (one.status === 'fulfilled') {
        setSetup(one.value)
        setState('ready')
        hasData.current = true
        setError(null)
      } else {
        setError(String(one.reason?.message ?? one.reason))
        if (!hasData.current) setState('error')
      }
    })

    return () => {
      disposed = true
      controller.abort()
    }
  }, [asset, nonce])

  return { list, setup, state, error, refetch }
}
