import { useState } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import {
  MetricCard,
  ResearchSafetyBanner,
  ResearchStatusTag,
  ResearchUnavailable,
  SectionCard,
  SectionError,
  SkeletonRows,
} from '../components/research/primitives'
import { useTradeSetup } from '../lib/useTradeSetup'
import type { SetupState } from '../types/tradeSetup'

const ASSETS = [
  'XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF',
  'EURJPY', 'GBPJPY', 'AUDJPY',
]

const STATE_TONE: Record<SetupState, 'positive' | 'warning' | 'negative' | 'neutral' | 'info'> = {
  READY: 'positive',
  SETUP_FORMING: 'info',
  WATCH: 'warning',
  STALE: 'warning',
  INSUFFICIENT_EVIDENCE: 'neutral',
  NO_SETUP: 'neutral',
  INVALIDATED: 'negative',
}

const fmt = (v: number | null | undefined, d = 5) =>
  v === null || v === undefined ? '—' : v.toFixed(d)

/**
 * Trade Setup (`/workspace/trade-setup`) — Phase 72.
 * Research answers *what historically has an edge*; this answers *does the
 * current market satisfy that validated edge right now*. A setup is only READY
 * behind a VALIDATED strategy with every mandatory condition passing. The
 * deterministic engine owns the state — nothing here can override it.
 */
export function TradeSetupPage() {
  const [asset, setAsset] = useState('XAUUSD')
  const { list, setup, state, error, refetch } = useTradeSetup(asset)

  return (
    <PageContainer
      title="Trade Setup"
      description="Does today's market satisfy a validated strategy for this instrument? READY only behind a VALIDATED edge with every mandatory condition met. Research-only — no execution."
    >
      <ResearchSafetyBanner broker={setup?.safety_barrier.live_broker_transmission ?? 'BLOCKED'} />

      <div className="mt-4 flex flex-wrap gap-1.5">
        {ASSETS.map((a) => {
          const li = list?.setups.find((s) => s.asset === a)
          const active = a === asset
          return (
            <button
              key={a}
              type="button"
              onClick={() => setAsset(a)}
              className={`rounded border px-2 py-1 font-mono text-[11px] ${
                active
                  ? 'border-info bg-info/10 text-info'
                  : 'border-border-subtle text-secondary hover:border-info/40'
              }`}
            >
              {a}
              {li ? (
                <span className="ml-1.5 text-[9px] text-muted">{li.state.replace(/_/g, ' ')}</span>
              ) : null}
            </button>
          )
        })}
      </div>

      {state === 'loading' && !setup ? (
        <div className="mt-4">
          <SkeletonRows rows={5} />
        </div>
      ) : null}
      {state === 'error' && !setup ? (
        <div className="mt-4">
          <SectionError message={error ?? 'Trade setup unavailable.'} onRetry={refetch} />
        </div>
      ) : null}

      {setup ? (
        <>
          {/* 3-second glance (Phase 60 principle) */}
          <div className="mt-4 rounded-lg border border-border-subtle bg-surface-elevated/40 p-4">
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="font-mono text-2xl text-primary">{setup.asset}</span>
              {setup.direction ? (
                <span
                  className={`font-mono text-lg ${
                    setup.direction === 'LONG' ? 'text-positive' : 'text-negative'
                  }`}
                >
                  {setup.direction}
                </span>
              ) : null}
              <ResearchStatusTag value={setup.state.replace(/_/g, ' ')} tone={STATE_TONE[setup.state]} />
            </div>
            <p className="mt-1.5 text-sm text-secondary">{setup.reason}</p>
            {setup.waiting_for ? (
              <p className="mt-1 text-xs text-warning">Waiting for: {setup.waiting_for}</p>
            ) : null}
          </div>

          {/* Levels — only when READY */}
          {setup.state === 'READY' && setup.entry !== null ? (
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Entry" value={fmt(setup.entry)} />
              <MetricCard label="Stop loss" value={fmt(setup.stop_loss)} tone="negative" />
              <MetricCard label="Take profit" value={fmt(setup.take_profit)} tone="positive" />
              <MetricCard label="R:R" value={setup.risk_reward ?? '—'} />
            </div>
          ) : null}

          {/* Strategy validation */}
          <div className="mt-4">
            <SectionCard title="Strategy validation">
              {setup.strategy_id ? (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <MetricCard label="Strategy" value={setup.strategy_id} sub={setup.strategy_family ?? ''} />
                  <MetricCard
                    label="OOS E[R]"
                    value={String(setup.strategy_validation.oos_expectancy_r ?? '—')}
                  />
                  <MetricCard
                    label="OOS PF"
                    value={String(setup.strategy_validation.oos_profit_factor ?? '—')}
                  />
                  <MetricCard
                    label="OOS N"
                    value={String(setup.strategy_validation.oos_trades ?? '—')}
                  />
                  <MetricCard
                    label="OOS CI"
                    value={String(setup.strategy_validation.oos_ci ?? '—')}
                  />
                  <MetricCard
                    label="WFO stability"
                    value={String(setup.strategy_validation.wfo_stability ?? '—')}
                  />
                </div>
              ) : (
                <ResearchUnavailable>
                  No validated strategy for {setup.asset}. Phase 70/71 discovery found none clearing
                  positive OOS lower-CI + N≥50 + WFO stability on the available 1h/1d data. This is
                  the honest state — the engine only produces READY behind a VALIDATED edge.
                </ResearchUnavailable>
              )}
            </SectionCard>
          </div>

          {/* Conditions checklist */}
          {setup.conditions.length ? (
            <div className="mt-4">
              <SectionCard title="Setup conditions">
                <ul className="space-y-1.5 text-xs">
                  {setup.conditions.map((c) => (
                    <li key={c.name} className="flex items-start gap-2">
                      <span
                        className={`mt-0.5 font-mono ${
                          c.passed === true
                            ? 'text-positive'
                            : c.passed === false
                              ? 'text-negative'
                              : 'text-muted'
                        }`}
                      >
                        {c.passed === true ? '✓' : c.passed === false ? '✗' : '·'}
                      </span>
                      <span>
                        <span className="text-primary">{c.name}</span>
                        {c.mandatory ? null : (
                          <span className="ml-1 text-[10px] text-muted">(optional)</span>
                        )}
                        <span className="block text-[11px] text-muted">{c.detail}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </div>
          ) : null}

          <p className="mt-3 text-[10px] text-muted">
            Evidence provenance: {setup.evidence_provenance.join(', ') || '—'} · mode {setup.mode} ·
            generated {new Date(setup.generated_at).toLocaleString()}
          </p>
        </>
      ) : null}
    </PageContainer>
  )
}
