import { Link } from 'react-router-dom'
import type { BacktestRunResponse } from '../../types/research'
import {
  HashChip,
  ResearchStatusTag,
  SectionCard,
  researchTone,
} from './primitives'
import { BacktestMetrics } from './BacktestMetrics'
import { EquityCurve } from './EquityCurve'
import { MonteCarloPanel } from './MonteCarloPanel'
import { WfoPanel } from './WfoPanel'
import { BacktestTradeTable } from './BacktestTradeTable'
import { timeAgo } from '../../lib/format'

function ConfigRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[11px] text-muted">{label}</dt>
      <dd className="font-mono text-[11px] tabular-nums text-primary">{value}</dd>
    </div>
  )
}

interface Props {
  result: BacktestRunResponse
  /** True when the form config no longer matches the config that produced this result. */
  stale: boolean
}

export function BacktestResultView({ result, stale }: Props) {
  const c = result.config
  const failed = result.status === 'failed'

  return (
    <div className="space-y-4">
      <SectionCard
        title="Run status"
        action={
          <div className="flex items-center gap-2">
            {stale && !failed ? (
              <ResearchStatusTag value="CONFIG CHANGED" tone="warning" size="sm" />
            ) : null}
            <ResearchStatusTag
              value={result.status.toUpperCase()}
              tone={failed ? 'negative' : researchTone(result.status)}
              size="sm"
            />
          </div>
        }
      >
        {failed ? (
          <p className="text-sm text-negative">
            {result.error ?? 'The backtest engine reported a failure.'}
          </p>
        ) : (
          <>
            {stale ? (
              <p className="mb-3 rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                The configuration has changed since this result was produced —
                run again to refresh.
              </p>
            ) : null}
            <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
              <ConfigRow label="Symbol" value={c.symbol} />
              <ConfigRow label="Timeframe" value={c.timeframe} />
              <ConfigRow label="Strategy" value={c.strategy} />
              <ConfigRow label="Mode" value={c.mode} />
              <ConfigRow label="Capital" value={`$${c.capital.toLocaleString()}`} />
              <ConfigRow label="Risk / SL / TP" value={`${c.risk_pct}% · ${c.sl_atr} · ${c.tp_atr}`} />
              {c.mode === 'standard' ? (
                <ConfigRow label="Train split" value={c.train_split} />
              ) : null}
              <ConfigRow label="Duration" value={`${result.duration_sec.toFixed(1)}s`} />
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-2 text-[11px] text-muted">
              <span>ran {timeAgo(result.ran_at) ?? 'just now'}</span>
              <span>·</span>
              <span className="flex items-center gap-1">
                config <HashChip value={result.config_id} chars={12} />
              </span>
              <span>·</span>
              <span className="font-mono text-blocked">🔒 {result.live_broker_transmission}</span>
            </div>
          </>
        )}
      </SectionCard>

      {failed ? null : (
        <>
          <BacktestMetrics
            overall={result.metrics}
            is={result.metrics_is}
            oos={result.metrics_oos}
            finalCapital={result.final_capital}
          />

          {result.mode === 'walk_forward' ? <WfoPanel result={result} /> : null}

          <div className="grid gap-4 xl:grid-cols-2">
            <EquityCurve
              points={result.equity_curve}
              total={result.equity_curve_total}
              sampled={result.equity_curve_sampled}
            />
            <MonteCarloPanel mc={result.monte_carlo} />
          </div>

          <BacktestTradeTable
            trades={result.trades}
            total={result.trades_total}
            truncated={result.trades_truncated}
          />

          <div className="flex flex-wrap gap-x-4 gap-y-1 rounded-lg border border-border-subtle bg-surface px-3 py-2 text-[11px] text-muted">
            <span className="font-semibold text-secondary">
              Historical research — not forward evidence, not an execution signal.
            </span>
            <Link
              to={`/workspace/market?symbol=${encodeURIComponent(c.symbol)}`}
              className="text-secondary hover:text-primary"
            >
              Market workspace →
            </Link>
            <Link
              to={`/workspace/risk?symbol=${encodeURIComponent(c.symbol)}`}
              className="text-secondary hover:text-primary"
            >
              Risk Gateway →
            </Link>
            <Link to="/evidence" className="text-secondary hover:text-primary">
              Forward Evidence →
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
