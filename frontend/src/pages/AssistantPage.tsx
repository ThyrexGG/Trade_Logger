import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { useAIChat } from '../lib/useAIChat'
import { PageContainer } from '../components/shell/PageContainer'
import { OpsSafetyBanner, OpsUnavailable } from '../components/operations/primitives'

const SUGGESTIONS = [
  'How did I perform today?',
  "Why is today's P&L negative?",
  'What are my strongest and weakest symbols?',
  'What does the Command Center show right now?',
  'What are the biggest weaknesses in my current research state?',
  'Summarize my current market context.',
]

/**
 * AI Assistant (`/workspace/assistant`). A read-only analytical chat grounded in
 * an allowlisted TradeLogger snapshot + Gemini (server-side key). It cannot
 * place, modify, cancel or transmit an order — there is no such pathway.
 */
export function AssistantPage() {
  const { configured, turns, sending, lastMeta, send, retry, clear } = useAIChat()
  const [draft, setDraft] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [turns, sending])

  const disabled = configured === false

  function submit(e: FormEvent | KeyboardEvent) {
    e.preventDefault()
    if (!draft.trim() || sending || disabled) return
    send(draft)
    setDraft('')
  }

  const lastErrored = turns[turns.length - 1]?.error

  return (
    <PageContainer
      title="AI Assistant"
      description="Read-only analytical assistant over your authoritative TradeLogger data. It can explain and analyze — it cannot trade, place orders, or change any setting."
      actions={
        <div className="flex items-center gap-2">
          {turns.length > 0 ? (
            <button type="button" onClick={clear} className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
              Clear conversation
            </button>
          ) : null}
        </div>
      }
    >
      <div className="flex h-[calc(100vh-14rem)] min-h-[28rem] flex-col gap-3">
        <OpsSafetyBanner />

        {disabled ? (
          <OpsUnavailable>
            The AI assistant is not configured on this server. An operator needs to set
            <code> GEMINI_API_KEY</code> in the backend environment. Every other page works
            without it.
          </OpsUnavailable>
        ) : null}

        <div
          ref={scrollRef}
          className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-border bg-surface p-4"
        >
          {turns.length === 0 && !disabled ? (
            <div className="space-y-3">
              <p className="text-xs text-muted">
                Ask about your performance, positions, alerts, market context or research
                state. Answers are grounded in a live read-only snapshot; if the data
                isn't available the assistant will say so rather than guess.
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => { send(s) }}
                    className="rounded border border-border px-2 py-1 text-[11px] text-secondary hover:border-accent/40 hover:text-accent"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {turns.map((t, i) => (
            <div
              key={i}
              className={`max-w-[85%] rounded-lg px-3 py-2 text-xs whitespace-pre-wrap ${
                t.role === 'user'
                  ? 'ml-auto bg-accent/10 text-primary'
                  : t.error
                    ? 'border border-negative/30 bg-negative/10 text-negative'
                    : 'bg-surface-elevated/50 text-secondary'
              }`}
            >
              {t.content}
              {t.error && t.errorKind && t.errorKind !== 'not_configured' ? (
                <button type="button" onClick={retry} className="ml-2 underline">retry</button>
              ) : null}
            </div>
          ))}

          {sending ? (
            <div className="max-w-[85%] rounded-lg bg-surface-elevated/50 px-3 py-2 text-xs text-muted">
              thinking…
            </div>
          ) : null}
        </div>

        {lastMeta && lastMeta.ok && lastMeta.context_sections_unavailable.length > 0 ? (
          <p className="text-[11px] text-muted">
            Snapshot sections unavailable this turn: {lastMeta.context_sections_unavailable.join(', ')}.
          </p>
        ) : null}

        <form onSubmit={submit} className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(e) }
            }}
            disabled={sending || disabled}
            rows={2}
            maxLength={4000}
            placeholder={disabled ? 'Assistant unavailable' : 'Ask about your TradeLogger data…'}
            className="flex-1 resize-none rounded border border-border bg-background px-2 py-1.5 text-xs text-primary placeholder:text-muted focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={!draft.trim() || sending || disabled}
            className="rounded border border-accent/40 bg-accent/10 px-3 py-2 text-xs text-accent disabled:opacity-40"
          >
            Send
          </button>
        </form>

        <p className="text-[11px] text-muted">
          {lastErrored ? '' : null}
          Not investment advice. Trading decisions and their consequences are yours. The
          assistant is read-only — it has no path to order submission, position changes,
          risk settings or automation.
        </p>
      </div>
    </PageContainer>
  )
}
