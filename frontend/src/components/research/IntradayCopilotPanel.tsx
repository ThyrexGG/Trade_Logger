import { useMemo } from 'react'
import { useIntradayCopilot } from '../../lib/useIntradayCopilot'
import type {
  CopilotBaseRate,
  CopilotScanInstrument,
  CopilotUniverseScan,
} from '../../types/intradayCopilot'
import {
  ResearchStatusTag,
  ResearchUnavailable,
  SectionCard,
  SkeletonRows,
  researchTone,
} from './primitives'

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`

function scanFor(scan: CopilotUniverseScan | undefined, asset: string): CopilotScanInstrument | undefined {
  return scan?.instruments.find((i) => i.instrument === asset)
}

function TimeframeScan({ label, snap }: { label: string; snap: CopilotScanInstrument | undefined }) {
  if (!snap) {
    return (
      <div className="rounded border border-border-subtle bg-surface-elevated/30 p-2 text-[11px] text-muted">
        {label}: no scan for this instrument.
      </div>
    )
  }
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 p-2">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[11px] text-muted">
        <span className="font-mono text-secondary">{label}</span>
        <span>close {snap.close}</span>
        <span>regime {snap.regime}</span>
        <span>session {snap.session}</span>
        <span>TR/ATR {snap.tr_atr.toFixed(2)}</span>
        <span>bar {new Date(snap.bar_time).toLocaleString()}</span>
      </div>
      {snap.active_conditions.length ? (
        <ul className="mt-1.5 flex flex-wrap gap-1">
          {snap.active_conditions.map((c) => (
            <li
              key={c}
              title={snap.active_condition_notes[c] ?? ''}
              className="rounded border border-info/30 bg-info/10 px-1.5 py-0.5 font-mono text-[10px] text-info"
            >
              {c.replace(/_/g, ' ')}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1.5 text-[11px] text-muted">No named structural condition on the latest bar.</p>
      )}
    </div>
  )
}

function BaseRateRow({ br }: { br: CopilotBaseRate }) {
  const horizons = Object.entries(br.by_horizon).sort(
    (a, b) => a[1].horizon_bars - b[1].horizon_bars,
  )
  return (
    <div className="rounded border border-border-subtle p-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="font-mono text-secondary">
          {br.conditions.map((c) => c.replace(/_/g, ' ')).join(' + ')}
        </span>
        <span className="text-muted">
          {br.timeframe} · N={br.n_occurrences.toLocaleString()}
        </span>
      </div>
      <div className="mt-1 overflow-x-auto">
        <table className="w-full text-left text-[11px] font-mono">
          <thead className="text-muted">
            <tr>
              <th className="py-0.5 pr-3">+bars</th>
              <th className="py-0.5 pr-3 text-right">up rate</th>
              <th className="py-0.5 pr-3 text-right">mean MFE</th>
              <th className="py-0.5 pr-3 text-right">mean MAE</th>
              <th className="py-0.5">verdict</th>
            </tr>
          </thead>
          <tbody>
            {horizons.map(([k, h]) => (
              <tr key={k} className="border-t border-border-subtle/50">
                <td className="py-0.5 pr-3">{h.horizon_bars}</td>
                <td className="py-0.5 pr-3 text-right tabular-nums">{pct(h.up_rate)}</td>
                <td className="py-0.5 pr-3 text-right tabular-nums">{h.mean_mfe_atr.toFixed(2)}R</td>
                <td className="py-0.5 pr-3 text-right tabular-nums">{h.mean_mae_atr.toFixed(2)}R</td>
                <td className="py-0.5">
                  <ResearchStatusTag size="sm" value={h.verdict} tone={researchTone(h.verdict)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * Phase 100 intraday setup co-pilot, scoped to one instrument. Shows the named
 * structural conditions on the latest 15m / 1h bar and, where sampled, their
 * multi-year forward-outcome base rates. This is decision support, not a
 * signal: Phases 70–93 found no systematic intraday directional edge, so the
 * co-pilot never emits a direction or a trade.
 */
export function IntradayCopilotPanel({ asset }: { asset: string }) {
  const { data, state, error } = useIntradayCopilot()

  const snap15 = useMemo(() => scanFor(data?.universe_scan_15m, asset), [data, asset])
  const snap1h = useMemo(() => scanFor(data?.universe_scan_1h, asset), [data, asset])
  const baseRates = useMemo(
    () =>
      Object.values(data?.sample_base_rates ?? {}).filter((b) => b.instrument === asset),
    [data, asset],
  )

  return (
    <SectionCard title="Intraday setup co-pilot — Phase 100">
      <p className="mb-3 rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
        Decision support only. Conditions are structural descriptions of the latest bar, not trade
        signals — Phases 70–93 found no systematic intraday directional edge, and every sampled base
        rate below is NEAR&nbsp;COIN&nbsp;FLIP. Nothing here recommends a direction or a trade.
      </p>

      {state === 'loading' ? (
        <SkeletonRows rows={4} />
      ) : state === 'error' ? (
        <ResearchUnavailable>
          Could not load the Phase 100 artifact ({error}). Run{' '}
          <span className="font-mono">python -m phase100_intraday_copilot</span>.
        </ResearchUnavailable>
      ) : data?.state !== 'AVAILABLE' ? (
        <ResearchUnavailable>
          {data?.reason ?? 'Not computed yet — run `python -m phase100_intraday_copilot`.'}
        </ResearchUnavailable>
      ) : (
        <div className="space-y-3">
          <div className="space-y-2">
            <TimeframeScan label="15m" snap={snap15} />
            <TimeframeScan label="1h" snap={snap1h} />
          </div>

          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wider text-muted">
              Forward-outcome base rates for {asset} (sampled)
            </p>
            {baseRates.length ? (
              <div className="space-y-2">
                {baseRates.map((br) => (
                  <BaseRateRow key={`${br.timeframe}-${br.conditions.join('+')}`} br={br} />
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-muted">
                No base rate sampled for {asset} in the current artifact. The CLI (
                <span className="font-mono">--base-rate {asset} 15m &lt;CONDITION&gt;</span>) computes
                any condition on demand.
              </p>
            )}
          </div>

          {data.skill_report_all ? (
            <p className="text-[10px] text-muted">
              Setup-skill tracker: {data.skill_report_all.state.replace(/_/g, ' ').toLowerCase()} (
              {data.skill_report_all.n_resolved} resolved){' '}
              {data.skill_report_all.note ? `— ${data.skill_report_all.note}` : null}
            </p>
          ) : null}

          <p className="text-[10px] text-muted">
            Scan bar {snap15 ? new Date(snap15.bar_time).toLocaleString() : '—'} · artifact generated{' '}
            {new Date(data.generated_at).toLocaleString()}
          </p>
        </div>
      )}
    </SectionCard>
  )
}
