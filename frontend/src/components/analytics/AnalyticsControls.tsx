import { useEffect, useRef, useState } from 'react'
import type { AnalyticsAvailable, AnalyticsQuery } from '../../types/analytics'
import { SectionCard } from '../intelligence/primitives'
import { Tooltip } from '../common/Tooltip'
import { parseNumberInput } from '../../lib/format'
import { saveInitialBalance } from '../../api/analytics'
import { describeAccount } from '../../lib/accountLabel'

/**
 * Filter bar for the analytics population: account, symbols, date range,
 * starting balance. Emits an `AnalyticsQuery`; the hook debounces the request.
 * No calculation happens here — only filter selection.
 */
export function AnalyticsControls({
  available,
  availableAccount,
  query,
  onChange,
}: {
  available: AnalyticsAvailable
  /** Which account `available` actually reflects (the last response's echoed
   * filter) — while a new account's fetch is in flight, `available` still
   * holds the PREVIOUS account's numbers, so this must be checked before
   * trusting `available.saved_initial_balance` for `query.account`. */
  availableAccount: string | undefined
  query: AnalyticsQuery
  onChange: (next: AnalyticsQuery) => void
}) {
  const selectedSymbols = query.symbols ?? []
  const [balanceText, setBalanceText] = useState(String(query.initial_balance ?? 10000))
  const [autoFilled, setAutoFilled] = useState(false)

  // keep the local balance field in sync if the query is reset elsewhere
  useEffect(() => {
    setBalanceText(String(query.initial_balance ?? 10000))
  }, [query.initial_balance])

  // A single selected account prefills its starting balance once per account
  // switch: the user's own saved value (POST .../initial-balance) always wins
  // if one exists — that's not a guess, it's what they told the app — else
  // the auto-detected suggestion (synced balance minus all-time P&L). Typing
  // in the field by hand overrides it for that account and saves the new
  // value (debounced below); picking a different account re-applies.
  const appliedFor = useRef<string | null>(null)
  useEffect(() => {
    const acct = query.account
    if (!acct || acct === 'ALL') {
      setAutoFilled(false)
      return
    }
    if (appliedFor.current === acct) return
    // `available` lags one fetch behind while switching accounts — it still
    // reflects the PREVIOUS account until the new response lands. Applying it
    // here would prefill the new account with the old one's saved balance and
    // then mark it "applied", permanently skipping the real value once it
    // arrives (the bug: every account showing Capital.com's $350).
    if (availableAccount !== acct) return
    if (available.saved_initial_balance != null) {
      appliedFor.current = acct
      setAutoFilled(false)
      onChange({ ...query, initial_balance: available.saved_initial_balance })
    } else if (available.suggested_initial_balance != null) {
      appliedFor.current = acct
      setAutoFilled(true)
      onChange({ ...query, initial_balance: available.suggested_initial_balance })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.account, availableAccount, available.saved_initial_balance, available.suggested_initial_balance])

  // When the user has exactly one account, "All accounts" is the same data but
  // can't hold a saved starting balance — so start on that account. Runs once,
  // so the user can still pick "All accounts" afterwards.
  const autoPicked = useRef(false)
  useEffect(() => {
    if (autoPicked.current || available.accounts.length === 0) return
    autoPicked.current = true
    if ((!query.account || query.account === 'ALL') && available.accounts.length === 1) {
      onChange({ ...query, account: available.accounts[0], symbols: undefined, start: undefined, end: undefined })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [available.accounts])

  // Debounced save of a hand-typed balance — waits for typing to pause so
  // every keystroke doesn't fire its own request. Leaving the page flushes a
  // pending save instead of dropping it.
  const saveTimer = useRef<number | null>(null)
  const pendingSave = useRef<{ acct: string; n: number } | null>(null)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const flushSave = () => {
    if (saveTimer.current) {
      window.clearTimeout(saveTimer.current)
      saveTimer.current = null
    }
    const p = pendingSave.current
    if (!p) return
    pendingSave.current = null
    setSaveState('saving')
    saveInitialBalance(p.acct, p.n)
      .then(() => setSaveState('saved'))
      .catch(() => setSaveState('error'))
  }
  useEffect(() => flushSave, []) // eslint-disable-line react-hooks/exhaustive-deps

  const noAccountSelected = !query.account || query.account === 'ALL'

  const toggleSymbol = (sym: string) => {
    const has = selectedSymbols.includes(sym)
    const next = has ? selectedSymbols.filter((s) => s !== sym) : [...selectedSymbols, sym]
    // empty selection === "all", represented as undefined
    onChange({ ...query, symbols: next.length && next.length < available.symbols.length ? next : undefined })
  }

  const allSelected = selectedSymbols.length === 0 || selectedSymbols.length === available.symbols.length

  return (
    <SectionCard title="Filters">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)]">
        <label className="block text-[11px] text-muted">
          Account
          <select
            value={query.account ?? 'ALL'}
            onChange={(e) => onChange({ ...query, account: e.target.value, symbols: undefined, start: undefined, end: undefined })}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          >
            <option value="ALL">All accounts</option>
            {available.accounts.map((a) => (
              <option key={a} value={a}>{describeAccount(a).label}</option>
            ))}
          </select>
        </label>

        <div className="text-[11px] text-muted">
          Symbols
          <div className="mt-1 flex flex-wrap gap-1">
            <button
              type="button"
              onClick={() => onChange({ ...query, symbols: undefined })}
              className={`rounded border px-2 py-0.5 text-[11px] ${
                allSelected ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-secondary hover:text-primary'
              }`}
            >
              All
            </button>
            {available.symbols.map((s) => {
              const on = !allSelected && selectedSymbols.includes(s)
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSymbol(s)}
                  className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
                    on ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-secondary hover:text-primary'
                  }`}
                >
                  {s}
                </button>
              )
            })}
            {available.symbols.length === 0 ? <span className="text-muted">no trades</span> : null}
          </div>
        </div>

        <label className="block text-[11px] text-muted">
          <span className="inline-flex items-center gap-1">
            Starting balance ($)
            {autoFilled ? (
              <Tooltip label="Detected from this account's synced balance minus its all-time P&L. Edit it if you know the real figure — a deposit or withdrawal in between would throw this off.">
                <span className="cursor-help rounded bg-accent/10 px-1 text-[9px] font-semibold uppercase tracking-wide text-accent">
                  auto
                </span>
              </Tooltip>
            ) : null}
          </span>
          <input
            value={balanceText}
            onChange={(e) => {
              setBalanceText(e.target.value)
              setAutoFilled(false)
              const n = parseNumberInput(e.target.value)
              if (n === null || n <= 0) return
              onChange({ ...query, initial_balance: n })
              const acct = query.account
              if (!acct || acct === 'ALL') return
              if (saveTimer.current) window.clearTimeout(saveTimer.current)
              pendingSave.current = { acct, n }
              setSaveState('idle')
              saveTimer.current = window.setTimeout(flushSave, 800)
            }}
            inputMode="decimal"
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs tabular-nums text-primary focus:border-accent focus:outline-none"
          />
          <span className="mt-1 block min-h-[14px] text-[10px]" aria-live="polite">
            {noAccountSelected ? (
              <span className="text-muted">Pick an account above to save this balance.</span>
            ) : saveState === 'saving' ? (
              <span className="text-muted">Saving…</span>
            ) : saveState === 'saved' ? (
              <span className="text-positive">✓ Saved for {describeAccount(query.account).label}</span>
            ) : saveState === 'error' ? (
              <span className="text-warning">Couldn’t save — check your connection and retype it.</span>
            ) : null}
          </span>
        </label>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="block text-[11px] text-muted">
          From
          <input
            type="date"
            value={query.start ?? ''}
            min={available.date_min ?? undefined}
            max={available.date_max ?? undefined}
            onChange={(e) => onChange({ ...query, start: e.target.value || undefined })}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label className="block text-[11px] text-muted">
          To
          <input
            type="date"
            value={query.end ?? ''}
            min={available.date_min ?? undefined}
            max={available.date_max ?? undefined}
            onChange={(e) => onChange({ ...query, end: e.target.value || undefined })}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={() => onChange({ account: query.account, symbols: undefined, start: undefined, end: undefined, initial_balance: query.initial_balance })}
            className="rounded border border-border px-2.5 py-1 text-[11px] text-secondary hover:text-primary"
          >
            Clear dates / symbols
          </button>
        </div>
      </div>

      {available.date_min ? (
        <p className="mt-2 font-mono text-[10px] text-muted">
          data range {available.date_min} → {available.date_max}
        </p>
      ) : null}
    </SectionCard>
  )
}
