import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState } from 'react-native'
import type { JournalUpdateRequest } from '../types/journal'

export interface AnnotationFields {
  setup_tag: string
  notes: string
  chart_snapshot_url: string
  rating: number
}

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

const DEBOUNCE_MS = 900

/** Tag and link are stored trimmed server-side; notes keep their whitespace. */
function normalize(f: AnnotationFields): AnnotationFields {
  return { ...f, setup_tag: f.setup_tag.trim(), chart_snapshot_url: f.chart_snapshot_url.trim() }
}

function diff(next: AnnotationFields, base: AnnotationFields): JournalUpdateRequest {
  const n = normalize(next)
  const out: JournalUpdateRequest = {}
  if (n.setup_tag !== base.setup_tag) out.setup_tag = n.setup_tag
  if (n.notes !== base.notes) out.notes = n.notes
  if (n.chart_snapshot_url !== base.chart_snapshot_url) out.chart_snapshot_url = n.chart_snapshot_url
  if (n.rating !== base.rating) out.rating = n.rating
  return out
}

/**
 * Debounced autosave for the journal editor, mirroring the web: only the
 * fields that actually changed are PATCHed, ~0.9 s after the last keystroke,
 * and pending edits are flushed when the screen closes or the app goes to
 * the background so nothing typed is lost.
 */
export function useAutosave(
  initial: AnnotationFields,
  save: (patch: JournalUpdateRequest) => Promise<void>,
) {
  const [fields, setFields] = useState<AnnotationFields>(initial)
  const [status, setStatus] = useState<SaveStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const latest = useRef(initial)
  const baseline = useRef(normalize(initial))
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const inFlight = useRef(false)
  const mounted = useRef(true)
  const saveRef = useRef(save)
  saveRef.current = save

  const flush = useCallback(async () => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = undefined
    }
    if (inFlight.current) {
      // A save is running; try again right after it finishes so the newest text wins.
      timer.current = setTimeout(() => void flush(), 300)
      return
    }
    const patch = diff(latest.current, baseline.current)
    if (Object.keys(patch).length === 0) return
    inFlight.current = true
    if (mounted.current) {
      setStatus('saving')
      setError(null)
    }
    try {
      await saveRef.current(patch)
      // Only the fields we just sent become the new baseline — newer typing stays "dirty".
      baseline.current = { ...baseline.current, ...patch } as AnnotationFields
      inFlight.current = false
      const stillDirty = Object.keys(diff(latest.current, baseline.current)).length > 0
      if (mounted.current) setStatus(stillDirty ? 'saving' : 'saved')
      // The user kept typing while this save was in flight — send the newer text too.
      if (stillDirty && !timer.current) timer.current = setTimeout(() => void flush(), DEBOUNCE_MS)
    } catch (err) {
      // No automatic retry on failure (a 404/422 would loop forever): the next edit
      // or a tap on the error line tries again.
      inFlight.current = false
      if (mounted.current) {
        setStatus('error')
        setError(err instanceof Error ? err.message : 'Save failed.')
      }
    }
  }, [])

  const update = useCallback(
    (patch: Partial<AnnotationFields>) => {
      const next = { ...latest.current, ...patch }
      latest.current = next
      setFields(next)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => void flush(), DEBOUNCE_MS)
    },
    [flush],
  )

  useEffect(() => {
    mounted.current = true
    const sub = AppState.addEventListener('change', (s) => {
      if (s !== 'active') void flush()
    })
    return () => {
      mounted.current = false
      sub.remove()
      void flush() // leaving the screen: push out whatever is pending
    }
  }, [flush])

  return { fields, update, status, error, retry: flush }
}
