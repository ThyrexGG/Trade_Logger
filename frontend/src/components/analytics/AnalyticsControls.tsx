import { useEffect, useRef, useState } from 'react'
import type { AnalyticsAvailable, AnalyticsQuery } from '../../types/analytics'
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
  const [filtersOpen, setFiltersOpen] = useState(false)

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

  const activeFilters = (allSelected ? 0 : 1) + (query.start ? 1 : 0) + (query.end ? 1 : 0)

  return (
    <div className="space-y-3">
      <div className="tl-toolbar">
        <label className="flex items-center">
          <span className="sr-only">Account</span>
          <select
            value={query.account ?? 'ALL'}
            onChange={(e) => onChange({ ...query, account: e.target.value, symbols: undefined, start: undefined, end: undefined })}
            className="tl-select"
          >
            <option value="ALL">All accounts</option>
            {available.accounts.map((a) => (
              <option key={a} value={a}>{describeAccount(a).label}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => setFiltersOpen((v) => !v)}
          aria-expanded={filtersOpen}
          className={`tl-btn tl-btn--secondary ${activeFilters ? '!border-[var(--tl-accent-line)]' : ''}`}
        >
          Filters
          {activeFilters ? <span className="rounded-full bg-accent-fill px-1.5 font-mono text-[10px] font-bold text-[var(--tl-gradient-ink)]">{activeFilters}</span> : null}
        </button>
        {activeFilters ? (
          <button
            type="button"
            onClick={() => onChange({ account: query.account, symbols: undefined, start: undefined, end: undefined, initial_balance: query.initial_balance })}
            className="tl-btn tl-btn--ghost"
          >
            Clear
          </button>
        ) : null}
        {available.date_min ? (
          <span className="ml-auto text-xs text-muted">
            Trades from {available.date_min} to {available.date_max}
          </span>
        ) : null}
      </div>

      {filtersOpen ? (
        <div className="tl-card tl-fade-in grid gap-4 p-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <p className="mb-1.5 text-xs font-semibold text-muted">Markets</p>
            <div className="flex flex-wrap gap-1.5">
              <button type="button" aria-pressed={allSelected} onClick={() => onChange({ ...query, symbols: undefined })} className="tl-chip">
                All
              </button>
              {available.symbols.map((s) => (
                <button key={s} type="button" aria-pressed={!allSelected && selectedSymbols.includes(s)} onClick={() => toggleSymbol(s)} className="tl-chip font-mono">
                  {s}
                </button>
              ))}
              {available.symbols.length === 0 ? <span className="text-xs text-muted">No trades yet</span> : null}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <label className="block text-xs font-semibold text-muted">
              From
              <input
                type="date"
                value={query.start ?? ''}
                min={available.date_min ?? undefined}
                max={available.date_max ?? undefined}
                onChange={(e) => onChange({ ...query, start: e.target.value || undefined })}
                className="tl-input mt-1.5 w-full"
              />
            </label>
            <label className="block text-xs font-semibold text-muted">
              To
              <input
                type="date"
                value={query.end ?? ''}
                min={available.date_min ?? undefined}
                max={available.date_max ?? undefined}
                onChange={(e) => onChange({ ...query, end: e.target.value || undefined })}
                className="tl-input mt-1.5 w-full"
              />
            </label>
          </div>

          <label className="block text-xs font-semibold text-muted">
            <span className="inline-flex items-center gap-1.5">
              Starting balance ($)
              {autoFilled ? (
                <Tooltip label="Worked out from this account's synced balance minus its all-time profit and loss. Change it if you know the real figure: a deposit or withdrawal in between would throw it off.">
                  <span className="cursor-help rounded bg-accent-soft px-1.5 text-[10px] font-bold text-accent">auto</span>
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
              className="tl-input mt-1.5 w-full font-mono tabular-nums"
            />
            <span className="mt-1 block min-h-[16px] text-[11px] font-normal" aria-live="polite">
              {noAccountSelected ? (
                <span className="text-muted">Pick an account to save this balance.</span>
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
      ) : null}
    </div>
  )
}
