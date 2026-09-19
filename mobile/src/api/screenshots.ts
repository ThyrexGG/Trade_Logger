import { API_BASE_URL } from '../config'
import type { JournalScreenshotMeta, JournalScreenshotsResponse } from '../types/screenshots'
import { apiDelete, apiGet, apiPostForm } from './client'

const base = (ownerId: string) => `/api/operations/journal/${encodeURIComponent(ownerId)}/screenshots`

/** GET the screenshot list for a closed trade id or an open position id. */
export function getScreenshots(ownerId: string, signal?: AbortSignal): Promise<JournalScreenshotsResponse> {
  return apiGet<JournalScreenshotsResponse>(base(ownerId), signal)
}

/** POST one image (multipart). `localUri` is a file:// JPEG the app already downscaled. */
export function uploadScreenshot(ownerId: string, localUri: string, signal?: AbortSignal): Promise<JournalScreenshotMeta> {
  const form = new FormData()
  // React Native's FormData takes this {uri,name,type} shape for files.
  form.append('file', { uri: localUri, name: 'screenshot.jpg', type: 'image/jpeg' } as unknown as Blob)
  return apiPostForm<JournalScreenshotMeta>(base(ownerId), form, signal)
}

export function deleteScreenshot(screenshotId: string, signal?: AbortSignal): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`/api/operations/journal/screenshot/${encodeURIComponent(screenshotId)}`, signal)
}

/** Absolute URL for the image bytes (needs the auth header — see authHeaders()). */
export function screenshotUrl(meta: JournalScreenshotMeta): string {
  return `${API_BASE_URL}${meta.url}`
}
