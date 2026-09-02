/**
 * AI Assistant contracts (`/api/ai/*`, Stage 15C). Read-only analytical chat.
 * The POST endpoint generates text only — it has no execution authority.
 */

export type AIChatRole = 'user' | 'assistant'

export interface AIChatMessage {
  role: AIChatRole
  content: string
}

export interface AIChatRequest {
  messages: AIChatMessage[]
}

export type AIErrorKind =
  | 'not_configured'
  | 'provider_unavailable'
  | 'timeout'
  | 'rate_limit'
  | 'empty'

export interface AIChatResponse {
  ok: boolean
  reply: string | null
  error: string | null
  error_kind: AIErrorKind | null
  model: string | null
  context_sections_used: string[]
  context_sections_unavailable: string[]
  read_only: boolean
  live_broker_transmission: string
  timestamp: string
}

export interface AIStatusResponse {
  configured: boolean
  model: string | null
  read_only: boolean
  live_broker_transmission: string
  timestamp: string
}
