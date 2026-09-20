/**
 * Chart-screenshot analysis (`/api/ai/chart/analyze`). Gemini vision reads what is plotted on one image;
 * it is an opinion about that screenshot, never a signal.
 */
export type ChartAnalysisErrorKind =
  | 'not_configured'
  | 'provider_unavailable'
  | 'timeout'
  | 'rate_limit'
  | 'empty'
  | 'bad_response'
  | 'bad_input'

export interface ChartAnalysisResponse {
  ok: boolean
  error: string | null
  error_kind: ChartAnalysisErrorKind | null
  model: string | null

  /** the analysed image echoed back (present whenever `ok`) */
  image_base64: string | null
  image_mime: string | null

  symbol: string | null
  timeframe: string | null
  direction: 'long' | 'short' | null
  entry: number | null
  stop_loss: number | null
  take_profit: number | null
  additional_targets: number[]
  risk_reward: number | null
  pattern: string | null
  confluences: string[]
  setup_rating: number | null
  rating_reasoning: string | null
  caveats: string | null
  extraction_confidence: 'high' | 'medium' | 'low' | null
  disclaimer: string
  timestamp: string
}
