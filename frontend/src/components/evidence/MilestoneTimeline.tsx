import type { ForwardEvidenceState } from '../../types/evidence'
import { SectionCard } from './primitives'

/**
 * Sequential evidence milestone progression across the engine's 14 fixed
 * checkpoints. Reached / pending status and progress toward the next milestone
 * are the engine's own — this component never infers completion from N.
 */
export function MilestoneTimeline({ data }: { data: ForwardEvidenceState }) {
  const ms = data.milestones
  const roadmap = ms.milestone_roadmap

  return (
    <SectionCard
      title="Evidence milestones"
      action={
        <span className="font-mono text-[11px] text-muted">
          N = {ms.current_n} · next {ms.next_milestone}
        </span>
      }
    >
      <div className="mb-4">
        <div className="flex items-center justify-between text-[11px] text-muted">
          <span>Progress to milestone N = {ms.next_milestone}</span>
          <span className="font-mono tabular-nums">
            {ms.completion_pct_toward_next.toFixed(0)}% · {ms.trades_remaining} to go
          </span>
        </div>
        <div
          className="mt-1 h-2 w-full overflow-hidden rounded bg-surface-elevated"
          role="img"
          aria-label={`${ms.completion_pct_toward_next.toFixed(0)} percent toward milestone N equals ${ms.next_milestone}`}
        >
          <div
            className="h-full rounded bg-info/60"
            style={{ width: `${Math.max(0, Math.min(100, ms.completion_pct_toward_next))}%` }}
          />
        </div>
      </div>

      {roadmap.length === 0 ? (
        <p className="text-sm text-muted">No milestone roadmap returned.</p>
      ) : (
        <ol className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-4">
          {roadmap.map((mstone) => {
            const isNext = mstone.target_n === ms.next_milestone && !mstone.is_reached
            return (
              <li
                key={mstone.target_n}
                className={`flex items-center gap-2 rounded border px-2 py-1.5 text-xs ${
                  mstone.is_reached
                    ? 'border-positive/30 bg-positive/5'
                    : isNext
                      ? 'border-info/40 bg-info/5'
                      : 'border-border-subtle'
                }`}
              >
                <span
                  className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                    mstone.is_reached
                      ? 'bg-positive'
                      : isNext
                        ? 'bg-info'
                        : 'bg-border'
                  }`}
                  aria-hidden="true"
                />
                <span className="font-mono tabular-nums text-primary">
                  N = {mstone.target_n}
                </span>
                <span className="ml-auto text-[10px] uppercase tracking-wide text-muted">
                  {mstone.is_reached
                    ? 'reached'
                    : isNext
                      ? 'next'
                      : `+${mstone.trades_remaining}`}
                </span>
              </li>
            )
          })}
        </ol>
      )}
      <p className="mt-3 text-[11px] text-muted">
        Recorded milestone snapshots (cryptographic evidence records) exist in the
        governance store but are not exposed by the current evidence API.
      </p>
    </SectionCard>
  )
}
