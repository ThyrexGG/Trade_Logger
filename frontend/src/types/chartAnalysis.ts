/**
 * Chart-screenshot analysis contracts (`/api/ai/chart/analyze`, W12).
 * Pure image-to-JSON extraction over Gemini vision — no execution authority.
 */

export type ChartAnalysisErrorKind =
  | 'not_configured'
  | 'provider_unavailable'
  | 'timeout'
  | 'rate_limit'
  | 'empty'
  | 'bad_response'
  | 'bad_input'

export type ChartDirection = 'long' | 'short'
export type ChartExtractionConfidence = 'high' | 'medium' | 'low'

export interface ChartAnalysisResponse {
  ok: boolean
  error: string | null
  error_kind: ChartAnalysisErrorKind | null
  model: string | null

  /** The analyzed image, echoed back so it can be attached to a journal
   * trade/entry afterward — present whenever `ok` is true. */
  image_base64: string | null
  image_mime: string | null

  symbol: string | null
  timeframe: string | null
  direction: ChartDirection | null
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
  extraction_confidence: ChartExtractionConfidence | null
  disclaimer: string

  turn_usage: Record<string, number> | null
  usage: Record<string, unknown> | null
  read_only: boolean
  live_broker_transmission: string
  timestamp: string
}
