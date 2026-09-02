import { useEffect, useState } from 'react'
import type { AnalyticsAvailable, AnalyticsQuery } from '../../types/analytics'
import { SectionCard } from '../intelligence/primitives'
import { parseNumberInput } from '../../lib/format'

/**
 * Filter bar for the analytics population: account, symbols, date range,
 * starting balance. Emits an `AnalyticsQuery`; the hook debounces the request.
 * No calculation happens here — only filter selection.
 */
export function AnalyticsControls({
  available,
  query,
  onChange,
}: {
  available: AnalyticsAvailable
  query: AnalyticsQuery
  onChange: (next: AnalyticsQuery) => void
}) {
  const selectedSymbols = query.symbols ?? []
  const [balanceText, setBalanceText] = useState(String(query.initial_balance ?? 10000))

  // keep the local balance field in sync if the query is reset elsewhere
  useEffect(() => {
    setBalanceText(String(query.initial_balance ?? 10000))
  }, [query.initial_balance])

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
              <option key={a} value={a}>{a}</option>
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
          Starting balance ($)
          <input
            value={balanceText}
            onChange={(e) => {
              setBalanceText(e.target.value)
              const n = parseNumberInput(e.target.value)
              if (n !== null && n > 0) onChange({ ...query, initial_balance: n })
            }}
            inputMode="decimal"
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs tabular-nums text-primary focus:border-accent focus:outline-none"
          />
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
