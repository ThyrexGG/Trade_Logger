import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ResearchAuditRequest } from '../types/research'
import { useStrategyLab } from '../lib/useStrategyLab'
import { useResearchAudit } from '../lib/useResearchAudit'
import { PageContainer } from '../components/shell/PageContainer'
import { ResearchAuditView } from '../components/research/ResearchAuditView'
import { inputClass } from '../components/risk/fields'
import {
  ResearchSafetyBanner,
  ResearchUnavailable,
  SectionCard,
  SectionError,
  SkeletonRows,
} from '../components/research/primitives'
import { parseNumberInput } from '../lib/format'

/**
 * Research Lab — statistical edge / adversarial audit (`/research/audit`).
 * Configure → Run → Inspect. Migrated from the Streamlit "GENERAL RESEARCH &
 * EDGE AUDIT" tab. The POST fires only on the explicit "Run audit" click.
 * Research-only: no broker, no execution, no automation.
 */
export function ResearchAuditPage() {
  const lab = useStrategyLab()
  const audit = useResearchAudit()

  const [symbol, setSymbol] = useState('')
  const [timeframe, setTimeframe] = useState('')
  const [strategy, setStrategy] = useState('')
  const [raw, setRaw] = useState<Record<string, string>>({
    capital: '10000',
    risk_pct: '1',
    sl_atr: '1.5',
    tp_atr: '2',
    train_split: '0.6',
    slippage: '0.0001',
    commission_pct: '0.01',
    fixed_spread: '0',
  })

  const d = lab.data
  const symbols = d?.supported_symbols ?? []
  const timeframes = useMemo(() => (d?.timeframes ?? []).map((t) => t.timeframe), [d])
  const strategyNames = useMemo(() => (d?.strategies ?? []).map((s) => s.name), [d])

  const sym = symbol || symbols[0] || 'XAUUSD'
  const tf = timeframe || timeframes[0] || '1h'
  const strat = strategy || d?.backtest_defaults.strategy || strategyNames[0] || 'Trend Continuation'

  const nums = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, parseNumberInput(v)]),
  ) as Record<string, number | null>

  const splitValid = nums.train_split !== null && nums.train_split >= 0.1 && nums.train_split <= 0.9
  const capitalValid = nums.capital !== null && nums.capital > 0
  const canRun =
    audit.state !== 'running' && lab.state === 'ready' && splitValid && capitalValid &&
    Object.values(nums).every((v) => v !== null)

  function run() {
    if (!canRun) return
    const req: ResearchAuditRequest = {
      symbol: sym,
      timeframe: tf,
      strategy: strat,
      risk_pct: nums.risk_pct as number,
      sl_atr: nums.sl_atr as number,
      tp_atr: nums.tp_atr as number,
      capital: nums.capital as number,
      slippage: nums.slippage as number,
      commission_pct: nums.commission_pct as number,
      fixed_spread: nums.fixed_spread as number,
      train_split: nums.train_split as number,
    }
    audit.run(req)
  }

  const Fld = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-muted">{label}</span>
      {children}
    </label>
  )

  const field = (key: string, label: string) => (
    <Fld label={label}>
      <input
        value={raw[key]}
        inputMode="decimal"
        onChange={(e) => setRaw((p) => ({ ...p, [key]: e.target.value }))}
        disabled={audit.state === 'running'}
        className={inputClass}
      />
    </Fld>
  )

  return (
    <PageContainer
      title="Research Lab — Edge Audit"
      description="Statistical edge & adversarial audit over the frozen strategy contract. Research-only — no broker, no live execution."
      actions={
        <Link to="/research/backtest" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
          Backtest workspace
        </Link>
      }
    >
      <div className="space-y-4">
        <ResearchSafetyBanner />

        {lab.state === 'loading' ? (
          <div className="rounded-lg border border-border bg-surface p-4"><SkeletonRows rows={4} /></div>
        ) : lab.state === 'error' ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={lab.error ?? 'Could not load the research configuration.'} onRetry={lab.refetch} />
          </div>
        ) : d ? (
          <SectionCard title="Audit configuration">
            <div className="grid gap-3 sm:grid-cols-3">
              <Fld label="Symbol">
                <select value={sym} onChange={(e) => setSymbol(e.target.value)} disabled={audit.state === 'running'} className={inputClass}>
                  {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Fld>
              <Fld label="Timeframe">
                <select value={tf} onChange={(e) => setTimeframe(e.target.value)} disabled={audit.state === 'running'} className={inputClass}>
                  {timeframes.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </Fld>
              <Fld label="Strategy">
                <select value={strat} onChange={(e) => setStrategy(e.target.value)} disabled={audit.state === 'running'} className={inputClass}>
                  {strategyNames.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Fld>
              {field('capital', 'Capital ($)')}
              {field('risk_pct', 'Risk per trade (%)')}
              {field('train_split', 'Train split (0.1–0.9)')}
              {field('sl_atr', 'SL (ATR)')}
              {field('tp_atr', 'TP (ATR)')}
              {field('slippage', 'Slippage')}
              {field('commission_pct', 'Commission (%)')}
              {field('fixed_spread', 'Fixed spread')}
            </div>

            {!splitValid ? (
              <p className="mt-2 text-[11px] text-negative">Train split must be between 0.1 and 0.9.</p>
            ) : null}

            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={run}
                disabled={!canRun}
                className="rounded border border-accent/40 bg-accent/10 px-3 py-1 text-xs text-accent disabled:opacity-40"
              >
                {audit.state === 'running' ? 'Running audit…' : 'Run audit'}
              </button>
              {audit.result ? (
                <button type="button" onClick={audit.reset} className="rounded border border-border px-2.5 py-1 text-xs text-secondary hover:text-primary">
                  Clear
                </button>
              ) : null}
              <span className="font-mono text-[10px] text-muted">
                runs one backtest (~2–12s) then the canonical research functions · no order is placed
              </span>
            </div>
          </SectionCard>
        ) : null}

        {audit.state === 'idle' ? (
          <ResearchUnavailable>
            Configure the strategy / symbol / timeframe above and run the audit.
          </ResearchUnavailable>
        ) : audit.state === 'failed' && !audit.result ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError message={audit.error ?? 'The audit failed.'} onRetry={run} />
          </div>
        ) : audit.result ? (
          <>
            {audit.state === 'running' ? (
              <p className="rounded border border-info/30 bg-info/10 px-2 py-1 text-[11px] text-info">Running a new audit — showing the previous result.</p>
            ) : null}
            {audit.state === 'failed' && audit.error ? (
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">Last run failed: {audit.error}</p>
            ) : null}
            <ResearchAuditView data={audit.result} />
          </>
        ) : (
          <div className="rounded-lg border border-border bg-surface p-4"><SkeletonRows rows={8} /></div>
        )}
      </div>
    </PageContainer>
  )
}
