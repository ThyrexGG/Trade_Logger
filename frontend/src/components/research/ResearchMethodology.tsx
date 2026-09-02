import type { StrategyLabResponse } from '../../types/research'
import { ResearchStatusTag, SectionCard } from './primitives'

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-0.5 text-xs text-primary">{value}</dd>
    </div>
  )
}

/** Backtest methodology + data-provenance panel — authoritative fields only. */
export function ResearchMethodology({ data }: { data: StrategyLabResponse }) {
  const m = data.methodology
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionCard
        title="Research methodology"
        action={
          <ResearchStatusTag
            value={m.lookahead_protection ? 'LOOKAHEAD PROTECTED' : 'LOOKAHEAD UNVERIFIED'}
            tone={m.lookahead_protection ? 'positive' : 'warning'}
            size="sm"
          />
        }
      >
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Item label="Execution model" value={m.execution_model} />
          <Item label="Split model" value={m.split_model} />
          <Item label="Slippage" value={m.slippage_model} />
          <Item label="Commission" value={m.commission_model} />
          <Item label="Spread" value={m.spread_model} />
          <Item label="Timezone" value={m.timezone} />
        </dl>
        <p className="mt-3 border-t border-border-subtle pt-2 text-[11px] text-muted">
          {m.lookahead_note}
        </p>
        {m.notes.length > 0 ? (
          <ul className="mt-2 space-y-1 text-[11px] text-muted">
            {m.notes.map((n, i) => (
              <li key={i} className="border-l-2 border-l-border pl-2">
                {n}
              </li>
            ))}
          </ul>
        ) : null}
      </SectionCard>

      <SectionCard title="Data provenance & quality">
        <dl className="space-y-2.5">
          <Item label="Data source" value={m.data_source} />
          <Item label="Timezone handling" value={m.timezone} />
          <Item
            label="Lookahead protection"
            value={m.lookahead_protection ? 'Enforced (next-bar open fill)' : 'Not verified'}
          />
        </dl>
        <p className="mt-3 border-t border-border-subtle pt-2 text-[11px] text-muted">
          Per-run data-quality metrics (coverage, missing bars, freshness,
          validation status) are not exposed by the current research API. The
          backtester fetches history live from the data source at run time.
        </p>
      </SectionCard>
    </div>
  )
}
