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
    const errors: string[] = []
    try {
      // The cloud API call covers Capital.com (and MT5 wherever the backend
      // actually has MT5 access). The desktop bridge covers the other case:
      // this page is talking to the cloud backend on Render, which can never
      // reach this PC's MT5 terminal (Windows-only library) -- without this,
      // "Sync now" would silently do nothing for MT5 and only the 15-minute
      // scheduled task would catch new trades. Outside the desktop app, or on
      // any machine but the owner's, the bridge is absent/skipped and this is
      // just the cloud sync alone, same as before.
      const [cloudResult, mt5Result] = await Promise.allSettled([
        runSyncNow(),
        window.tradelogger?.triggerMT5SyncNow?.() ?? Promise.resolve(null),
      ])

      if (cloudResult.status === 'fulfilled') {
        const r = cloudResult.value
        setStatus(r)
        const runs = Array.isArray(r.ran) ? r.ran : r.ran ? [r.ran] : []
        if (runs.some((x) => x.ok)) onSyncedRef.current?.()
        const failed = runs.find((x) => !x.ok)
        if (failed) errors.push(failed.errors[0] ?? 'Sync completed with errors')
      } else {
        errors.push(cloudResult.reason instanceof Error ? cloudResult.reason.message : 'Sync failed')
      }

      const mt5 = mt5Result.status === 'fulfilled' ? mt5Result.value : null
      if (mt5 && !mt5.skipped) {
        if (mt5.ok) onSyncedRef.current?.()
        else errors.push(`MT5: ${mt5.error || 'sync failed'}`)
      }

      if (errors.length) setError(errors.join(' · '))
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
