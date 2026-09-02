import { useCallback, useEffect, useRef, useState } from 'react'
import { getAIStatus, postAIChat } from '../api/ai'
import type { AIChatMessage, AIChatResponse } from '../types/ai'

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  /** set on an assistant turn that came back as an error */
  error?: boolean
  errorKind?: string | null
}

interface UseAIChatResult {
  configured: boolean | null
  turns: ChatTurn[]
  sending: boolean
  lastMeta: AIChatResponse | null
  send: (text: string) => void
  retry: () => void
  clear: () => void
}

const MAX_HISTORY = 18

/**
 * Drives the AI Assistant. `send()` is the only trigger (explicit user action).
 * AbortController + request-id guard; a superseded / unmounted request is
 * dropped. History sent to the server is capped; nothing is persisted.
 */
export function useAIChat(): UseAIChatResult {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [sending, setSending] = useState(false)
  const [lastMeta, setLastMeta] = useState<AIChatResponse | null>(null)
  const inFlight = useRef<AbortController | null>(null)
  const reqId = useRef(0)
  const lastUser = useRef<string | null>(null)

  useEffect(() => {
    const c = new AbortController()
    getAIStatus(c.signal)
      .then((s) => setConfigured(s.configured))
      .catch(() => setConfigured(null))
    return () => c.abort()
  }, [])

  useEffect(() => () => inFlight.current?.abort(), [])

  const dispatch = useCallback((userText: string, base: ChatTurn[]) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    const id = ++reqId.current
    lastUser.current = userText
    setSending(true)

    const history: AIChatMessage[] = [...base, { role: 'user' as const, content: userText }]
      .slice(-MAX_HISTORY)
      .map((t) => ({ role: t.role, content: t.content }))

    postAIChat({ messages: history }, controller.signal)
      .then((res) => {
        if (id !== reqId.current) return
        setLastMeta(res)
        setTurns((prev) => [
          ...prev,
          res.ok && res.reply
            ? { role: 'assistant', content: res.reply }
            : {
                role: 'assistant',
                content: res.error ?? 'The assistant could not respond.',
                error: true,
                errorKind: res.error_kind,
              },
        ])
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || id !== reqId.current) return
        setTurns((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: err instanceof Error ? err.message : 'Network error contacting the assistant.',
            error: true,
          },
        ])
      })
      .finally(() => {
        if (id === reqId.current) setSending(false)
      })
  }, [])

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || sending) return
      setTurns((prev) => {
        const next: ChatTurn[] = [...prev, { role: 'user', content: trimmed }]
        dispatch(trimmed, prev)
        return next
      })
    },
    [dispatch, sending],
  )

  const retry = useCallback(() => {
    if (sending || !lastUser.current) return
    // drop the trailing errored assistant turn, resend the last user text
    setTurns((prev) => {
      const trimmed = prev[prev.length - 1]?.error ? prev.slice(0, -1) : prev
      const base = trimmed[trimmed.length - 1]?.role === 'user' ? trimmed.slice(0, -1) : trimmed
      dispatch(lastUser.current as string, base)
      return trimmed
    })
  }, [dispatch, sending])

  const clear = useCallback(() => {
    inFlight.current?.abort()
    reqId.current++
    lastUser.current = null
    setTurns([])
    setLastMeta(null)
    setSending(false)
  }, [])

  return { configured, turns, sending, lastMeta, send, retry, clear }
}
