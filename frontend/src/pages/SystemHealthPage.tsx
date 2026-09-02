import { Link } from 'react-router-dom'
import { useHealth } from '../lib/health'
import { useSystemOps } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import {
  SystemDiagnostics,
  SystemHealthPanel,
  SystemSafety,
} from '../components/operations/SystemView'
import { OpsSafetyBanner, SectionError } from '../components/operations/primitives'

/**
 * `/operations/system` — operational system health. `/api/health` (via the
 * app-wide HealthProvider) stays the authoritative connection + safety source;
 * `/api/operations/system` adds the deterministic safety-gate diagnostics.
 * No second health mechanism, no toggle, no go-live control.
 */
export function SystemHealthPage() {
  const health = useHealth()
  const ops = useSystemOps()

  return (
    <PageContainer
      title="System Health"
      description="Backend service status and deterministic safety-gate diagnostics. Read-only."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {ops.refreshing ? <span className="text-[11px] text-muted" aria-live="polite">Refreshing…</span> : null}
          <Link to="/operations/audit" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Audit
          </Link>
          <Link to="/evidence" className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover">
            Evidence
          </Link>
          <button
            type="button"
            onClick={() => { health.refetch(); ops.refetch() }}
            className="rounded border border-border px-2.5 py-1 text-xs text-primary hover:bg-surface-hover"
          >
            Re-check
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <OpsSafetyBanner
          broker={health.data?.live_broker_transmission}
          automationDisabled={health.data ? health.data.automation_enabled === false : true}
        />

        <SystemSafety health={health.data} connection={health.state} />

        <div className="grid gap-4 lg:grid-cols-2">
          <SystemHealthPanel
            health={health.data}
            connection={health.state}
            lastChecked={health.lastChecked}
          />
          {ops.state === 'error' && !ops.data ? (
            <div className="rounded-lg border border-border bg-surface p-4">
              <SectionError
                message={ops.error ?? 'The operations system endpoint could not be reached.'}
                onRetry={ops.refetch}
              />
            </div>
          ) : (
            <SystemDiagnostics ops={ops.data} />
          )}
        </div>

        <p className="border-t border-border-subtle pt-3 text-[11px] text-muted">
          `/api/health` is polled on a slow interval by the shell (pauses while
          hidden). The safety-gate diagnostics refresh every 20s. Host telemetry
          (CPU / RAM / uptime / latency), market-data feed health and cache
          statistics are not exposed by the current API and are not fabricated.
        </p>
      </div>
    </PageContainer>
  )
}
