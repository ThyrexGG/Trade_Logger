import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState } from 'react-native'
import { getPositions } from './api/positions'
import { runSyncNow } from './api/system'
import type { PositionsResponse } from './types/positions'

const REFRESH_MS = 45_000

interface UsePositions {
  data: PositionsResponse | null
  /** first load, no data yet */
  loading: boolean
  /** a pull-to-refresh / manual reload is in flight */
  refreshing: boolean
  error: string | null
  refresh: () => void
  /** a "Sync now" cycle is in flight */
  syncing: boolean
  /** error text from the last sync cycle, if it failed */
  syncError: string | null
  syncNow: () => Promise<void>
}

/**
 * Open positions with a 45 s poll (paused in the background, refreshed the
 * moment the app returns to the foreground) plus a Sync-now action that pulls
 * from the broker and then reloads. Keeps showing the last good data if a
 * refresh fails.
 */
export function usePositions(): UsePositions {
  const [data, setData] = useState<PositionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback((manual: boolean) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    if (manual) setRefreshing(true)
    return getPositions(controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) return
        setData(payload)
        setError(null)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Could not load positions.')
      })
      .finally(() => {
        if (inFlight.current !== controller) return
        setLoading(false)
        setRefreshing(false)
      })
  }, [])

  useEffect(() => {
    void load(false)
    let timer: ReturnType<typeof setInterval> | undefined = setInterval(() => void load(false), REFRESH_MS)
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') {
        void load(false)
        if (!timer) timer = setInterval(() => void load(false), REFRESH_MS)
      } else if (timer) {
        clearInterval(timer)
        timer = undefined
      }
    })
    return () => {
      sub.remove()
      if (timer) clearInterval(timer)
      inFlight.current?.abort()
    }
  }, [load])

  const refresh = useCallback(() => void load(true), [load])

  const syncNow = useCallback(async () => {
    setSyncing(true)
    setSyncError(null)
    try {
      const r = await runSyncNow()
      const runs = Array.isArray(r.ran) ? r.ran : r.ran ? [r.ran] : []
      const failed = runs.find((x) => !x.ok)
      if (failed) setSyncError(failed.errors[0] ?? 'Sync finished with errors.')
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : 'Sync failed.')
    } finally {
      setSyncing(false)
      await load(true)
    }
  }, [load])

  return { data, loading, refreshing, error, refresh, syncing, syncError, syncNow }
}
