import { Link } from 'react-router-dom'
import { useStrategyLab } from '../lib/useStrategyLab'
import { PageContainer } from '../components/shell/PageContainer'
import { StrategyIdentity } from '../components/research/StrategyIdentity'
import { StrategyConfiguration } from '../components/research/StrategyConfiguration'
import { ResearchMethodology } from '../components/research/ResearchMethodology'
import {
  ResearchSafetyBanner,
  SectionError,
  SkeletonRows,
} from '../components/research/primitives'

/**
 * Strategy Lab (`/research/strategy`). Read-only research configuration surface:
 * frozen strategy contract, registered strategies, the authoritative research /
 * backtester defaults, and backtest methodology. No "save" — the backend
 * exposes no strategy-write endpoint and none is faked.
 */
export function StrategyLabPage() {
  const { state, data, error, refetch } = useStrategyLab()

  return (
    <PageContainer
      title="Strategy Lab"
      description="Research configuration and methodology for the frozen strategy contract. Read-only — nothing here is editable or executed."
      actions={
        <div className="flex flex-wrap gap-2">
          <Link
            to="/research/backtest"
            className="rounded border border-accent/50 bg-accent/10 px-2.5 py-1 text-xs font-semibold text-accent hover:bg-accent/20"
          >
            Backtest workspace
          </Link>
          <Link
            to="/evidence/governance"
            className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
          >
            Evidence Governance
          </Link>
        </div>
      }
    >
      <div className="space-y-4">
        <ResearchSafetyBanner broker={data?.live_broker_transmission} />

        {state === 'loading' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SkeletonRows rows={8} />
          </div>
        ) : state === 'error' && !data ? (
          <div className="rounded-lg border border-border bg-surface p-4">
            <SectionError
              message={error ?? 'The research service could not be reached.'}
              onRetry={refetch}
            />
          </div>
        ) : data ? (
          <>
            <StrategyIdentity data={data} />
            <ResearchMethodology data={data} />
            <StrategyConfiguration data={data} />

            <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
              Not exposed by the current research API: editable strategy
              parameters, per-strategy filter/regime/SMC configuration detail,
              dataset period metadata, and a strategy-write endpoint. Historical
              research is separate from Forward Evidence and from live execution.
            </p>
          </>
        ) : null}
      </div>
    </PageContainer>
  )
}
