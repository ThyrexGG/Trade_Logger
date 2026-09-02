import type { StrategyLabResponse } from '../../types/research'
import { SectionCard } from './primitives'

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between border-b border-border-subtle/60 py-1.5 last:border-0">
      <span className="text-xs text-secondary">{label}</span>
      <span className="font-mono text-xs tabular-nums text-primary">{value}</span>
    </div>
  )
}

/** Registered strategies + the authoritative research / backtester defaults. */
export function StrategyConfiguration({ data }: { data: StrategyLabResponse }) {
  const rd = data.research_defaults
  const bd = data.backtest_defaults

  return (
    <div className="space-y-4">
      <SectionCard title="Registered strategies">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead className="border-b border-border text-muted">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium">Strategy</th>
                <th className="px-2 py-1.5 text-left font-medium">Version</th>
                <th className="px-2 py-1.5 text-left font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {data.strategies.map((s) => (
                <tr key={s.name} className="border-b border-border-subtle/60 align-top">
                  <td className="px-2 py-1.5 font-mono font-semibold text-primary">
                    {s.name}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-secondary">{s.version}</td>
                  <td className="px-2 py-1.5 text-secondary">{s.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Research specification defaults">
          <Row label="Train split" value={rd.train_split} />
          <Row label="Validation split" value={rd.val_split} />
          <Row label="Holdout split" value={rd.holdout_split} />
          <Row label="Structure timeframe" value={rd.struct_tf} />
          <Row label="Bias timeframe" value={rd.bias_tf} />
          <Row label="Spread (pips)" value={rd.spread_pips} />
          <Row label="Slippage (pips)" value={rd.slippage_pips} />
          <Row label="Commission (%)" value={rd.commission_pct} />
          <Row label="Random seed" value={rd.random_seed} />
          <p className="mt-2 text-[11px] text-muted">
            From <code>research_engine.ResearchExperiment</code> — the frozen
            3-layer (train / validation / holdout) research spec.
          </p>
        </SectionCard>

        <SectionCard title="Backtester defaults">
          <Row label="Default strategy" value={bd.strategy} />
          <Row label="Risk per trade (%)" value={bd.risk_pct} />
          <Row label="Stop-loss (ATR ×)" value={bd.sl_atr} />
          <Row label="Take-profit (ATR ×)" value={bd.tp_atr} />
          <Row label="Initial capital" value={`$${bd.capital.toLocaleString()}`} />
          <Row label="Slippage" value={bd.slippage} />
          <Row label="Commission (%)" value={bd.commission_pct} />
          <Row label="Fixed spread" value={bd.fixed_spread} />
          <Row label="Train split" value={bd.train_split} />
          <p className="mt-2 text-[11px] text-muted">
            Read from the <code>backtester.run_backtest</code> signature. The
            backtest workspace pre-fills a research split rather than the
            authoritative default of {bd.train_split}.
          </p>
        </SectionCard>
      </div>
    </div>
  )
}
