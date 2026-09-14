import { API_BASE_URL, ApiError } from './client'
import type { ChartAnalysisResponse } from '../types/chartAnalysis'

async function post(form: FormData, signal?: AbortSignal): Promise<ChartAnalysisResponse> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/api/ai/chart/analyze`, {
      method: 'POST',
      body: form,
      credentials: 'include',
      signal,
    })
  } catch (cause) {
    throw new ApiError('Network error contacting the chart analyzer', 0, { cause })
  }
  if (!res.ok) {
    let detail = `Chart analysis failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: string; error?: string }
      if (body?.detail) detail = body.detail
      else if (body?.error) detail = body.error
    } catch {
      /* not JSON — keep the generic message */
    }
    throw new ApiError(detail, res.status)
  }
  return (await res.json()) as ChartAnalysisResponse
}

/** POST an uploaded chart screenshot (multipart) for analysis. */
export function analyzeChartFile(file: File, signal?: AbortSignal): Promise<ChartAnalysisResponse> {
  const form = new FormData()
  form.append('file', file)
  return post(form, signal)
}

/** POST a tradingview.com/x/... share link for analysis (fetched server-side). */
export function analyzeChartUrl(tradingviewUrl: string, signal?: AbortSignal): Promise<ChartAnalysisResponse> {
  const form = new FormData()
  form.append('tradingview_url', tradingviewUrl)
  return post(form, signal)
}
