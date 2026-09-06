import { useMemo } from 'react'
import { useIntradayCopilot } from '../../lib/useIntradayCopilot'
import type {
  CopilotBaseRate,
  CopilotScanInstrument,
  CopilotUniverseScan,
} from '../../types/intradayCopilot'
import { InfoTip, glossaryLookup } from '../common/InfoTip'
import {
  ResearchStatusTag,
  ResearchUnavailable,
  SectionCard,
  SkeletonRows,
  researchTone,
} from './primitives'

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`

const HEADER_INFO =
  "A lookup tool, not a signal. It names what the chart is doing right now on the 15-minute and 1-hour timeframes, then shows what happened next — historically — the thousands of other times the chart looked the same. Almost everything comes out a coin flip, and that is the point: it keeps you from seeing an edge that isn't there. Nothing here tells you to buy or sell."

// ---- plain-English mappings -------------------------------------------------
const REGIME_PLAIN: Record<string, string> = {
  TRENDING: 'trending',
  RANGING: 'ranging (sideways)',
  VOLATILE: 'volatile / choppy',
  QUIET: 'quiet',
}
const SESSION_PLAIN: Record<string, string> = {
  TOKYO: 'Tokyo session',
  LONDON: 'London session',
  NEW_YORK: 'New York session',
  LATE_US: 'late US (thin)',
  ASIA: 'Asia session',
  PRE_LONDON: 'pre-London',
}
const VERDICT_PLAIN: Record<string, string> = {
  NEAR_COIN_FLIP: 'coin flip — no edge',
  WEAK_SKEW: 'slight lean (weak — treat as a guess)',
  NOTABLE_SKEW: 'notable lean (hypothesis only)',
  LOW_CONFIDENCE: 'too few past cases to trust',
}

const conditionText = (c: string) => c.replace(/_/g, ' ').toLowerCase()

function ConditionChip({ code, note }: { code: string; note?: string }) {
  const text = conditionText(code)
  const explain = note || glossaryLookup(text) || glossaryLookup(code.replace(/_/g, ' '))
  return (
    <span className="inline-flex items-center rounded border border-info/30 bg-info/10 px-1.5 py-0.5 text-[10px] text-info">
      {text}
      {explain ? <InfoTip text={explain} /> : null}
    </span>
  )
}

function TimeframeScan({ label, snap }: { label: string; snap: CopilotScanInstrument | undefined }) {
  if (!snap) {
    return (
      <div className="rounded border border-border-subtle bg-surface-elevated/30 p-2.5 text-[11px] text-muted">
        {label} chart: no scan for this instrument in the latest run.
      </div>
    )
  }
  const regime = REGIME_PLAIN[snap.regime] ?? snap.regime.toLowerCase()
  const session = SESSION_PLAIN[snap.session] ?? snap.session.replace(/_/g, ' ').toLowerCase()
  const barSize =
    snap.tr_atr < 0.8 ? 'a quiet bar' : snap.tr_atr > 1.3 ? 'a big bar' : 'a normal-size bar'
  return (
    <div className="rounded border border-border-subtle bg-surface-elevated/30 p-2.5">
      <div className="flex items-center gap-2 text-xs">
        <span className="font-mono font-semibold text-secondary">{label} chart</span>
        <span className="text-muted">·</span>
        <span className="text-secondary">{session}</span>
      </div>
      <p className="mt-1 text-[11px] text-muted">
        Price <span className="font-mono text-secondary">{snap.close}</span> · {regime} ·{' '}
        {barSize} (
        <span title="latest bar range ÷ average bar range">
          {snap.tr_atr.toFixed(2)}× normal
        </span>
        ) · bar {new Date(snap.bar_time).toLocaleString()}
      </p>
      <div className="mt-2">
        <p className="mb-1 text-[10px] uppercase tracking-wide text-muted">
          What&apos;s on the chart now
        </p>
        {snap.active_conditions.length ? (
          <div className="flex flex-wrap gap-1">
            {snap.active_conditions.map((c) => (
              <ConditionChip key={c} code={c} note={snap.active_condition_notes[c]} />
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-muted">Nothing notable on the latest bar.</p>
        )}
      </div>
    </div>
  )
}

function BaseRateRow({ br }: { br: CopilotBaseRate }) {
  const horizons = Object.entries(br.by_horizon).sort(
    (a, b) => a[1].horizon_bars - b[1].horizon_bars,
  )
  const spanYears =
    br.history_span?.length === 2
      ? `${br.history_span[0].slice(0, 4)}–${br.history_span[1].slice(0, 4)}`
      : null
  // a representative horizon (the middle one) for the plain-English sentence
  const mid = horizons[Math.floor(horizons.length / 2)]?.[1]

  return (
    <div className="rounded border border-border-subtle p-2.5">
      <p className="text-[11px] text-secondary">
        When{' '}
        <span className="font-medium text-primary">
          {br.conditions.map(conditionText).join(' + ')}
        </span>{' '}
        happened on the {br.timeframe} chart
      </p>
      <p className="text-[10px] text-muted">
        {br.n_occurrences.toLocaleString()} times{spanYears ? ` · ${spanYears}` : ''} — this is the
        historical base rate, not a prediction
      </p>

      {mid ? (
        <p className="mt-1.5 rounded bg-surface-elevated/40 px-2 py-1 text-[11px] text-secondary">
          {mid.horizon_bars} bars later, price had closed higher{' '}
          <span className="font-mono">{pct(mid.up_rate)}</span> of the time
          {Math.abs(mid.up_rate - 0.5) < 0.04 ? ' — a coin flip.' : '.'} Best-case move averaged{' '}
          <span className="font-mono">{mid.mean_mfe_atr.toFixed(1)}R</span>, worst-case{' '}
          <span className="font-mono">{mid.mean_mae_atr.toFixed(1)}R</span>.
        </p>
      ) : null}

      <div className="mt-1.5 overflow-x-auto">
        <table className="w-full text-left text-[11px] font-mono">
          <thead className="text-muted">
            <tr>
              <th className="py-0.5 pr-3 font-medium">
                bars later
              </th>
              <th className="py-0.5 pr-3 text-right font-medium">
                <InfoTip text={glossaryLookup('up rate')!}>closed higher</InfoTip>
              </th>
              <th className="py-0.5 pr-3 text-right font-medium">
                <InfoTip text={glossaryLookup('mfe')!}>gain if right</InfoTip>
              </th>
              <th className="py-0.5 pr-3 text-right font-medium">
                <InfoTip text={glossaryLookup('mae')!}>loss if wrong</InfoTip>
              </th>
              <th className="py-0.5 font-medium">read</th>
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
                  <span title={VERDICT_PLAIN[h.verdict] ?? ''}>
                    <ResearchStatusTag size="sm" value={h.verdict} tone={researchTone(h.verdict)} />
                  </span>
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
    <SectionCard title="Intraday setup co-pilot — Phase 100" info={HEADER_INFO}>
      <p className="mb-3 rounded border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-[11px] leading-snug text-warning">
        <span className="font-semibold">Reference only — not a trade signal.</span> Below is what the
        chart looks like right now and what usually happened next in the past. Research on this system
        (Phases 70–93) found <span className="font-semibold">no reliable intraday direction edge</span>
        , and every base rate here is close to 50/50. Nothing here recommends buying or selling.
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
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-muted">
              1 · What {asset} is doing right now
            </p>
            <TimeframeScan label="15m" snap={snap15} />
            <TimeframeScan label="1h" snap={snap1h} />
          </div>

          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wider text-muted">
              2 · What usually happened next ({asset}, from history)
            </p>
            {baseRates.length ? (
              <div className="space-y-2">
                {baseRates.map((br) => (
                  <BaseRateRow key={`${br.timeframe}-${br.conditions.join('+')}`} br={br} />
                ))}
              </div>
            ) : (
              <p className="rounded border border-border-subtle p-2.5 text-[11px] text-muted">
                No base rate has been pre-computed for {asset} yet. The scan above still applies; a
                specific condition can be sampled on demand with{' '}
                <span className="font-mono">--base-rate {asset} 15m &lt;CONDITION&gt;</span>.
              </p>
            )}
          </div>

          <div className="rounded border border-border-subtle bg-surface-elevated/30 p-2.5 text-[10px] leading-relaxed text-muted">
            <span className="font-semibold text-secondary">How to read this — </span>
            <span className="font-mono">closed higher</span> = share of past cases where price was up
            after that many bars (50% = coin flip). <span className="font-mono">R</span> = one unit of
            the instrument&apos;s typical bar range (ATR), so moves compare across instruments.{' '}
            <span className="font-mono">gain if right / loss if wrong</span> are the average best- and
            worst-case moves before the horizon.{' '}
            <span className="font-mono">read</span>: coin flip = no edge · weak/notable lean =
            a hypothesis only (many conditions are scanned, so some look skewed by chance).
          </div>

          {data.skill_report_all ? (
            <p className="text-[10px] text-muted">
              <InfoTip text={glossaryLookup('setup-skill tracker')!}>
                <span className="uppercase tracking-wide">Setup-skill tracker</span>
              </InfoTip>
              : {data.skill_report_all.n_resolved} of your trades tagged &amp; resolved so far.{' '}
              {data.skill_report_all.note
                ? data.skill_report_all.note
                : 'Log ~30 real setups before it can compare your results to the base rate.'}
            </p>
          ) : null}

          <p className="text-[10px] text-muted">
            Chart snapshot {snap15 ? new Date(snap15.bar_time).toLocaleString() : '—'} · data
            refreshed {new Date(data.generated_at).toLocaleString()}
          </p>
        </div>
      )}
    </SectionCard>
  )
}

function scanFor(
  scan: CopilotUniverseScan | undefined,
  asset: string,
): CopilotScanInstrument | undefined {
  return scan?.instruments.find((i) => i.instrument === asset)
}
