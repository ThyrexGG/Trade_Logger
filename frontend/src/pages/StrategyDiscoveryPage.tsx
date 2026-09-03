import { useMemo, useState } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import {
  HashChip,
  MetricCard,
  ResearchSafetyBanner,
  ResearchStatusTag,
  ResearchUnavailable,
  SectionCard,
  SectionError,
  SkeletonRows,
  researchTone,
} from '../components/research/primitives'
import { useStrategyDiscovery } from '../lib/useStrategyDiscovery'
import type { LeaderboardRow } from '../types/strategyResearch'

const fmtR = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(3)}R`
const fmt = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? '—' : v.toFixed(d)

/**
 * Strategy Discovery (`/research/discovery`) — Phase 69/70.
 * Read-only view of the persistent historical data foundation, the machine-
 * readable strategy definitions, the offline-computed pair × strategy leaderboard,
 * and the recovered Gold baseline. Discovery compute is an operator CLI
 * (`python -m pair_ranking`); this page only renders the persisted artifact.
 */
export function StrategyDiscoveryPage() {
  const { coverage, strategies, ranking, gold, state, error, refetch } = useStrategyDiscovery()
  const [openStrategy, setOpenStrategy] = useState<string | null>(null)

  const leaderboard = ranking?.leaderboard ?? []
  const goldRows = useMemo(
    () => leaderboard.filter((r) => r.asset === 'XAUUSD'),
    [leaderboard],
  )

  return (
    <PageContainer
      title="Strategy Discovery"
      description="Which instrument + strategy combination has the most defensible statistical edge on real historical data — and where it does not. Research-only."
    >
      <ResearchSafetyBanner broker={ranking?.safety_barrier.live_broker_transmission ?? 'BLOCKED'} />

      {state === 'loading' && !ranking ? (
        <div className="mt-4">
          <SkeletonRows rows={6} />
        </div>
      ) : null}

      {state === 'error' && !ranking ? (
        <div className="mt-4">
          <SectionError message={error ?? 'Research surface unavailable.'} onRetry={refetch} />
        </div>
      ) : null}

      {/* ---- Verdict ---- */}
      <div className="mt-4">
        <SectionCard title="Research verdict">
          {ranking?.state === 'AVAILABLE' ? (
            <div className="space-y-2">
              <p className="font-mono text-sm text-primary">{ranking.verdict}</p>
              <p className="text-[11px] text-muted">
                Timeframe {ranking.timeframe ?? '1h'} · computed{' '}
                {new Date(ranking.generated_at).toLocaleString()} ·{' '}
                {ranking.deep ? 'deep (WFO/MC/sensitivity)' : 'quick (discovery only)'}
              </p>
            </div>
          ) : (
            <ResearchUnavailable>
              {ranking?.reason ??
                'No pair-ranking artifact computed yet. Run `python -m pair_ranking --timeframe 1h` (offline).'}
            </ResearchUnavailable>
          )}
        </SectionCard>
      </div>

      {/* ---- Leaderboard ---- */}
      <div className="mt-4">
        <SectionCard title={`Pair × strategy leaderboard${leaderboard.length ? ` (${leaderboard.length})` : ''}`}>
          {leaderboard.length ? (
            <div className="overflow-x-auto">
              <LeaderboardTable rows={leaderboard} />
              <p className="mt-2 text-[10px] text-muted">
                Sorted by <span className="font-mono">ResearchRankingScore</span> (RRS) — a
                decomposable candidate-sorting aid, <b>not</b> a trading signal. A candidate below
                the OOS sample floor is <span className="font-mono">INSUFFICIENT_EVIDENCE</span> and
                never ranked.
              </p>
            </div>
          ) : (
            <ResearchUnavailable>
              No ranked candidates. Either the artifact is not computed, or no
              instrument/strategy cleared the sample floor on the current data.
            </ResearchUnavailable>
          )}
        </SectionCard>
      </div>

      {/* ---- Gold detail ---- */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SectionCard title="XAUUSD — previous discovery (protected baseline)">
          {gold ? (
            <div className="space-y-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <ResearchStatusTag value={gold.edge_status} tone={researchTone(gold.edge_status)} />
                <HashChip value={gold.frozen_contract_hash} />
                <span className="text-[10px] text-muted">
                  {gold.contract_hash_matches_canonical ? 'contract hash matches canonical' : 'HASH MISMATCH'}
                </span>
              </div>
              <p className="text-secondary">{gold.previous_discovery.timeframe_stack}</p>
              <p className="text-[11px] text-muted">{gold.edge_status_reason}</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {gold.previous_discovery.metrics
                  .filter((m) => m.name.startsWith('holdout'))
                  .map((m) => (
                    <MetricCard
                      key={m.name}
                      label={m.name.replace('holdout_', '').replace(/_/g, ' ')}
                      value={m.value ?? '—'}
                      sub={`${m.unit}${m.reconstructable ? '' : ' · not reproducible here'}`}
                    />
                  ))}
              </div>
              <details className="rounded border border-border-subtle bg-surface-elevated/30 p-2">
                <summary className="cursor-pointer text-[11px] text-muted">
                  Explicitly unverifiable ({gold.previous_discovery.unverifiable.length})
                </summary>
                <ul className="mt-1 list-disc pl-4 text-[10px] text-muted">
                  {gold.previous_discovery.unverifiable.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              </details>
              <p className="text-[10px] text-muted">
                Data source: {gold.previous_discovery.data_source}
              </p>
            </div>
          ) : (
            <SkeletonRows rows={4} />
          )}
        </SectionCard>

        <SectionCard title="XAUUSD — current revalidation">
          {gold?.native_revalidation ? (
            <div className="mb-3 space-y-2 rounded border border-border-subtle bg-surface-elevated/30 p-2 text-xs">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                Native / near-native attempt (Phase 73)
              </p>
              <p className="text-[10px] text-warning">{gold.native_revalidation.native_verdict}</p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px] font-mono">
                  <thead className="text-muted">
                    <tr>
                      <th className="py-0.5 pr-2">TF</th>
                      <th className="py-0.5 pr-2">Role</th>
                      <th className="py-0.5 pr-2">State</th>
                      <th className="py-0.5 pr-2 text-right">Span d</th>
                      <th className="py-0.5 pr-2 text-right">OOS E[R]</th>
                      <th className="py-0.5 text-right">N</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gold.native_revalidation.per_timeframe.map((r) => (
                      <tr key={r.timeframe} className="border-t border-border-subtle/50">
                        <td className="py-0.5 pr-2">{r.timeframe}</td>
                        <td className="py-0.5 pr-2">
                          <span
                            className={
                              r.role === 'NATIVE'
                                ? 'text-info'
                                : r.role === 'NEAR_NATIVE'
                                  ? 'text-secondary'
                                  : 'text-muted'
                            }
                          >
                            {r.role}
                          </span>
                        </td>
                        <td className="py-0.5 pr-2">{r.state}</td>
                        <td className="py-0.5 pr-2 text-right">{r.stored_span_days ?? '—'}</td>
                        <td className="py-0.5 pr-2 text-right">
                          {r.oos_metrics?.expectancy_r ?? '—'}
                        </td>
                        <td className="py-0.5 text-right">{r.oos_metrics?.total_trades ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[9px] text-muted">{gold.native_revalidation.caveat}</p>
            </div>
          ) : null}
          {gold?.revalidated_metrics ? (
            <div className="space-y-3 text-xs">
              <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[10px] text-warning">
                {gold.revalidated_metrics.timeframe_substitution}
              </p>
              <p className="text-[11px] text-muted">{gold.wfo_status}</p>
              {gold.revalidated_metrics.comparison?.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[11px]">
                    <thead className="text-muted">
                      <tr>
                        <th className="py-1 pr-2">Metric</th>
                        <th className="py-1 pr-2 text-right">Old (1m holdout)</th>
                        <th className="py-1 pr-2 text-right">New (1h proxy)</th>
                        <th className="py-1">Interpretation</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {gold.revalidated_metrics.comparison.map((c) => (
                        <tr key={c.metric} className="border-t border-border-subtle/50">
                          <td className="py-1 pr-2">{c.metric}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{c.old ?? '—'}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{c.new ?? '—'}</td>
                          <td className="py-1 text-muted">{c.interpretation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ) : (
            <ResearchUnavailable>
              Not revalidated yet (Phase 71). {gold?.next_dependency}
            </ResearchUnavailable>
          )}
          {goldRows.length ? (
            <div className="mt-3">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-muted">
                Gold candidates in the current leaderboard
              </p>
              <LeaderboardTable rows={goldRows} compact />
            </div>
          ) : null}
        </SectionCard>
      </div>

      {/* ---- Strategy definitions ---- */}
      <div className="mt-4">
        <SectionCard title={`Strategy definitions${strategies ? ` (${strategies.strategies.length})` : ''}`}>
          {strategies ? (
            <div className="space-y-2">
              {strategies.strategies.map((sd) => {
                const open = openStrategy === sd.id
                const stab = ranking?.pair_stability?.[sd.id]
                return (
                  <div key={sd.id} className="rounded border border-border-subtle">
                    <button
                      type="button"
                      onClick={() => setOpenStrategy(open ? null : sd.id)}
                      className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
                    >
                      <span className="font-mono text-xs text-primary">{sd.id}</span>
                      <span className="flex items-center gap-2">
                        {stab ? (
                          <ResearchStatusTag
                            size="sm"
                            value={stab.class}
                            tone={stab.class.includes('NO_EDGE') ? 'negative' : 'info'}
                          />
                        ) : null}
                        <span className="text-[10px] text-muted">v{sd.version}</span>
                      </span>
                    </button>
                    {open ? (
                      <dl className="grid gap-x-4 gap-y-1 border-t border-border-subtle px-3 py-2 text-[11px] sm:grid-cols-2">
                        <Row k="Family" v={sd.family} />
                        <Row k="Scope" v={sd.instrument_scope} />
                        <Row k="Entry" v={sd.entry_conditions} />
                        <Row k="Exit" v={sd.exit_conditions} />
                        <Row k="Stop" v={sd.stop_model} />
                        <Row k="Target" v={sd.target_model} />
                        {sd.filters ? <Row k="Filters" v={sd.filters} /> : null}
                        {stab ? (
                          <Row
                            k="Pair stability"
                            v={`${stab.class} — positive on: ${
                              stab.positive_instruments.join(', ') || 'none'
                            }`}
                          />
                        ) : null}
                      </dl>
                    ) : null}
                  </div>
                )
              })}
            </div>
          ) : (
            <SkeletonRows rows={4} />
          )}
        </SectionCard>
      </div>

      {/* ---- Data foundation ---- */}
      <div className="mt-4">
        <SectionCard title="Historical data foundation (Phase 69)">
          {coverage ? (
            <div className="space-y-3 text-xs">
              <p className="text-[11px] text-muted">
                Real multi-year depth only for{' '}
                <span className="font-mono">{coverage.data_capable_timeframes.join(' / ')}</span>{' '}
                (yfinance limit). Intraday below 1h is{' '}
                <span className="font-mono">INSUFFICIENT_EVIDENCE</span> pending a provider.
              </p>
              {coverage.available.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[11px]">
                    <thead className="text-muted">
                      <tr>
                        <th className="py-1 pr-3">Asset</th>
                        <th className="py-1 pr-3">TF</th>
                        <th className="py-1 pr-3 text-right">Bars</th>
                        <th className="py-1 pr-3">From</th>
                        <th className="py-1">To</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {coverage.available.map((r) => (
                        <tr key={`${r.asset}-${r.timeframe}`} className="border-t border-border-subtle/50">
                          <td className="py-1 pr-3">{r.asset}</td>
                          <td className="py-1 pr-3">{r.timeframe}</td>
                          <td className="py-1 pr-3 text-right tabular-nums">{r.count.toLocaleString()}</td>
                          <td className="py-1 pr-3">{r.first_iso?.slice(0, 10) ?? '—'}</td>
                          <td className="py-1">{r.last_iso?.slice(0, 10) ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <ResearchUnavailable>
                  The candle store is empty. Populate it with{' '}
                  <span className="font-mono">python -m market_data_ingest --universe</span>.
                </ResearchUnavailable>
              )}
            </div>
          ) : (
            <SkeletonRows rows={4} />
          )}
        </SectionCard>
      </div>
    </PageContainer>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 text-muted">{k}</dt>
      <dd className="text-secondary">{v}</dd>
    </div>
  )
}

function LeaderboardTable({ rows, compact }: { rows: LeaderboardRow[]; compact?: boolean }) {
  return (
    <table className="w-full text-left text-[11px]">
      <thead className="text-muted">
        <tr>
          {!compact ? <th className="py-1 pr-2">#</th> : null}
          <th className="py-1 pr-2">Asset</th>
          <th className="py-1 pr-2">Strategy</th>
          <th className="py-1 pr-2 text-right">OOS E[R]</th>
          <th className="py-1 pr-2 text-right">PF</th>
          <th className="py-1 pr-2 text-right">WR%</th>
          <th className="py-1 pr-2 text-right">N</th>
          <th className="py-1 pr-2 text-right">RRS</th>
          <th className="py-1">Card</th>
        </tr>
      </thead>
      <tbody className="font-mono">
        {rows.map((r) => (
          <tr key={`${r.asset}-${r.strategy_id}`} className="border-t border-border-subtle/50">
            {!compact ? <td className="py-1 pr-2 tabular-nums">{r.rank}</td> : null}
            <td className="py-1 pr-2">{r.asset}</td>
            <td className="py-1 pr-2">{r.strategy_id}</td>
            <td
              className={`py-1 pr-2 text-right tabular-nums ${
                (r.oos_expectancy_r ?? 0) > 0 ? 'text-positive' : 'text-negative'
              }`}
            >
              {fmtR(r.oos_expectancy_r)}
            </td>
            <td className="py-1 pr-2 text-right tabular-nums">{fmt(r.oos_profit_factor)}</td>
            <td className="py-1 pr-2 text-right tabular-nums">{fmt(r.oos_win_rate_pct, 1)}</td>
            <td className="py-1 pr-2 text-right tabular-nums">{r.oos_trades ?? '—'}</td>
            <td className="py-1 pr-2 text-right tabular-nums">{fmt(r.research_ranking_score, 1)}</td>
            <td className="py-1">
              {r.scorecard ? (
                <ResearchStatusTag size="sm" value={r.scorecard} tone={researchTone(r.scorecard)} />
              ) : (
                '—'
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
