import { useCallback, useEffect, useRef, useState } from 'react'
import type { JournalScreenshotMeta } from '../../types/operations'
import {
  deleteJournalScreenshot,
  getJournalScreenshots,
  journalScreenshotSrc,
  uploadJournalScreenshot,
} from '../../api/operations'

const ACCEPT = 'image/png,image/jpeg,image/webp,image/gif'
const MAX_MB = 4

/**
 * Screenshot attachments for one closed trade's journal entry. Upload via the
 * button, drag-drop, or paste (Ctrl+V a TradingView capture). Images are stored
 * in the DB by the backend; this only ever touches the annotation endpoints.
 */
export function ScreenshotStrip({
  tradeId,
  compact = false,
  onCountChange,
}: {
  tradeId: string
  compact?: boolean
  onCountChange?: (n: number) => void
}) {
  const [shots, setShots] = useState<JournalScreenshotMeta[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [preview, setPreview] = useState<JournalScreenshotMeta | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    getJournalScreenshots(tradeId)
      .then((r) => {
        setShots(r.screenshots)
        onCountChange?.(r.screenshots.length)
      })
      .catch(() => setShots([]))
  }, [tradeId, onCountChange])

  useEffect(() => {
    load()
  }, [load])

  const upload = useCallback(
    async (file: File) => {
      setErr(null)
      if (file.size > MAX_MB * 1024 * 1024) {
        setErr(`That image is ${(file.size / 1024 / 1024).toFixed(1)} MB — max ${MAX_MB} MB.`)
        return
      }
      setBusy(true)
      try {
        await uploadJournalScreenshot(tradeId, file)
        load()
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Upload failed')
      } finally {
        setBusy(false)
      }
    },
    [tradeId, load],
  )

  // paste-to-upload while this strip (or a child) has focus / is hovered
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const onPaste = (e: ClipboardEvent) => {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith('image/'))
      const f = item?.getAsFile()
      if (f) {
        e.preventDefault()
        void upload(f)
      }
    }
    el.addEventListener('paste', onPaste)
    return () => el.removeEventListener('paste', onPaste)
  }, [upload])

  const remove = useCallback(
    async (id: string) => {
      try {
        await deleteJournalScreenshot(id)
        load()
        setPreview(null)
      } catch {
        /* keep it visible on failure */
      }
    },
    [load],
  )

  const thumbSize = compact ? 'h-12 w-16' : 'h-16 w-24'

  return (
    <div
      ref={rootRef}
      tabIndex={-1}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        const f = e.dataTransfer.files?.[0]
        if (f && f.type.startsWith('image/')) void upload(f)
      }}
      className="outline-none"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        {(shots ?? []).map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setPreview(s)}
            className={`group relative overflow-hidden rounded border border-border-subtle ${thumbSize}`}
            title={s.caption ?? s.filename ?? 'screenshot'}
          >
            <img
              src={journalScreenshotSrc(s.url)}
              alt={s.caption ?? 'trade screenshot'}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          </button>
        ))}

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className={`flex ${thumbSize} flex-col items-center justify-center rounded border border-dashed border-border text-[10px] text-muted hover:border-accent hover:text-accent disabled:opacity-50`}
        >
          {busy ? '…' : <>＋ image</>}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void upload(f)
            e.target.value = ''
          }}
        />
      </div>

      {!compact ? (
        <p className="mt-1 text-[10px] text-muted">
          Upload, drag-drop, or paste a screenshot (Ctrl+V). PNG / JPEG / WebP / GIF, max {MAX_MB} MB.
        </p>
      ) : null}
      {err ? <p className="mt-1 text-[10px] text-negative">{err}</p> : null}

      {preview ? (
        <div
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPreview(null)}
        >
          <div
            className="flex max-h-full max-w-3xl flex-col gap-2 rounded-lg border border-border bg-surface p-2"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={journalScreenshotSrc(preview.url)}
              alt={preview.caption ?? 'trade screenshot'}
              className="max-h-[70vh] w-auto rounded object-contain"
            />
            <div className="flex items-center justify-between gap-3 text-[11px] text-muted">
              <span className="truncate">
                {preview.caption || preview.filename || 'screenshot'} ·{' '}
                {(preview.byte_size / 1024).toFixed(0)} KB ·{' '}
                {new Date(preview.created_at).toLocaleString()}
              </span>
              <span className="flex gap-2">
                <button
                  type="button"
                  onClick={() => remove(preview.id)}
                  className="rounded border border-border px-2 py-0.5 text-negative hover:bg-negative/10"
                >
                  Delete
                </button>
                <button
                  type="button"
                  onClick={() => setPreview(null)}
                  className="rounded border border-border px-2 py-0.5 text-secondary hover:bg-surface-hover"
                >
                  Close
                </button>
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
