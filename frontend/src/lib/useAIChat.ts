import { useCallback, useEffect, useRef, useState } from 'react'
import { getAIStatus, postAIChat } from '../api/ai'
import type { AIChatMessage, AIChatResponse, AIToolCall, AIUsage } from '../types/ai'

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  /** epoch ms — when this turn was added */
  at?: number
  /** set on an assistant turn that came back as an error */
  error?: boolean
  errorKind?: string | null
  /** read-only tools the assistant ran for this reply */
  tools?: AIToolCall[]
}

interface UseAIChatResult {
  configured: boolean | null
  turns: ChatTurn[]
  sending: boolean
  lastMeta: AIChatResponse | null
  usage: AIUsage | null
  send: (text: string) => void
  retry: () => void
  clear: () => void
}

const MAX_HISTORY = 18
const STORAGE_KEY = 'tl.assistant.history.v1'
const STORE_CAP = 60

function loadStored(): ChatTurn[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (t): t is ChatTurn =>
          t && (t.role === 'user' || t.role === 'assistant') && typeof t.content === 'string',
      )
      .slice(-STORE_CAP)
  } catch {
    return []
  }
}

function persist(turns: ChatTurn[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(turns.slice(-STORE_CAP)))
  } catch {
    /* private mode / quota / disabled — the chat still works in-memory */
  }
}

/**
 * Drives the AI Assistant. `send()` is the only trigger (explicit user action).
 * AbortController + request-id guard; a superseded / unmounted request is
 * dropped. The visible transcript is persisted to this browser's localStorage
 * so a refresh keeps the conversation; the history *sent to the server* is
 * still capped at MAX_HISTORY.
 */
export function useAIChat(): UseAIChatResult {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>(() => loadStored())
  const [sending, setSending] = useState(false)
  const [lastMeta, setLastMeta] = useState<AIChatResponse | null>(null)
  const [usage, setUsage] = useState<AIUsage | null>(null)
  const inFlight = useRef<AbortController | null>(null)
  const reqId = useRef(0)
  const lastUser = useRef<string | null>(null)

  useEffect(() => {
    const c = new AbortController()
    getAIStatus(c.signal)
      .then((s) => {
        setConfigured(s.configured)
        if (s.usage) setUsage(s.usage)
      })
      .catch(() => setConfigured(null))
    return () => c.abort()
  }, [])

  useEffect(() => () => inFlight.current?.abort(), [])

  useEffect(() => {
    persist(turns)
  }, [turns])

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
        if (res.usage) setUsage(res.usage)
        setTurns((prev) => [
          ...prev,
          res.ok && res.reply
            ? {
                role: 'assistant',
                content: res.reply,
                at: Date.now(),
                tools: res.tool_calls ?? undefined,
              }
            : {
                role: 'assistant',
                content: res.error ?? 'The assistant could not respond.',
                error: true,
                errorKind: res.error_kind,
                at: Date.now(),
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
            at: Date.now(),
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
        const next: ChatTurn[] = [...prev, { role: 'user', content: trimmed, at: Date.now() }]
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
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  return { configured, turns, sending, lastMeta, usage, send, retry, clear }
}
