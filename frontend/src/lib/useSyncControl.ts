import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getSyncStatus,
  runSyncNow,
  setSyncAuto,
  type SyncStatusResponse,
} from '../api/system'

interface UseSyncControlResult {
  status: SyncStatusResponse | null
  /** a "Sync now" cycle is in flight (this tab) */
  syncing: boolean
  busyAuto: boolean
  error: string | null
  syncNow: () => Promise<void>
  toggleAuto: () => void
}

/**
 * Drives the in-process broker-sync service (GET/POST/PUT /api/system/sync).
 * "Sync now" runs one cycle and resolves when it finishes; the auto toggle
 * flips the persisted background loop. Polls status every 20s so the auto
 * state and last-run stay fresh across tabs.
 */
export function useSyncControl(onSynced?: () => void): UseSyncControlResult {
  const [status, setStatus] = useState<SyncStatusResponse | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [busyAuto, setBusyAuto] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const onSyncedRef = useRef(onSynced)
  onSyncedRef.current = onSynced

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setInterval> | undefined
    const poll = () => {
      getSyncStatus(controller.signal)
        .then(setStatus)
        .catch(() => {})
    }
    poll()
    timer = setInterval(poll, 20_000)
    return () => {
      controller.abort()
      if (timer) clearInterval(timer)
    }
  }, [])

  const syncNow = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const r = await runSyncNow()
      setStatus(r)
      const runs = Array.isArray(r.ran) ? r.ran : r.ran ? [r.ran] : []
      if (runs.some((x) => x.ok)) onSyncedRef.current?.()
      const failed = runs.find((x) => !x.ok)
      if (failed) setError(failed.errors[0] ?? 'Sync completed with errors')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }, [])

  const toggleAuto = useCallback(() => {
    if (!status) return
    setBusyAuto(true)
    setError(null)
    setSyncAuto(!status.auto_enabled)
      .then(setStatus)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Could not change auto-sync'),
      )
      .finally(() => setBusyAuto(false))
  }, [status])

  return { status, syncing, busyAuto, error, syncNow, toggleAuto }
}
