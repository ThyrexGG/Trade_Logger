import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useWatchlist } from '../lib/useWatchlist'
import { useMarketSnapshot } from '../lib/useMarketSnapshot'
import { Watchlist } from '../components/workspace/Watchlist'
import { MarketSnapshot } from '../components/workspace/MarketSnapshot'

/**
 * Trading workspace: real watchlist (one request) + market snapshot for the
 * selected symbol (one request per selection, race-safe). No fabricated data,
 * no per-row snapshot fetches.
 */
export function MarketWorkspacePage() {
  const watchlist = useWatchlist()
  const [searchParams] = useSearchParams()
  const requestedSymbol = searchParams.get('symbol')?.toUpperCase() || null
  const [selected, setSelected] = useState<string | null>(requestedSymbol)

  // Honour a ?symbol= handoff (from intelligence / risk); otherwise default to
  // the backend's first configured instrument. Recover if the current
  // selection disappears from a refreshed list.
  useEffect(() => {
    if (requestedSymbol && requestedSymbol !== selected) {
      setSelected(requestedSymbol)
    }
  }, [requestedSymbol]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (watchlist.items.length === 0) return
    const stillPresent = watchlist.items.some((i) => i.symbol === selected)
    if (!selected || (!stillPresent && !requestedSymbol)) {
      setSelected(watchlist.items[0].symbol)
    }
  }, [watchlist.items, selected, requestedSymbol])

  const snapshot = useMarketSnapshot(selected)
  const onSelect = useCallback((symbol: string) => setSelected(symbol), [])

  return (
    <div className="flex flex-col lg:h-[calc(100vh-var(--tl-topbar-height))] lg:flex-row">
      <div className="flex max-h-[46vh] min-h-0 flex-col lg:max-h-none lg:w-[330px] lg:shrink-0">
        <Watchlist
          state={watchlist.state}
          items={watchlist.items}
          updatedAt={watchlist.updatedAt}
          error={watchlist.error}
          refreshing={watchlist.refreshing}
          selectedSymbol={selected}
          onSelect={onSelect}
          onRetry={watchlist.refetch}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <MarketSnapshot
          symbol={selected}
          state={snapshot.state}
          data={snapshot.data}
          error={snapshot.error}
          refreshing={snapshot.refreshing}
          onRetry={snapshot.refetch}
        />
      </div>
    </div>
  )
}
