import type { ReactNode } from 'react'
import type { OperationsSystemResponse } from '../../types/operations'
import type { HealthResponse } from '../../types/health'
import type { ConnectionState } from '../../lib/health'
import { CheckRow, OpsStatusTag, SectionCard, opsTone } from './primitives'
import { timeAgo } from '../../lib/format'

function KV({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border-subtle/60 py-1.5 last:border-0">
      <span className="text-xs text-secondary">{label}</span>
      <span className="text-right font-mono text-xs text-primary">{children}</span>
    </div>
  )
}

/** Hard safety flags — always from `/api/health` (authoritative), shown big. */
export function SystemSafety({
  health,
  connection,
}: {
  health: HealthResponse | null
  connection: ConnectionState
}) {
  const automationOff = health ? health.automation_enabled === false : true
  const broker = health?.live_broker_transmission ?? 'BLOCKED'
  return (
    <SectionCard title="Safety state">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className={`rounded border px-3 py-3 ${automationOff ? 'border-positive/30 bg-positive/5' : 'border-negative/40 bg-negative/10'}`}>
          <p className="text-[10px] uppercase tracking-wider text-muted">Live automation</p>
          <p className={`mt-1 font-mono text-xl font-semibold ${automationOff ? 'text-positive' : 'text-negative'}`}>
            {automationOff ? 'DISABLED' : 'ENABLED'}
          </p>
        </div>
        <div className="rounded border border-negative/40 bg-negative/10 px-3 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted">Broker transmission</p>
          <p className="mt-1 font-mono text-xl font-semibold text-negative">🔒 {broker}</p>
        </div>
      </div>
      <p className="mt-3 text-[11px] text-muted">
        Authoritative fail-closed flags from <code>/api/health</code>
        {connection !== 'connected' ? ' (currently unreachable — last known values shown)' : ''}.
        There is no toggle, enable or go-live control anywhere in this application.
      </p>
    </SectionCard>
  )
}

/** API + service identity from /api/health. */
export function SystemHealthPanel({
  health,
  connection,
  lastChecked,
}: {
  health: HealthResponse | null
  connection: ConnectionState
  lastChecked: Date | null
}) {
  return (
    <SectionCard
      title="API health"
      action={
        <OpsStatusTag
          value={connection === 'connected' ? 'CONNECTED' : connection === 'loading' ? 'CHECKING' : 'UNREACHABLE'}
          tone={connection === 'connected' ? 'positive' : connection === 'loading' ? 'warning' : 'negative'}
          size="sm"
        />
      }
    >
      <KV label="Reported status">{health?.status ?? '—'}</KV>
      <KV label="Service">{health ? `${health.app_name} v${health.version}` : '—'}</KV>
      <KV label="Endpoint"><span className="text-muted">/api/health</span></KV>
      <KV label="Last checked">{lastChecked ? timeAgo(lastChecked.toISOString()) ?? '—' : '—'}</KV>
      <KV label="Server time">{health ? new Date(health.timestamp).toLocaleTimeString() : '—'}</KV>
    </SectionCard>
  )
}

/** Deterministic PAPER-mode safety-gate diagnostics from system_health. */
export function SystemDiagnostics({ ops }: { ops: OperationsSystemResponse | null }) {
  if (!ops) {
    return (
      <SectionCard title="Safety-gate diagnostics">
        <p className="text-xs text-muted">Diagnostics unavailable.</p>
      </SectionCard>
    )
  }
  const g = ops.safety_gate
  const recon = g.reconciliation
  return (
    <SectionCard
      title="Safety-gate diagnostics"
      action={<OpsStatusTag value={g.overall_status} tone={opsTone(g.overall_status)} size="sm" />}
    >
      <CheckRow label="Global kill switch" ok={g.kill_switch_engaged === null ? null : !g.kill_switch_engaged} okText="not engaged" badText="ENGAGED" />
      <CheckRow label="Emergency halt" ok={g.emergency_halt_engaged === null ? null : !g.emergency_halt_engaged} okText="not engaged" badText="ENGAGED" />
      <CheckRow label="Database connectivity" ok={g.database_connected} okText="connected" badText="unreachable" />
      <CheckRow
        label="Unresolved UNKNOWN orders"
        ok={g.unresolved_unknown_orders_count === null ? null : g.unresolved_unknown_orders_count === 0}
        okText={`${g.unresolved_unknown_orders_count ?? 0} (clear)`}
        badText={`${g.unresolved_unknown_orders_count ?? '?'} pending`}
      />
      <CheckRow
        label="Reconciliation worker"
        ok={recon?.healthy ?? null}
        okText={recon?.status ?? 'healthy'}
        badText={recon?.status ?? 'unhealthy'}
      />
      {recon?.reason ? <p className="mt-1 text-[11px] text-muted">{recon.reason}</p> : null}

      <div className="mt-3 rounded border border-info/20 bg-info/5 px-2.5 py-2 text-[11px] text-muted">
        <span className="font-mono text-info">Automation pre-flight: {g.automation_allowed ? 'would permit' : 'would block'}</span>{' '}
        — this is the deterministic gate <code>system_health.evaluate_system_health</code> would apply
        <em> if</em> automation were enabled. It does not enable anything; live automation is
        {' '}{ops.live_automation_enabled ? 'ENABLED' : 'DISABLED'} regardless.
      </div>
      {g.reasons.length > 0 ? (
        <ul className="mt-2 space-y-1 text-[11px] text-warning">
          {g.reasons.map((r, i) => <li key={i} className="border-l-2 border-l-warning pl-2">{r}</li>)}
        </ul>
      ) : null}
      <p className="mt-3 text-[11px] text-muted">
        Host telemetry (CPU, memory, latency, uptime), market-data feed health and
        cache statistics are not exposed by the current API.
      </p>
    </SectionCard>
  )
}
