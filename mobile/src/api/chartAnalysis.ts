import type { ChartAnalysisResponse } from '../types/chartAnalysis'
import { apiPostForm } from './client'

/** A vision model reads the chart — a reply can take up to ~90 s when the model is busy and the server retries. */
const ANALYSIS_TIMEOUT_MS = 100_000

/** POST a chart screenshot (a local file:// JPEG the app already downscaled) for analysis. */
export function analyzeChartImage(localUri: string, signal?: AbortSignal): Promise<ChartAnalysisResponse> {
  const form = new FormData()
  form.append('file', { uri: localUri, name: 'chart.jpg', type: 'image/jpeg' } as unknown as Blob)
  return apiPostForm<ChartAnalysisResponse>('/api/ai/chart/analyze', form, signal, ANALYSIS_TIMEOUT_MS)
}

/** POST a tradingview.com/x/... share link; the server fetches the image itself. */
export function analyzeChartLink(tradingviewUrl: string, signal?: AbortSignal): Promise<ChartAnalysisResponse> {
  const form = new FormData()
  form.append('tradingview_url', tradingviewUrl)
  return apiPostForm<ChartAnalysisResponse>('/api/ai/chart/analyze', form, signal, ANALYSIS_TIMEOUT_MS)
}
