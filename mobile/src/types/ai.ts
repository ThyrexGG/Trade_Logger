/** Mirrors api/schemas.py AIChat* — the read-only analytical assistant. */
export interface AIChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AIUsage {
  day: string
  day_requests: number
  day_tokens: number
  day_budget: number
}

export interface AIChatResponse {
  ok: boolean
  reply?: string | null
  error?: string | null
  error_kind?: string | null
  usage?: AIUsage | null
}

export interface AIStatusResponse {
  configured: boolean
  usage?: AIUsage | null
}
