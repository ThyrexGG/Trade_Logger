import type { ReactNode } from 'react'
import type { RiskPreviewResponse } from '../../types/risk'
import type { RiskState } from '../../lib/useRiskPreview'
import { formatLots, formatPercent, formatPrice, formatUsd } from '../../lib/format'

interface RiskResultProps {
  state: RiskState
  result: RiskPreviewResponse | null
  error: string | null
  isStale: boolean
  onRetry: () => void
}

function Metric({
  label,
  children,
  hint,
}: {
  label: string
  children: ReactNode
  hint?: string
}) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-0.5 font-mono text-sm tabular-nums text-primary">{children}</p>
      {hint ? <p className="text-[10px] text-muted">{hint}</p> : null}
    </div>
  )
}

function Block() {
  return <div className="h-6 w-28 rounded bg-surface-elevated" />
}

/** Authoritative risk-preview result. Renders only fields the API returns. */
export function RiskResult({ state, result, error, isStale, onRetry }: RiskResultProps) {
  if (state === 'idle' && !result) {
    return (
      <p className="text-sm text-muted">
        Enter trade parameters and select <span className="text-secondary">Calculate Risk</span>.
      </p>
    )
  }

  if (state === 'calculating' && !result) {
    return (
      <div className="space-y-4" aria-busy="true">
        <p className="text-xs uppercase tracking-wider text-muted">Calculating risk…</p>
        <Block />
        <div className="flex gap-6">
          <Block />
          <Block />
          <Block />
        </div>
      </div>
    )
  }

  if (state === 'error' && !result) {
    return (
      <div className="text-sm">
        <p className="text-negative">Risk preview unavailable</p>
        <p className="mt-1 text-xs text-muted">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
        >
          Recalculate
        </button>
      </div>
    )
  }

  if (!result) return null

  const stopDistance = Math.abs(result.entry_price - result.stop_loss)
  const dimmed = isStale || state === 'calculating'

  return (
    <div className="space-y-4" aria-live="polite">
      {state === 'error' && error ? (
        <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
          Showing last result — recalculation failed: {error}
        </p>
      ) : null}

      {isStale ? (
        <p
          role="status"
          className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning"
        >
          Inputs changed — recalculate for an updated position size.
        </p>
      ) : null}

      {state === 'calculating' ? (
        <p className="text-[11px] text-muted">Calculating…</p>
      ) : null}

      <div className={dimmed ? 'space-y-4 opacity-60' : 'space-y-4'}>
        {result.errors.length > 0 ? (
          <div className="rounded border border-negative/40 bg-negative/10 p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-negative">
              Invalid trade configuration
            </p>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm text-negative">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {result.is_valid ? (
          <>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted">
                Recommended position
              </p>
              <p className="font-mono text-3xl font-semibold tabular-nums text-primary">
                {formatLots(result.calculated_lot_size)}
                <span className="ml-2 text-base font-normal text-muted">lots</span>
              </p>
              <p className="mt-0.5 font-mono text-xs text-secondary">
                {result.symbol} · {result.side}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
              <Metric label="Estimated risk">{formatUsd(result.actual_risk_usd)}</Metric>
              <Metric label="Risk %">{formatPercent(result.actual_risk_pct)}</Metric>
              <Metric label="Stop distance" hint="price units">
                {formatPrice(stopDistance)}
              </Metric>
              <Metric label="Est. margin">
                {formatUsd(result.estimated_margin_usd)}
              </Metric>
              <Metric label="Target risk" hint="from risk %">
                {formatUsd(result.target_risk_usd)}
              </Metric>
            </div>

            {result.take_profit_1 > 0 ? (
              <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
                <Metric label="Reward TP1">{formatUsd(result.reward_tp1_usd)}</Metric>
                <Metric label="Reward TP1 %">
                  {formatPercent(result.reward_tp1_pct)}
                </Metric>
                <Metric label="Risk : reward">{result.risk_reward_ratio}</Metric>
                {result.take_profit_2 > 0 ? (
                  <Metric label="Reward TP2">
                    {formatUsd(result.reward_tp2_usd)}
                  </Metric>
                ) : (
                  <div />
                )}
              </div>
            ) : null}
          </>
        ) : result.errors.length > 0 ? (
          <p className="text-sm text-muted">
            No valid position size — resolve the errors above.
          </p>
        ) : null}

        {result.warnings.length > 0 ? (
          <div className="rounded border border-warning/30 bg-warning/10 p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-warning">
              Risk warnings
            </p>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm text-warning">
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="border-t border-border-subtle pt-3">
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-negative">
            <span aria-hidden="true">🔒</span>
            LIVE BROKER TRANSMISSION: {result.live_broker_transmission}
          </span>
        </div>
      </div>
    </div>
  )
}
