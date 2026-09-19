import type { AIChatMessage, AIChatResponse, AIStatusResponse } from '../types/ai'
import { apiGet, apiPostSlow } from './client'

/** GET /api/ai/status — is the assistant set up on the server, and today's usage. */
export function getAIStatus(signal?: AbortSignal): Promise<AIStatusResponse> {
  return apiGet<AIStatusResponse>('/api/ai/status', signal)
}

/** POST /api/ai/chat — one reply grounded in a read-only snapshot of your TradeLogger data. Text only. */
export function postAIChat(messages: AIChatMessage[], signal?: AbortSignal): Promise<AIChatResponse> {
  return apiPostSlow<AIChatResponse>('/api/ai/chat', { messages }, signal)
}
