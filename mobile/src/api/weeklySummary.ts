import type { WeeklySummaryResponse } from '../types/weeklySummary'
import { apiGet, apiPut } from './client'

/** GET /api/weekly-summary — this week so far and last week, plus whether the Sunday notification is on. */
export function getWeeklySummary(signal?: AbortSignal): Promise<WeeklySummaryResponse> {
  return apiGet<WeeklySummaryResponse>('/api/weekly-summary', signal)
}

/** PUT /api/weekly-summary — turn the Sunday notification on or off. */
export function setWeeklySummaryEnabled(enabled: boolean, signal?: AbortSignal): Promise<{ enabled: boolean }> {
  return apiPut<{ enabled: boolean }>('/api/weekly-summary', { enabled }, signal)
}
