import type { SafetyBarrier } from '../../types/evidence'

/**
 * Persistent reminder that forward evidence is research/validation context —
 * never an execution authorization. Values are the authoritative safety-barrier
 * fields from the engine.
 */
export function SafetyBanner({ safety }: { safety?: SafetyBarrier }) {
  const automationOff = safety ? safety.live_automation_enabled === false : true
  const broker = safety?.broker_transmission ?? 'BLOCKED'
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-blocked/30 bg-blocked/10 px-3 py-2 text-[11px]">
      <span className="font-mono font-semibold uppercase tracking-wider text-blocked">
        Research / Validation
      </span>
      <span className="text-secondary">
        Live automation {automationOff ? 'disabled' : 'ENABLED'}
      </span>
      <span className="text-secondary">·</span>
      <span className="text-secondary">Broker transmission {broker}</span>
      {safety?.status ? (
        <span className="ml-auto font-mono text-muted">{safety.status}</span>
      ) : null}
    </div>
  )
}
