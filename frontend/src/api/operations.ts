import { API_BASE_URL, ApiError, apiDelete, apiGet, apiPatch, apiPost } from './client'
import type {
  AuditResponse,
  JournalEntriesResponse,
  JournalEntry,
  JournalEntryCreate,
  JournalResponse,
  JournalScreenshotMeta,
  JournalScreenshotsResponse,
  JournalUpdateRequest,
  JournalUpdateResponse,
  OperationsSystemResponse,
} from '../types/operations'

/** GET /api/operations/journal — read-only closed-trade journal. */
export function getJournal(signal?: AbortSignal): Promise<JournalResponse> {
  return apiGet<JournalResponse>('/api/operations/journal', { signal })
}

/**
 * PATCH /api/operations/journal/{trade_id} — update the subjective annotations
 * (setup_tag / notes / chart_snapshot_url) of one closed trade. Never touches
 * execution, orders or a broker.
 */
export function patchJournalEntry(
  tradeId: string,
  body: JournalUpdateRequest,
  signal?: AbortSignal,
): Promise<JournalUpdateResponse> {
  return apiPatch<JournalUpdateResponse>(
    `/api/operations/journal/${encodeURIComponent(tradeId)}`,
    body,
    { signal },
  )
}

// --- journal screenshots (in-DB image attachments) ---------------------

const journalBase = (tradeId: string) =>
  `/api/operations/journal/${encodeURIComponent(tradeId)}/screenshots`

/** GET the screenshot metadata list for one closed trade. */
export function getJournalScreenshots(
  tradeId: string,
  signal?: AbortSignal,
): Promise<JournalScreenshotsResponse> {
  return apiGet<JournalScreenshotsResponse>(journalBase(tradeId), { signal })
}

/** POST one image (multipart) to a closed trade's journal entry. */
export async function uploadJournalScreenshot(
  tradeId: string,
  file: File,
  caption?: string,
  signal?: AbortSignal,
): Promise<JournalScreenshotMeta> {
  const form = new FormData()
  form.append('file', file)
  if (caption) form.append('caption', caption)
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}${journalBase(tradeId)}`, {
      method: 'POST',
      body: form,
      signal,
    })
  } catch (cause) {
    throw new ApiError('Network error uploading screenshot', 0, { cause })
  }
  if (!res.ok) {
    let detail = `Upload failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body?.detail) detail = body.detail
    } catch {
      /* non-JSON */
    }
    throw new ApiError(detail, res.status)
  }
  return (await res.json()) as JournalScreenshotMeta
}

/** DELETE one journal screenshot by id. */
export function deleteJournalScreenshot(
  screenshotId: string,
  signal?: AbortSignal,
): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(
    `/api/operations/journal/screenshot/${encodeURIComponent(screenshotId)}`,
    { signal },
  )
}

/** Absolute URL for an <img src> pointing at a stored screenshot. */
export function journalScreenshotSrc(url: string): string {
  return `${API_BASE_URL}${url}`
}

// --- free-standing journal entries (market ideas / reviews) ------------

export function getJournalEntries(signal?: AbortSignal): Promise<JournalEntriesResponse> {
  return apiGet<JournalEntriesResponse>('/api/operations/journal/entries', { signal })
}

export function createJournalEntry(
  body: JournalEntryCreate,
  signal?: AbortSignal,
): Promise<JournalEntry> {
  return apiPost<JournalEntry>('/api/operations/journal/entries', body, { signal })
}

export function patchJournalEntryNote(
  entryId: string,
  body: Partial<JournalEntryCreate>,
  signal?: AbortSignal,
): Promise<JournalEntry> {
  return apiPatch<JournalEntry>(
    `/api/operations/journal/entries/${encodeURIComponent(entryId)}`,
    body,
    { signal },
  )
}

export function deleteJournalEntry(
  entryId: string,
  signal?: AbortSignal,
): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(
    `/api/operations/journal/entries/${encodeURIComponent(entryId)}`,
    { signal },
  )
}

export interface JournalTagStat {
  tag: string
  n: number
  wins: number
  win_rate: number | null
  net_total: number
  expectancy: number | null
}

export function getJournalTagStats(
  signal?: AbortSignal,
): Promise<{ tags: JournalTagStat[]; timestamp: string }> {
  return apiGet<{ tags: JournalTagStat[]; timestamp: string }>(
    '/api/operations/journal/tag-stats',
    { signal },
  )
}

/** GET /api/operations/audit — read-only execution audit trail. */
export function getAudit(
  limit = 200,
  signal?: AbortSignal,
): Promise<AuditResponse> {
  return apiGet<AuditResponse>(`/api/operations/audit?limit=${limit}`, { signal })
}

/** GET /api/operations/system — health values + safety-gate diagnostics. */
export function getSystemOps(
  signal?: AbortSignal,
): Promise<OperationsSystemResponse> {
  return apiGet<OperationsSystemResponse>('/api/operations/system', { signal })
}
