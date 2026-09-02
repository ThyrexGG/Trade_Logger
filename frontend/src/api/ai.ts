import { apiGet, apiPost } from './client'
import type { AIChatRequest, AIChatResponse, AIStatusResponse } from '../types/ai'

/** GET /api/ai/status — whether the assistant is configured (no secret returned). */
export function getAIStatus(signal?: AbortSignal): Promise<AIStatusResponse> {
  return apiGet<AIStatusResponse>('/api/ai/status', { signal })
}

/**
 * POST /api/ai/chat — one analytical reply grounded in a read-only TradeLogger
 * snapshot. Generates text only; never executes or transmits anything.
 */
export function postAIChat(
  req: AIChatRequest,
  signal?: AbortSignal,
): Promise<AIChatResponse> {
  return apiPost<AIChatResponse>('/api/ai/chat', req, { signal })
}
