import { useId, useMemo, useRef, useState } from 'react'
import type { WatchlistItem } from '../../types/market'
import type { LoadState } from '../../lib/useWatchlist'
import { timeAgo } from '../../lib/format'
import { SearchIcon } from '../../lib/icons'
import { WatchlistRow } from './WatchlistRow'

interface WatchlistProps {
  state: LoadState
  items: WatchlistItem[]
  updatedAt: string | null
  error: string | null
  refreshing: boolean
  selectedSymbol: string | null
  onSelect: (symbol: string) => void
  onRetry: () => void
}

function matches(item: WatchlistItem, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return (
    item.symbol.toLowerCase().includes(q) ||
    item.display.toLowerCase().includes(q) ||
    item.name.toLowerCase().includes(q) ||
    item.asset_class.toLowerCase().includes(q)
  )
}

function RowSkeleton() {
  return (
    <li className="flex flex-col gap-1.5 px-3 py-2">
      <div className="h-3.5 w-2/3 rounded bg-surface-elevated" />
      <div className="h-2.5 w-1/2 rounded bg-surface-elevated" />
      <div className="h-3 w-3/4 rounded bg-surface-elevated" />
    </li>
  )
}

/** Configured watchlist with client-side search. One request feeds the list. */
export function Watchlist({
  state,
  items,
  updatedAt,
  error,
  refreshing,
  selectedSymbol,
  onSelect,
  onRetry,
}: WatchlistProps) {
  const [query, setQuery] = useState('')
  const searchId = useId()
  const listRef = useRef<HTMLUListElement>(null)

  const filtered = useMemo(
    () => items.filter((item) => matches(item, query)),
    [items, query],
  )

  const onListKeyDown = (e: React.KeyboardEvent<HTMLUListElement>) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    const buttons = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>('button') ?? [],
    )
    const idx = buttons.indexOf(document.activeElement as HTMLButtonElement)
    if (idx === -1) return
    e.preventDefault()
    const next = e.key === 'ArrowDown' ? idx + 1 : idx - 1
    buttons[Math.max(0, Math.min(buttons.length - 1, next))]?.focus()
  }

  return (
    <section
      aria-label="Watchlist"
      className="flex min-h-0 flex-col border-b border-border-subtle lg:border-b-0 lg:border-r"
    >
      <header className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex items-baseline gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Watchlist
          </h2>
          {state === 'ready' ? (
            <span className="text-[11px] tabular-nums text-muted">
              {filtered.length}/{items.length}
            </span>
          ) : null}
        </div>
        <span className="text-[11px] text-muted" aria-live="polite">
          {refreshing
            ? 'Refreshing…'
            : updatedAt
              ? (timeAgo(updatedAt) ?? '')
              : ''}
        </span>
      </header>

      <div className="px-3 pb-2">
        <label htmlFor={searchId} className="sr-only">
          Filter watchlist by symbol or name
        </label>
        <div className="flex items-center gap-2 rounded border border-border bg-background px-2">
          <SearchIcon className="h-3.5 w-3.5 shrink-0 text-muted" />
          <input
            id={searchId}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter… (e.g. USD)"
            autoComplete="off"
            className="w-full bg-transparent py-1.5 text-sm text-primary placeholder:text-muted focus:outline-none"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="shrink-0 rounded px-1 text-[11px] text-muted hover:text-primary"
              aria-label="Clear filter"
            >
              Clear
            </button>
          ) : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {state === 'loading' ? (
          <ul aria-hidden="true">
            {Array.from({ length: 6 }).map((_, i) => (
              <RowSkeleton key={i} />
            ))}
          </ul>
        ) : state === 'error' ? (
          <div className="px-3 py-6 text-sm">
            <p className="text-negative">Watchlist unavailable</p>
            <p className="mt-1 text-xs text-muted">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
            >
              Retry
            </button>
          </div>
        ) : items.length === 0 ? (
          <p className="px-3 py-6 text-sm text-muted">
            No instruments are configured in the watchlist.
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-3 py-6 text-sm text-muted">
            No instruments match “{query}”.
          </p>
        ) : (
          <ul ref={listRef} onKeyDown={onListKeyDown}>
            {filtered.map((item) => (
              <WatchlistRow
                key={item.symbol}
                item={item}
                selected={item.symbol === selectedSymbol}
                onSelect={onSelect}
              />
            ))}
          </ul>
        )}
      </div>

      {state === 'ready' && error ? (
        <p className="border-t border-border-subtle px-3 py-1.5 text-[11px] text-warning">
          Showing last good data — refresh failed
        </p>
      ) : null}
    </section>
  )
}
