import type { JournalEntry, JournalEntryInput } from '../types/entries'
import { apiDelete, apiGet, apiPatch, apiPost } from './client'

const base = '/api/operations/journal/entries'

export function listEntries(signal?: AbortSignal): Promise<{ entries: JournalEntry[] }> {
  return apiGet<{ entries: JournalEntry[] }>(base, signal)
}

export function createEntry(body: JournalEntryInput, signal?: AbortSignal): Promise<JournalEntry> {
  return apiPost<JournalEntry>(base, body, signal)
}

export function updateEntry(id: string, body: JournalEntryInput, signal?: AbortSignal): Promise<JournalEntry> {
  return apiPatch<JournalEntry>(`${base}/${encodeURIComponent(id)}`, body, signal)
}

export function deleteEntry(id: string, signal?: AbortSignal): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`${base}/${encodeURIComponent(id)}`, signal)
}
