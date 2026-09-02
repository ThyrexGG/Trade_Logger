import { memo } from 'react'
import type { WatchlistItem } from '../../types/market'
import { formatPrice } from '../../lib/format'
import { StateTag } from './StateTag'

interface WatchlistRowProps {
  item: WatchlistItem
  selected: boolean
  onSelect: (symbol: string) => void
}

function WatchlistRowImpl({ item, selected, onSelect }: WatchlistRowProps) {
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(item.symbol)}
        className={[
          'flex w-full flex-col gap-1 border-l-2 px-3 py-2 text-left transition-colors',
          selected
            ? 'border-accent bg-surface-hover'
            : 'border-transparent hover:bg-surface-elevated',
        ].join(' ')}
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className="flex items-center gap-1.5 truncate">
            <span className="font-mono text-sm font-semibold text-primary">
              {item.display}
            </span>
            {selected ? (
              <span className="sr-only">(selected)</span>
            ) : null}
          </span>
          <span className="font-mono text-sm tabular-nums text-primary">
            {formatPrice(item.price)}
          </span>
        </div>

        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-[11px] text-muted">{item.name}</span>
          <span className="shrink-0 rounded bg-surface-elevated px-1 text-[9px] font-semibold uppercase tracking-wide text-muted">
            {item.asset_class}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1">
          <StateTag label="4H" value={item.bias_4h} />
          <StateTag label="15M" value={item.bias_15m} />
          <StateTag value={item.setup_state} />
        </div>
      </button>
    </li>
  )
}

/** Memoised: a snapshot refresh for the selected symbol must not re-render rows. */
export const WatchlistRow = memo(WatchlistRowImpl)
