import type {
  ResearchAuditResponse,
  ResearchDimensionRow,
} from '../../types/research'
import {
  MetricCard,
  ResearchStatusTag,
  ResearchUnavailable,
  SectionCard,
  Sparkline,
} from './primitives'

function r(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(3)}R`
}

function DimensionTable({ rows, groupLabel }: { rows: ResearchDimensionRow[]; groupLabel: string }) {
  if (rows.length === 0) {
    return <ResearchUnavailable>No rows — the strategy did not tag this dimension.</ResearchUnavailable>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[11px]">
        <thead className="border-b border-border text-muted">
          <tr>
            <th className="px-2 py-1 text-left font-medium">{groupLabel}</th>
            <th className="px-2 py-1 text-right font-medium">N</th>
            <th className="px-2 py-1 text-right font-medium">Win %</th>
            <th className="px-2 py-1 text-right font-medium">E[R]</th>
            <th className="px-2 py-1 text-right font-medium">PF</th>
            <th className="px-2 py-1 text-right font-medium">Max DD (R)</th>
            <th className="px-2 py-1 text-right font-medium">Cum R</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.group} className="border-b border-border-subtle/60">
              <td className="px-2 py-1 font-mono text-primary">{d.group}</td>
              <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{d.trades_n}</td>
              <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{d.win_rate_pct.toFixed(1)}</td>
              <td className={`px-2 py-1 text-right font-mono tabular-nums ${d.expectancy_r > 0 ? 'text-positive' : d.expectancy_r < 0 ? 'text-negative' : 'text-secondary'}`}>
                {r(d.expectancy_r)}
              </td>
              <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{d.profit_factor.toFixed(2)}</td>
              <td className="px-2 py-1 text-right font-mono tabular-nums text-negative">{d.max_drawdown_r.toFixed(2)}</td>
              <td className={`px-2 py-1 text-right font-mono tabular-nums ${d.cumulative_r >= 0 ? 'text-positive' : 'text-negative'}`}>{d.cumulative_r.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ResearchAuditView({ data }: { data: ResearchAuditResponse }) {
  if (data.status === 'failed') {
    return (
      <SectionCard title="Audit failed">
        <ResearchUnavailable>{data.error ?? 'The research engine reported a failure.'}</ResearchUnavailable>
      </SectionCard>
    )
  }

  const sc = data.scorecard
  const layer = data.layer_expectancy
  const boot = data.bootstrap_ci
  const stress = data.execution_stress
  const drift = data.expectancy_drift
  const conf = data.confluence

  return (
    <div className="space-y-4">
      {/* Scorecard */}
      <SectionCard
        title="Strategy edge scorecard"
        action={
          <span className="font-mono text-[11px] text-muted">
            {data.config.strategy} · {data.config.symbol} {data.config.timeframe} · N={data.sample_n} · {data.duration_sec}s
          </span>
        }
      >
        {sc ? (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <ResearchStatusTag value={sc.status} />
              <span className="text-[11px] text-muted">
                deployable: <span className={sc.is_deployable ? 'text-positive' : 'text-negative'}>{sc.is_deployable ? 'yes' : 'no'}</span>
              </span>
              {boot ? (
                <span className="text-[11px] text-muted">
                  95% bootstrap CI <span className="font-mono text-primary">{boot.ci_range_str}</span> · {boot.sample_confidence}
                </span>
              ) : null}
            </div>
            <ul className="mt-2 space-y-1 text-[11px] text-secondary">
              {sc.score_reasons.map((reason, i) => (
                <li key={i}>• {reason}</li>
              ))}
            </ul>
            <p className="mt-2 text-[10px] text-muted">
              <span className="text-secondary">Classification</span> is an interpretation by
              <code> research_engine.ScorecardClassifier</code>, not a fact — it combines the
              observed out-of-sample expectancy, the bootstrap CI, execution fragility and a
              (fixed) walk-forward assumption.
            </p>
          </>
        ) : (
          <ResearchUnavailable>Scorecard unavailable.</ResearchUnavailable>
        )}
      </SectionCard>

      {/* 3-layer expectancy + bootstrap */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Three-layer expectancy">
          {layer ? (
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Train (60%)" value={r(layer.train_r)} sub={`${layer.train_trades} trades`} />
              <MetricCard label="Validation (20%)" value={r(layer.validation_r)} sub={`${layer.validation_trades} OOS`} />
              <MetricCard label="Holdout (20%)" value={r(layer.holdout_r)} sub={`${layer.holdout_trades} untouched`} />
            </div>
          ) : (
            <ResearchUnavailable>Not enough trades to split.</ResearchUnavailable>
          )}
        </SectionCard>

        <SectionCard title="Bootstrap 95% CI (out-of-sample)">
          {boot ? (
            <div className="space-y-1 text-[11px]">
              <div className="flex justify-between"><span className="text-muted">Observed mean R</span><span className="font-mono text-primary">{r(boot.observed_mean_r)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Observed median R</span><span className="font-mono text-secondary">{r(boot.observed_median_r)}</span></div>
              <div className="flex justify-between"><span className="text-muted">95% CI</span><span className="font-mono text-primary">{boot.ci_range_str}</span></div>
              <div className="flex justify-between"><span className="text-muted">Sample</span><span className="font-mono text-secondary">{boot.sample_size} ({boot.sample_confidence})</span></div>
              <p className={`mt-1 rounded px-2 py-1 ${boot.ci_lower > 0 ? 'bg-positive/10 text-positive' : boot.ci_upper < 0 ? 'bg-negative/10 text-negative' : 'bg-warning/10 text-warning'}`}>
                {boot.verdict}
              </p>
            </div>
          ) : (
            <ResearchUnavailable>CI unavailable.</ResearchUnavailable>
          )}
        </SectionCard>
      </div>

      {/* Execution stress */}
      <SectionCard
        title="Execution-cost sensitivity"
        action={stress ? <span className="font-mono text-[11px] text-muted">fragility: {stress.fragility_rating}</span> : null}
      >
        {stress ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[11px]">
              <thead className="border-b border-border text-muted">
                <tr>
                  <th className="px-2 py-1 text-left font-medium">Scenario</th>
                  <th className="px-2 py-1 text-right font-medium">E[R]</th>
                  <th className="px-2 py-1 text-right font-medium">Edge retention</th>
                  <th className="px-2 py-1 text-right font-medium">Profitable</th>
                </tr>
              </thead>
              <tbody>
                {stress.scenarios.map((s) => (
                  <tr key={s.scenario} className="border-b border-border-subtle/60">
                    <td className="px-2 py-1 text-secondary">{s.scenario}</td>
                    <td className={`px-2 py-1 text-right font-mono tabular-nums ${s.expectancy_r > 0 ? 'text-positive' : 'text-negative'}`}>{r(s.expectancy_r)}</td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{s.edge_retention_pct.toFixed(1)}%</td>
                    <td className={`px-2 py-1 text-right font-mono ${s.is_profitable ? 'text-positive' : 'text-negative'}`}>{s.is_profitable ? 'yes' : 'no'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[10px] text-muted">
              Calculated by <code>research_analytics.stress_test_execution_sensitivity</code> —
              a canonical R-penalty model applied to the base expectancy, not a re-simulation of fills.
            </p>
          </div>
        ) : (
          <ResearchUnavailable>Stress test unavailable.</ResearchUnavailable>
        )}
      </SectionCard>

      {/* Drift */}
      <SectionCard
        title="Expectancy drift"
        action={drift ? <span className="font-mono text-[11px] text-muted">{drift.status}</span> : null}
      >
        {drift ? (
          <>
            <div className="grid grid-cols-4 gap-2">
              <MetricCard label="Historical" value={r(drift.historical_expectancy_r)} />
              <MetricCard label="Rolling 20" value={r(drift.rolling_20_r)} />
              <MetricCard label="Rolling 50" value={r(drift.rolling_50_r)} />
              <MetricCard label="Rolling 100" value={r(drift.rolling_100_r)} />
            </div>
            {drift.curve.length >= 2 ? (
              <div className="mt-3 text-primary">
                <Sparkline points={drift.curve.map((p) => ({ time: String(p.trade_index), equity: p.rolling_20_r }))} />
              </div>
            ) : null}
          </>
        ) : (
          <ResearchUnavailable>Drift monitor unavailable (need ≥10 trades).</ResearchUnavailable>
        )}
      </SectionCard>

      {/* Confluence */}
      {conf ? (
        <SectionCard title="Confluence calibration" action={<span className="font-mono text-[11px] text-muted">{conf.calibration_status}</span>}>
          <DimensionTable rows={conf.buckets} groupLabel="Confluence bucket" />
          {conf.quality_curve.length > 0 ? (
            <table className="mt-3 w-full border-collapse text-[11px]">
              <thead className="border-b border-border text-muted">
                <tr>
                  <th className="px-2 py-1 text-left font-medium">Min confluence</th>
                  <th className="px-2 py-1 text-right font-medium">N</th>
                  <th className="px-2 py-1 text-right font-medium">E[R]</th>
                  <th className="px-2 py-1 text-right font-medium">Win %</th>
                </tr>
              </thead>
              <tbody>
                {conf.quality_curve.map((q) => (
                  <tr key={q.min_confluence} className="border-b border-border-subtle/60">
                    <td className="px-2 py-1 font-mono text-primary">≥ {q.min_confluence}</td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{q.trades_n}</td>
                    <td className={`px-2 py-1 text-right font-mono tabular-nums ${q.expectancy_r > 0 ? 'text-positive' : 'text-negative'}`}>{r(q.expectancy_r)}</td>
                    <td className="px-2 py-1 text-right font-mono tabular-nums text-secondary">{q.win_rate_pct.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </SectionCard>
      ) : null}

      {/* Dimension breakdowns */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="By liquidity source"><DimensionTable rows={data.liquidity_breakdown} groupLabel="Liquidity" /></SectionCard>
        <SectionCard title="By session"><DimensionTable rows={data.session_breakdown} groupLabel="Session" /></SectionCard>
        <SectionCard title="Liquidity × session"><DimensionTable rows={data.liquidity_session_matrix} groupLabel="Combo" /></SectionCard>
        <SectionCard title="By market regime"><DimensionTable rows={data.regime_breakdown} groupLabel="Regime" /></SectionCard>
        <SectionCard title="By hour (UTC)"><DimensionTable rows={data.hourly_breakdown} groupLabel="Hour" /></SectionCard>
        <SectionCard title="By day of week"><DimensionTable rows={data.daily_breakdown} groupLabel="Day" /></SectionCard>
      </div>

      <SectionCard title="Method notes">
        <ul className="space-y-1 text-[11px] text-muted">
          {data.notes.map((n, i) => (
            <li key={i}>• {n}</li>
          ))}
          <li>• Contract hash <code className="text-secondary">{data.contract_hash.slice(0, 16)}…</code></li>
        </ul>
      </SectionCard>
    </div>
  )
}
