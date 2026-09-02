import { useState } from 'react'
import type { StrategyLabResponse } from '../../types/research'
import { ResearchStatusTag, SectionCard } from './primitives'

/** Frozen strategy contract identity + research mode. */
export function StrategyIdentity({ data }: { data: StrategyLabResponse }) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard?.writeText(data.contract_hash).then(
      () => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1500)
      },
      () => undefined,
    )
  }

  return (
    <SectionCard
      title="Strategy identity"
      action={<ResearchStatusTag value={`MODE ${data.mode}`} tone="info" size="sm" />}
    >
      <dl className="space-y-2.5 text-xs">
        <div>
          <dt className="text-[10px] uppercase tracking-wider text-muted">
            Strategy contract SHA-256 (frozen)
          </dt>
          <dd className="mt-0.5 flex flex-wrap items-center gap-2">
            <code className="break-all font-mono text-[11px] text-secondary">
              {data.contract_hash}
            </code>
            <button
              type="button"
              onClick={copy}
              className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] text-primary hover:bg-surface-hover"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </dd>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">
              Registered strategies
            </dt>
            <dd className="mt-0.5 font-mono text-primary">{data.strategies.length}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">
              Supported symbols
            </dt>
            <dd className="mt-0.5 font-mono text-primary">
              {data.supported_symbols.length}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">Timeframes</dt>
            <dd className="mt-0.5 font-mono text-primary">{data.timeframes.length}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted">Execution</dt>
            <dd className="mt-0.5 font-mono text-[11px] text-blocked">
              🔒 {data.live_broker_transmission}
            </dd>
          </div>
        </div>
      </dl>
      <p className="mt-3 text-[11px] text-muted">
        This is a <strong>research configuration</strong> surface — the strategy
        contract identity is authoritative and read-only. Strategy name / version
        per-strategy are listed below; a configuration ID is assigned per
        backtest run.
      </p>
    </SectionCard>
  )
}
