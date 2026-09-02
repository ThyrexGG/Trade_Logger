import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { BacktestRunRequest } from '../types/research'
import { useStrategyLab } from '../lib/useStrategyLab'
import { useBacktestRun } from '../lib/useBacktestRun'
import { PageContainer } from '../components/shell/PageContainer'
import { BacktestConfiguration } from '../components/research/BacktestConfiguration'
import { BacktestResultView } from '../components/research/BacktestResultView'
import {
  ResearchSafetyBanner,
  ResearchUnavailable,
  SectionError,
  SkeletonRows,
} from '../components/research/primitives'

/** Fields that define "the same backtest" for staleness detection. */
function configKey(r: BacktestRunRequest | null): string {
  if (!r) return ''
  return JSON.stringify([
    r.symbol, r.timeframe, r.strategy, r.mode, r.capital, r.risk_pct,
    r.sl_atr, r.tp_atr, r.train_split, r.slippage, r.commission_pct, r.fixed_spread,
  ])
}

/**
 * Backtest workspace (`/research/backtest`). Configure → Run → Inspect. The
 * "Run Backtest" POST fires only on the explicit click; StrictMode / re-renders
 * / tab switches never trigger a run.
 */
export function BacktestWorkspacePage() {
  const [searchParams] = useSearchParams()
  const lab = useStrategyLab()
  const backtest = useBacktestRun()
  const [pendingConfig, setPendingConfig] = useState<BacktestRunRequest | null>(null)

  const onConfigChange = useCallback(
    (req: BacktestRunRequest | null) => setPendingConfig(req),
    [],
  )

  const stale =
    backtest.result !== null &&
    backtest.result.status === 'complete' &&
    pendingConfig !== null &&
    configKey(pendingConfig) !== configKey(backtest.resultRequest)

  return (
    <PageContainer
      title="Backtest Workspace"
      description="Historical research backtests over the frozen strategy contract. Research-only — no broker, no live execution."
      actions={
        <Link
          to="/research/strategy"
          className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
        >
          Strategy Lab
        </Link>
      }
    >
      <div className="space-y-4">
        <ResearchSafetyBanner broker={lab.data?.live_broker_transmission} />

        {lab.state === 'loading' && !lab.data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={6} />
          </div>
        ) : lab.state === 'error' && !lab.data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError
              message={lab.error ?? 'The research service could not be reached.'}
              onRetry={lab.refetch}
            />
          </div>
        ) : lab.data ? (
          <>
            <BacktestConfiguration
              lab={lab.data}
              initialSymbol={searchParams.get('symbol')}
              running={backtest.state === 'running'}
              onRun={backtest.run}
              onConfigChange={onConfigChange}
            />

            {backtest.state === 'running' && !backtest.result ? (
              <div className="rounded-lg border border-border bg-surface p-4">
                <p className="mb-3 text-sm text-secondary" aria-live="polite">
                  Running backtest — fetching history and simulating trades…
                </p>
                <SkeletonRows rows={5} />
              </div>
            ) : null}

            {backtest.state === 'failed' && !backtest.result ? (
              <div className="rounded-lg border border-border bg-surface p-4">
                <SectionError
                  message={backtest.error ?? 'The backtest failed.'}
                  onRetry={() => pendingConfig && backtest.run(pendingConfig)}
                />
              </div>
            ) : null}

            {backtest.result ? (
              <BacktestResultView result={backtest.result} stale={stale} />
            ) : backtest.state === 'idle' ? (
              <ResearchUnavailable>
                No backtest has been run yet. Configure the parameters above and
                choose <span className="text-secondary">Run Backtest</span>.
              </ResearchUnavailable>
            ) : null}
          </>
        ) : null}
      </div>
    </PageContainer>
  )
}
