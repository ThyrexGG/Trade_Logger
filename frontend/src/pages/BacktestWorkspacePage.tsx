import { useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { BacktestRunRequest, ResearchAuditRequest } from '../types/research'
import { useStrategyLab } from '../lib/useStrategyLab'
import { useBacktestRun } from '../lib/useBacktestRun'
import { useResearchAudit } from '../lib/useResearchAudit'
import { PageContainer } from '../components/shell/PageContainer'
import { BacktestConfiguration } from '../components/research/BacktestConfiguration'
import { BacktestResultView } from '../components/research/BacktestResultView'
import { ResearchAuditView } from '../components/research/ResearchAuditView'
import {
  ResearchSafetyBanner,
  ResearchUnavailable,
  SectionError,
  SkeletonRows,
} from '../components/research/primitives'

/** Fields that define "the same run" for staleness detection. */
function configKey(r: BacktestRunRequest | null): string {
  if (!r) return ''
  return JSON.stringify([
    r.symbol, r.timeframe, r.strategy, r.mode, r.capital, r.risk_pct,
    r.sl_atr, r.tp_atr, r.train_split, r.slippage, r.commission_pct, r.fixed_spread,
  ])
}

function toAuditRequest(r: BacktestRunRequest): ResearchAuditRequest {
  const { symbol, timeframe, strategy, risk_pct, sl_atr, tp_atr, capital,
    slippage, commission_pct, fixed_spread, train_split } = r
  return { symbol, timeframe, strategy, risk_pct, sl_atr, tp_atr, capital,
    slippage, commission_pct, fixed_spread, train_split }
}

type ResultTab = 'backtest' | 'audit'

/**
 * Backtest & Edge Audit workspace (`/research/backtest`). One shared config
 * (symbol / timeframe / strategy / risk / costs); two analyses over it:
 *
 *  - **Backtest** — equity curve, trade stats, walk-forward and Monte Carlo.
 *  - **Edge audit** — R-multiple distribution, bootstrap CIs, dimensional
 *    breakdown and adversarial cost/slippage stress.
 *
 * Each POST fires only on its explicit button; re-renders / tab switches never
 * trigger a run. Research-only — no broker, no live execution.
 */
export function BacktestWorkspacePage() {
  const [searchParams] = useSearchParams()
  const lab = useStrategyLab()
  const backtest = useBacktestRun()
  const audit = useResearchAudit()
  const [pendingConfig, setPendingConfig] = useState<BacktestRunRequest | null>(null)
  const [tab, setTab] = useState<ResultTab>('backtest')

  const onConfigChange = useCallback(
    (req: BacktestRunRequest | null) => setPendingConfig(req),
    [],
  )

  const runBacktest = useCallback(
    (req: BacktestRunRequest) => {
      setTab('backtest')
      backtest.run(req)
    },
    [backtest],
  )

  const runAudit = useCallback(() => {
    if (!pendingConfig) return
    setTab('audit')
    audit.run(toAuditRequest(pendingConfig))
  }, [audit, pendingConfig])

  const stale =
    backtest.result !== null &&
    backtest.result.status === 'complete' &&
    pendingConfig !== null &&
    configKey(pendingConfig) !== configKey(backtest.resultRequest)

  const hasBacktest = backtest.result !== null || backtest.state === 'running'
  const hasAudit = audit.result !== null || audit.state === 'running'
  const auditBusy = audit.state === 'running'

  const tabs = useMemo(
    () =>
      [
        { id: 'backtest' as const, label: 'Backtest', show: hasBacktest },
        { id: 'audit' as const, label: 'Edge audit', show: hasAudit },
      ].filter((t) => t.show),
    [hasBacktest, hasAudit],
  )

  return (
    <PageContainer
      title="Backtest & Edge Audit"
      description="One configuration, two analyses over the frozen strategy contract: a historical backtest (equity, walk-forward, Monte Carlo) and a statistical edge / adversarial audit (R-multiples, bootstrap CIs, cost stress). Research-only — no broker, no live execution."
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
              onRun={runBacktest}
              onConfigChange={onConfigChange}
            />

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={runAudit}
                disabled={!pendingConfig || auditBusy}
                className="rounded border border-accent/40 bg-accent/10 px-3 py-1 text-xs text-accent disabled:opacity-40"
              >
                {auditBusy ? 'Running edge audit…' : 'Run edge audit'}
              </button>
              <span className="font-mono text-[10px] text-muted">
                uses the same configuration · runs one backtest then the canonical audit functions
                (~2–12s) · no order is placed
              </span>
            </div>

            {tabs.length > 1 ? (
              <div className="flex gap-1 border-b border-border-subtle">
                {tabs.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={`-mb-px border-b-2 px-3 py-1.5 text-xs ${
                      tab === t.id
                        ? 'border-accent text-primary'
                        : 'border-transparent text-muted hover:text-secondary'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            ) : null}

            {(tab === 'backtest' || !hasAudit) && hasBacktest ? (
              <>
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
                      onRetry={() => pendingConfig && runBacktest(pendingConfig)}
                    />
                  </div>
                ) : null}
                {backtest.result ? (
                  <BacktestResultView result={backtest.result} stale={stale} />
                ) : null}
              </>
            ) : null}

            {tab === 'audit' && hasAudit ? (
              <>
                {audit.state === 'running' && !audit.result ? (
                  <div className="rounded-lg border border-border bg-surface p-4">
                    <p className="mb-3 text-sm text-secondary" aria-live="polite">
                      Running edge audit — backtest then bootstrap / stress…
                    </p>
                    <SkeletonRows rows={6} />
                  </div>
                ) : null}
                {audit.state === 'failed' && !audit.result ? (
                  <div className="rounded-lg border border-border bg-surface p-4">
                    <SectionError message={audit.error ?? 'The audit failed.'} onRetry={runAudit} />
                  </div>
                ) : null}
                {audit.result ? (
                  <>
                    {audit.state === 'running' ? (
                      <p className="rounded border border-info/30 bg-info/10 px-2 py-1 text-[11px] text-info">
                        Running a new audit — showing the previous result.
                      </p>
                    ) : null}
                    {audit.state === 'failed' && audit.error ? (
                      <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                        Last run failed: {audit.error}
                      </p>
                    ) : null}
                    <ResearchAuditView data={audit.result} />
                  </>
                ) : null}
              </>
            ) : null}

            {!hasBacktest && !hasAudit && backtest.state === 'idle' ? (
              <ResearchUnavailable>
                Configure the parameters above, then <span className="text-secondary">Run
                Backtest</span> for the equity/WFO/MC view or <span className="text-secondary">Run
                edge audit</span> for the statistical / adversarial view.
              </ResearchUnavailable>
            ) : null}
          </>
        ) : null}
      </div>
    </PageContainer>
  )
}
