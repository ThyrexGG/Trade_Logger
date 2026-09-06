import { useCallback, useEffect, useState } from 'react'
import type { JournalEntry, JournalEntryKind } from '../../types/operations'
import {
  createJournalEntry,
  deleteJournalEntry,
  getJournalEntries,
  patchJournalEntryNote,
} from '../../api/operations'
import { SectionCard } from '../operations/primitives'
import { ScreenshotStrip } from './ScreenshotStrip'

const KINDS: { id: JournalEntryKind; label: string }[] = [
  { id: 'idea', label: 'Idea' },
  { id: 'review', label: 'Review' },
  { id: 'observation', label: 'Observation' },
]
const KIND_TONE: Record<JournalEntryKind, string> = {
  idea: 'bg-accent/10 text-accent',
  review: 'bg-warning/10 text-warning',
  observation: 'bg-surface-elevated text-secondary',
}

function fmtDate(iso: string): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''
}

function EntryCard({
  entry,
  onChanged,
  onDeleted,
}: {
  entry: JournalEntry
  onChanged: (e: JournalEntry) => void
  onDeleted: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [kind, setKind] = useState<JournalEntryKind>(entry.kind)
  const [instrument, setInstrument] = useState(entry.instrument ?? '')
  const [title, setTitle] = useState(entry.title ?? '')
  const [body, setBody] = useState(entry.body)
  const [tags, setTags] = useState((entry.tags ?? []).join(', '))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setErr(null)
    try {
      const updated = await patchJournalEntryNote(entry.id, {
        kind,
        instrument: instrument.trim() || null,
        title: title.trim() || null,
        body,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      })
      onChanged(updated)
      setEditing(false)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!confirm('Delete this entry and its screenshots?')) return
    setBusy(true)
    try {
      await deleteJournalEntry(entry.id)
      onDeleted(entry.id)
    } catch {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-border-subtle bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${KIND_TONE[entry.kind]}`}>
          {entry.kind}
        </span>
        {entry.instrument ? (
          <span className="font-mono font-semibold text-primary">{entry.instrument}</span>
        ) : null}
        <span className="font-medium text-secondary">{entry.title || '(untitled)'}</span>
        <span className="text-muted">{fmtDate(entry.updated_at)}</span>
        <span className="ml-auto flex gap-2">
          {!editing ? (
            <button type="button" onClick={() => setEditing(true)} className="text-accent hover:underline">
              edit
            </button>
          ) : null}
          <button type="button" onClick={remove} disabled={busy} className="text-negative hover:underline disabled:opacity-50">
            delete
          </button>
        </span>
      </div>

      {editing ? (
        <div className="mt-2 space-y-2">
          <div className="flex flex-wrap gap-2">
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as JournalEntryKind)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary"
            >
              {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
            <input
              value={instrument}
              onChange={(e) => setInstrument(e.target.value)}
              placeholder="instrument"
              maxLength={32}
              className="w-28 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
            />
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="title"
              maxLength={200}
              className="min-w-[10rem] flex-1 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
            />
          </div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            maxLength={20_000}
            className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary"
          />
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="tags, comma separated"
            className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
          />
          {err ? <p className="text-[11px] text-negative">{err}</p> : null}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] text-accent disabled:opacity-40"
            >
              {busy ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded border border-border px-2.5 py-1 text-[11px] text-secondary hover:text-primary"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : entry.body ? (
        <p className="mt-1.5 whitespace-pre-wrap text-xs text-secondary">{entry.body}</p>
      ) : null}

      {entry.tags?.length ? (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {entry.tags.map((t) => (
            <span key={t} className="rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] text-muted">
              #{t}
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-2">
        <ScreenshotStrip tradeId={entry.id} compact />
      </div>
    </div>
  )
}

/** Free-standing journal entries (ideas / reviews / observations) not tied to a trade. */
export function FreeEntries() {
  const [entries, setEntries] = useState<JournalEntry[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState({ kind: 'idea' as JournalEntryKind, instrument: '', title: '', body: '', tags: '' })
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    getJournalEntries()
      .then((r) => setEntries(r.entries))
      .catch(() => setEntries([]))
  }, [])
  useEffect(() => load(), [load])

  async function create() {
    if (!draft.body.trim() && !draft.title.trim()) return
    setBusy(true)
    try {
      await createJournalEntry({
        kind: draft.kind,
        instrument: draft.instrument.trim() || null,
        title: draft.title.trim() || null,
        body: draft.body,
        tags: draft.tags.split(',').map((t) => t.trim()).filter(Boolean),
      })
      setDraft({ kind: 'idea', instrument: '', title: '', body: '', tags: '' })
      setAdding(false)
      load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      title="Notes & ideas"
      action={
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="rounded border border-border px-2 py-0.5 text-[11px] text-secondary hover:border-accent/40 hover:text-accent"
        >
          {adding ? 'Cancel' : '＋ New note'}
        </button>
      }
    >
      <p className="mb-2 text-[11px] text-muted">
        Market observations, pre-trade plans and post-mortems that aren&apos;t tied to a single closed trade.
      </p>

      {adding ? (
        <div className="mb-3 space-y-2 rounded border border-accent/30 bg-surface-elevated/40 p-3">
          <div className="flex flex-wrap gap-2">
            <select
              value={draft.kind}
              onChange={(e) => setDraft({ ...draft, kind: e.target.value as JournalEntryKind })}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-primary"
            >
              {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
            <input
              value={draft.instrument}
              onChange={(e) => setDraft({ ...draft, instrument: e.target.value })}
              placeholder="instrument (optional)"
              maxLength={32}
              className="w-40 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
            />
            <input
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              placeholder="title"
              maxLength={200}
              className="min-w-[10rem] flex-1 rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
            />
          </div>
          <textarea
            value={draft.body}
            onChange={(e) => setDraft({ ...draft, body: e.target.value })}
            rows={4}
            placeholder="What are you seeing / planning / reviewing?"
            className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
          />
          <input
            value={draft.tags}
            onChange={(e) => setDraft({ ...draft, tags: e.target.value })}
            placeholder="tags, comma separated"
            className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary placeholder:text-muted"
          />
          <button
            type="button"
            onClick={create}
            disabled={busy}
            className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] text-accent disabled:opacity-40"
          >
            {busy ? 'Creating…' : 'Create — then add screenshots'}
          </button>
        </div>
      ) : null}

      {entries === null ? (
        <p className="text-[11px] text-muted">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-[11px] text-muted">No notes yet.</p>
      ) : (
        <div className="space-y-2">
          {entries.map((e) => (
            <EntryCard
              key={e.id}
              entry={e}
              onChanged={(u) => setEntries((prev) => prev?.map((x) => (x.id === u.id ? u : x)) ?? prev)}
              onDeleted={(id) => setEntries((prev) => prev?.filter((x) => x.id !== id) ?? prev)}
            />
          ))}
        </div>
      )}
    </SectionCard>
  )
}
