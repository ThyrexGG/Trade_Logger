import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { useAIChat } from '../lib/useAIChat'
import { PageContainer } from '../components/shell/PageContainer'
import { ChatMarkdown } from '../components/assistant/ChatMarkdown'

const SUGGESTIONS = [
  'How did I perform today?',
  "Why is today's P&L negative?",
  'What are my strongest and weakest symbols?',
  'What does the Command Center show right now?',
  'Where is my research state weakest?',
  'Summarize my current market context.',
]

function clockTime(at?: number): string {
  if (!at) return ''
  return new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * AI Assistant (`/workspace/assistant`). A read-only analytical chat grounded in
 * an allowlisted TradeLogger snapshot + Gemini (server-side key). It cannot
 * place, modify, cancel or transmit an order — there is no such pathway. The
 * transcript persists in this browser so a refresh keeps the conversation.
 */
export function AssistantPage() {
  const { configured, turns, sending, lastMeta, send, retry, clear } = useAIChat()
  const [draft, setDraft] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns, sending])

  // auto-grow the textarea up to ~6 rows
  useLayoutEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = '0px'
    ta.style.height = `${Math.min(ta.scrollHeight, 150)}px`
  }, [draft])

  const disabled = configured === false

  function submit(e: FormEvent | KeyboardEvent) {
    e.preventDefault()
    if (!draft.trim() || sending || disabled) return
    send(draft)
    setDraft('')
  }

  const empty = turns.length === 0

  return (
    <PageContainer
      title="AI Assistant"
      description="Read-only analytical assistant grounded in your authoritative TradeLogger data. It explains and analyzes — it cannot trade, place orders, or change a setting."
      actions={
        turns.length > 0 ? (
          <button
            type="button"
            onClick={clear}
            className="rounded border border-border px-2.5 py-1 text-xs text-secondary hover:border-negative/40 hover:text-negative"
          >
            Clear
          </button>
        ) : null
      }
    >
      <div className="flex h-[calc(100vh-12rem)] min-h-[30rem] flex-col overflow-hidden rounded-xl border border-border bg-surface">
        {/* header strip */}
        <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-2 text-[11px]">
          <span className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                disabled ? 'bg-muted' : configured ? 'bg-positive' : 'bg-warning'
              }`}
              aria-hidden="true"
            />
            <span className="text-muted">
              {disabled ? 'Not configured' : lastMeta?.model ? lastMeta.model : 'Assistant'}
            </span>
          </span>
          <span className="font-mono uppercase tracking-wider text-blocked">Read-only · no order path</span>
        </div>

        {/* transcript */}
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {disabled ? (
            <div className="mx-auto max-w-md rounded-lg border border-warning/30 bg-warning/10 p-4 text-xs text-warning">
              The assistant isn't configured on this server — an operator needs to set{' '}
              <code>GEMINI_API_KEY</code> in the backend environment. Every other page works
              without it.
            </div>
          ) : empty ? (
            <div className="mx-auto flex max-w-lg flex-col items-center gap-4 pt-8 text-center">
              <div className="flex h-11 w-11 items-center justify-center rounded-full border border-border-subtle bg-surface-elevated text-lg">
                ✦
              </div>
              <div>
                <p className="text-sm font-medium text-primary">Ask about your trading</p>
                <p className="mt-1 text-xs text-muted">
                  Answers are grounded in a live read-only snapshot — performance, positions,
                  alerts, market and research state. If the data isn't there, it says so.
                </p>
              </div>
              <div className="grid w-full gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="rounded-lg border border-border-subtle bg-surface-elevated/40 px-3 py-2 text-left text-[11px] text-secondary transition-colors hover:border-accent/40 hover:text-primary"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {turns.map((t, i) =>
            t.role === 'user' ? (
              <div key={i} className="flex flex-col items-end gap-0.5">
                <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-accent/15 px-3.5 py-2 text-sm text-primary">
                  {t.content}
                </div>
                {t.at ? <span className="pr-1 text-[10px] text-muted">{clockTime(t.at)}</span> : null}
              </div>
            ) : (
              <div key={i} className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted">
                  <span className={`h-1.5 w-1.5 rounded-full ${t.error ? 'bg-negative' : 'bg-accent'}`} />
                  Assistant
                  {t.at ? <span className="normal-case tracking-normal">· {clockTime(t.at)}</span> : null}
                </div>
                <div
                  className={`max-w-[92%] rounded-2xl rounded-tl-sm px-3.5 py-2.5 ${
                    t.error
                      ? 'border border-negative/30 bg-negative/10 text-negative'
                      : 'bg-surface-elevated/50 text-secondary'
                  }`}
                >
                  {t.error ? (
                    <span className="text-sm">
                      {t.content}
                      {t.errorKind && t.errorKind !== 'not_configured' ? (
                        <button
                          type="button"
                          onClick={retry}
                          className="ml-2 underline underline-offset-2 hover:no-underline"
                        >
                          retry
                        </button>
                      ) : null}
                    </span>
                  ) : (
                    <ChatMarkdown text={t.content} />
                  )}
                </div>
              </div>
            ),
          )}

          {sending ? (
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                Assistant
              </div>
              <div className="w-fit rounded-2xl rounded-tl-sm bg-surface-elevated/50 px-4 py-3">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" />
                </span>
              </div>
            </div>
          ) : null}
        </div>

        {/* meta + composer */}
        <div className="border-t border-border-subtle px-4 py-3">
          {lastMeta && lastMeta.ok && lastMeta.context_sections_unavailable.length > 0 ? (
            <p className="mb-2 text-[10px] text-muted">
              Snapshot sections unavailable this turn:{' '}
              {lastMeta.context_sections_unavailable.join(', ')}.
            </p>
          ) : null}

          <form onSubmit={submit} className="flex items-end gap-2">
            <textarea
              ref={taRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit(e)
                }
              }}
              disabled={sending || disabled}
              rows={1}
              maxLength={4000}
              placeholder={disabled ? 'Assistant unavailable' : 'Ask about your TradeLogger data…  (Enter to send, Shift+Enter for a new line)'}
              className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-primary placeholder:text-muted focus:border-accent focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!draft.trim() || sending || disabled}
              className="shrink-0 rounded-lg bg-accent/15 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/25 disabled:opacity-40"
            >
              Send
            </button>
          </form>

          <p className="mt-2 text-[10px] text-muted">
            Not investment advice · read-only, no path to orders, position changes, risk
            settings or automation · transcript stays in this browser.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
