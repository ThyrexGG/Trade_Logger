import { Link } from 'react-router-dom'
import { useHealth } from '../lib/health'
import { useOpenPositions } from '../lib/useOpenPositions'
import { useAudit, useJournal, useSystemOps } from '../lib/useOperations'
import { PageContainer } from '../components/shell/PageContainer'
import {
  OpsMetric,
  OpsSafetyBanner,
  OpsStatusTag,
  SectionCard,
  opsTone,
} from '../components/operations/primitives'
import { formatUsd, timeAgo } from '../lib/format'

function money(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v).replace('$', '')}`
}

/**
 * `/operations` overview. Every card is backed by a real endpoint — system
 * health, safety-gate status, open-position count, latest journal trade and
 * latest audit event. Nothing is fabricated; a section with no data says so.
 */
export function OperationsOverviewPage() {
  const health = useHealth()
  const system = useSystemOps()
  const positions = useOpenPositions()
  const journal = useJournal()
  const audit = useAudit()

  const latestTrade = journal.data?.entries[0] ?? null
  const latestEvent = audit.data?.events[0] ?? null
  const gate = system.data?.safety_gate

  return (
    <PageContainer
      title="Operations"
      description="Operational overview — positions, journal, audit and system health. Read-only."
    >
      <div className="space-y-4">
        <OpsSafetyBanner
          broker={health.data?.live_broker_transmission}
          automationDisabled={health.data ? health.data.automation_enabled === false : true}
        />

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <OpsMetric
            label="API"
            value={
              <OpsStatusTag
                value={health.state === 'connected' ? 'HEALTHY' : health.state === 'loading' ? 'CHECKING' : 'UNREACHABLE'}
                tone={health.state === 'connected' ? 'positive' : health.state === 'loading' ? 'warning' : 'negative'}
                size="sm"
              />
            }
          />
          <OpsMetric
            label="Safety gate"
            value={gate ? <OpsStatusTag value={gate.overall_status} tone={opsTone(gate.overall_status)} size="sm" /> : '—'}
          />
          <OpsMetric label="Open positions" value={positions.data?.total_open ?? (positions.state === 'loading' ? '…' : '—')} />
          <OpsMetric
            label="Automation"
            value={<OpsStatusTag value="DISABLED" tone="positive" size="sm" />}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard title="System" action={<Link to="/operations/system" className="text-[11px] text-secondary hover:text-primary">Open →</Link>}>
            {system.data ? (
              <dl className="space-y-1.5 text-xs">
                <div className="flex justify-between"><dt className="text-muted">Service</dt><dd className="font-mono text-primary">{system.data.app_name} v{system.data.version}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Kill switch</dt><dd className="font-mono text-primary">{gate?.kill_switch_engaged ? 'ENGAGED' : 'not engaged'}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Database</dt><dd className="font-mono text-primary">{gate?.database_connected ? 'connected' : 'unreachable'}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Broker transmission</dt><dd className="font-mono text-negative">{system.data.live_broker_transmission}</dd></div>
              </dl>
            ) : (
              <p className="text-xs text-muted">Loading system status…</p>
            )}
          </SectionCard>

          <SectionCard title="Latest journal trade" action={<Link to="/operations/journal" className="text-[11px] text-secondary hover:text-primary">Open →</Link>}>
            {journal.state === 'loading' && !journal.data ? (
              <p className="text-xs text-muted">Loading…</p>
            ) : latestTrade ? (
              <div className="text-xs">
                <p className="font-mono font-semibold text-primary">{latestTrade.symbol} · {latestTrade.direction}</p>
                <p className={`mt-1 font-mono ${latestTrade.net_profit >= 0 ? 'text-positive' : 'text-negative'}`}>{money(latestTrade.net_profit)}</p>
                <p className="mt-1 text-muted">{timeAgo(latestTrade.exit_time) ?? latestTrade.exit_time.slice(0, 10)} · {journal.data?.total_trades} closed trades</p>
              </div>
            ) : (
              <p className="text-xs text-muted">No journal entries.</p>
            )}
          </SectionCard>

          <SectionCard title="Latest audit event" action={<Link to="/operations/audit" className="text-[11px] text-secondary hover:text-primary">Open →</Link>}>
            {audit.state === 'loading' && !audit.data ? (
              <p className="text-xs text-muted">Loading…</p>
            ) : latestEvent ? (
              <div className="text-xs">
                <p className="font-mono font-semibold text-primary">{latestEvent.symbol ?? '—'} · {latestEvent.side ?? '—'}</p>
                <p className="mt-1 flex gap-1.5">
                  <OpsStatusTag value={latestEvent.mode ?? '—'} size="sm" />
                  <OpsStatusTag value={latestEvent.state ?? '—'} size="sm" />
                </p>
                <p className="mt-1 text-muted">{timeAgo(latestEvent.created_at ?? undefined) ?? '—'} · {audit.data?.total_records.toLocaleString()} records</p>
              </div>
            ) : (
              <p className="text-xs text-muted">No audit events.</p>
            )}
          </SectionCard>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border-subtle pt-3 text-[11px] text-muted">
          <span>Operational data — separate from historical research and forward evidence.</span>
          <Link to="/workspace/positions" className="text-secondary hover:text-primary">Positions →</Link>
          <Link to="/evidence" className="text-secondary hover:text-primary">Forward Evidence →</Link>
          <Link to="/research/intelligence" className="text-secondary hover:text-primary">Market Intelligence →</Link>
        </div>
      </div>
    </PageContainer>
  )
}
