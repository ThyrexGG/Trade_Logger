import { PageContainer } from '../components/shell/PageContainer'
import {
  MetricCard,
  ResearchSafetyBanner,
  ResearchUnavailable,
  SectionCard,
  SectionError,
  SkeletonRows,
} from '../components/research/primitives'
import { SentimentBadge } from '../components/common/Sentiment'
import { InfoTip } from '../components/common/InfoTip'
import { useCryptoCarry } from '../lib/useCryptoCarry'

const VERDICT_PLAIN: Record<string, string> = {
  FORWARD_EVIDENCE_INSUFFICIENT: 'Too early to judge — keep accumulating weeks.',
  FORWARD_EVIDENCE_TRACKING: 'Live returns are tracking the backtest.',
  FORWARD_EVIDENCE_CONFIRMING: 'Live returns confirm the backtest — edge holding up.',
  FORWARD_EVIDENCE_DIVERGING: 'Live returns are diverging from the backtest — reassess.',
  USABLE_EDGE_FOUND: 'Yes — a small, survivable positive-expectancy allocation.',
}

const pct = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(d)}%`
const spct = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(d)}%`
const num = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? '—' : v.toFixed(d)

/**
 * Crypto Carry (`/research/crypto-carry`). The one usable edge from the swing
 * research programme: delta-neutral crypto perpetual funding carry. Shows the
 * recommended book and sizing (Phase 97), and — the point of the page — the
 * weekly forward-evidence tracker (Phase 98): is the live-forward return
 * tracking the backtest, or diverging from it? Research-only, no execution.
 */
export function CryptoCarryPage() {
  const { forward, book, edge, state, error, refetch } = useCryptoCarry()

  const rb = book?.recommended_book
  const led = forward?.ledger
  const gates = forward?.design_note?.verdict_gates
  const anchor = led?.go_live_anchor ?? forward?.design_note?.go_live_anchor
  const weeksForward = led?.forward_evidence.n_weeks ?? 0
  const assessAt = gates?.insufficient_below_weeks ?? 12
  const confirmAt = gates?.confirm_at_weeks ?? 26

  return (
    <PageContainer
      title="Crypto Carry"
      description="Delta-neutral crypto perpetual funding carry — the one usable edge from the swing research programme. Recommended book, sizing, and the weekly forward-evidence tracker. Research-only — no execution, no orders."
    >
      <ResearchSafetyBanner broker={forward?.safety_barrier.live_broker_transmission ?? 'BLOCKED'} />

      {state === 'loading' && !forward ? (
        <div className="mt-4"><SkeletonRows rows={6} /></div>
      ) : state === 'error' && !forward ? (
        <div className="mt-4"><SectionError message={error ?? 'Unavailable.'} onRetry={refetch} /></div>
      ) : null}

      {/* ---- Usability verdict (Phase 97) ---- */}
      {book ? (
        <div className="mt-4">
          <SectionCard
            title="Verdict — is this a usable edge?"
            info="The bottom line from the research: is delta-neutral crypto funding carry worth allocating to, and how much? This is the one strategy out of ~100 phases that came back as actually usable — modest (~2%/yr over cash), uncorrelated, and survivable."
          >
            {book.state === 'AVAILABLE' && book.usability_verdict ? (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <SentimentBadge value={book.usability_verdict} size="md" hint="up" />
                  <span className="text-xs text-secondary">
                    {VERDICT_PLAIN[book.usability_verdict] ?? ''}
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-secondary">{book.usability_reason}</p>
              </div>
            ) : (
              <ResearchUnavailable>
                {book.reason ?? 'Run `python -m phase97_portfolio_construction`.'}
              </ResearchUnavailable>
            )}
          </SectionCard>
        </div>
      ) : null}

      {/* ---- Recommended book (Phase 97) ---- */}
      {rb ? (
        <div className="mt-4">
          <SectionCard
            title="Recommended book"
            info="How to split capital: put ~25% into the delta-neutral carry (spread across at least 2 exchanges so one failing can't sink you), leave 75% in cash. The metrics are the historical performance of that blend before the tail-risk haircut."
          >
            <div className="mb-3">
              <div className="flex items-baseline justify-between text-[11px]">
                <span className="font-mono text-positive">Funding carry {pct(rb.allocation.funding_carry, 0)}</span>
                <span className="font-mono text-secondary">Cash {pct(rb.allocation.cash, 0)}</span>
              </div>
              <div className="mt-1 flex h-2.5 overflow-hidden rounded bg-surface-elevated/40">
                <div className="bg-positive/60" style={{ width: `${rb.allocation.funding_carry * 100}%` }} />
                <div className="bg-info/40" style={{ width: `${rb.allocation.cash * 100}%` }} />
              </div>
              <p className="mt-1 text-[10px] text-muted">
                Carry sleeve spread across ≥2 exchange venues · cash earns an assumed{' '}
                {pct(rb.cash_rate_assumed, 1)}/yr
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Historical CAGR" value={pct(rb.historical_metrics_no_tail.cagr)} tone="positive" />
              <MetricCard
                label={<InfoTip text="Annual return above what the cash sits at — the actual enhancement the carry sleeve buys you.">Excess over cash</InfoTip>}
                value={spct(rb.historical_metrics_no_tail.excess_cagr_over_cash)}
                tone="positive"
              />
              <MetricCard
                label={<InfoTip text="Largest peak-to-trough drop in the blended book over the backtest.">Max drawdown</InfoTip>}
                value={pct(rb.historical_metrics_no_tail.max_drawdown)}
              />
              <MetricCard
                label={<InfoTip text="Return above cash ÷ volatility. Higher = smoother path. This is before the tail-risk haircut, so treat it as an upper bound.">Sharpe (no tail)</InfoTip>}
                value={num(rb.historical_metrics_no_tail.sharpe)}
                sub="pre tail-risk haircut"
              />
            </div>
            {book?.fx_carry_status ? (
              <p className="mt-2 text-[10px] text-muted">FX carry sleeve: {book.fx_carry_status}</p>
            ) : null}
          </SectionCard>
        </div>
      ) : null}

      {/* ---- Forward evidence tracker (Phase 98) ---- */}
      <div className="mt-4">
        <SectionCard
          title="Forward evidence tracker"
          info="Since the go-live date, is the strategy actually delivering what the backtest promised? Each week you run the refresh, this compares real forward returns against the backtest reference. It needs 12 weeks before a call and 26 to confirm. The backtest is survivorship-biased, so this is the real test."
          action={forward?.verdict ? <SentimentBadge value={forward.verdict} hint="caution" /> : null}
        >
          {forward?.state === 'AVAILABLE' && led ? (
            <div className="space-y-3">
              {forward.verdict ? (
                <p className="text-sm font-medium text-primary">
                  {VERDICT_PLAIN[forward.verdict] ?? forward.verdict.replace(/_/g, ' ')}
                </p>
              ) : null}
              <p className="text-xs text-secondary">{forward.verdict_reason}</p>

              {/* progress toward assessment / confirmation */}
              <div>
                <div className="flex justify-between text-[10px] text-muted">
                  <span>go-live {anchor}</span>
                  <span>
                    week {weeksForward} · assess at {assessAt} · confirm at {confirmAt}
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded bg-surface-elevated/40">
                  <div
                    className="h-2 bg-accent/50"
                    style={{ width: `${Math.min(100, (weeksForward / confirmAt) * 100)}%` }}
                  />
                </div>
              </div>

              {/* backtest vs forward */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead className="text-muted">
                    <tr>
                      <th className="py-1 pr-3" />
                      <th className="py-1 pr-3 text-right">Backtest reference</th>
                      <th className="py-1 text-right">Forward (live)</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    <CmpRow label="Weeks" b={led.backtest_reference.n_weeks} f={led.forward_evidence.n_weeks} fmt={(v) => String(v)} />
                    <CmpRow label="Ann. funding" b={led.backtest_reference.ann_funding} f={led.forward_evidence.ann_funding} fmt={(v) => pct(v)} />
                    <CmpRow label="Ann. return (net)" b={led.backtest_reference.ann_return} f={led.forward_evidence.ann_return} fmt={(v) => pct(v)} />
                    <CmpRow label="Sharpe" b={led.backtest_reference.sharpe} f={led.forward_evidence.sharpe} fmt={(v) => num(v)} />
                    <CmpRow label="Positive weeks" b={led.backtest_reference.positive_weeks_pct} f={led.forward_evidence.positive_weeks_pct} fmt={(v) => pct(v, 0)} />
                    <CmpRow label="Cumulative" b={led.backtest_reference.cumulative_return} f={led.forward_evidence.cumulative_return} fmt={(v) => spct(v, 2)} />
                  </tbody>
                </table>
              </div>

              {gates ? (
                <div className="grid gap-2 text-[10px] sm:grid-cols-2">
                  <p className="rounded border border-positive/30 bg-positive/10 px-2 py-1 text-positive">
                    TRACKING needs: {gates.tracking_needs}
                  </p>
                  <p className="rounded border border-negative/30 bg-negative/10 px-2 py-1 text-negative">
                    DIVERGING if: {gates.diverging_if}
                  </p>
                </div>
              ) : null}

              {forward.snapshot_history?.length ? (
                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-wider text-muted">
                    Weekly snapshots ({forward.snapshot_history.length})
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[11px] font-mono">
                      <thead className="text-muted">
                        <tr>
                          <th className="py-1 pr-3">Captured</th>
                          <th className="py-1 pr-3 text-right">Fwd weeks</th>
                          <th className="py-1">Verdict</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...forward.snapshot_history].reverse().map((s) => (
                          <tr key={s.snapshot_key} className="border-t border-border-subtle/50">
                            <td className="py-1 pr-3">{new Date(s.captured_at).toLocaleDateString()}</td>
                            <td className="py-1 pr-3 text-right tabular-nums">{s.forward_weeks}</td>
                            <td className="py-1">
                              <SentimentBadge value={s.verdict} hint="caution" />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              <p className="rounded border border-border-subtle bg-surface-elevated/30 px-2 py-1.5 text-[10px] text-muted">
                Accumulate evidence: run{' '}
                <span className="font-mono text-secondary">python -m phase98_carry_forward_evidence --refresh</span>{' '}
                once a week (or leave the <span className="font-mono">TradeLogger Phase98</span> scheduled
                task on). Data through {led.data_through}.
              </p>
            </div>
          ) : (
            <ResearchUnavailable>
              {forward?.reason ?? 'Run `python -m phase98_carry_forward_evidence --refresh`.'}
            </ResearchUnavailable>
          )}
        </SectionCard>
      </div>

      {/* ---- Edge test (Phase 96) — secondary ---- */}
      {edge?.state === 'AVAILABLE' ? (
        <div className="mt-4">
          <SectionCard
            title="Edge test (Phase 96)"
            info="The original backtest that established the edge: net Sharpe across a cost ladder, how it holds up under adverse assumptions, whether funding stays positive per coin, the BTC beta (delta-neutrality check), and whether it beats a random-entry placebo. BASE = normal costs, ADVERSE = doubled."
          >
            <details>
              <summary className="cursor-pointer text-[11px] text-muted">
                {edge.edge_verdict} — how the backtested edge was judged
              </summary>
              <div className="mt-3 space-y-3">
                <p className="text-[11px] leading-relaxed text-secondary">{edge.edge_reason}</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <MetricCard label={<InfoTip text="Return above cash ÷ volatility, with normal trading costs. >2 is very good.">Sharpe (BASE)</InfoTip>} value={num(edge.headline_base?.sharpe)} />
                  <MetricCard label={<InfoTip text="Same Sharpe but with trading costs doubled — a stress test.">Sharpe (ADVERSE)</InfoTip>} value={num(edge.headline_adverse?.sharpe)} />
                  <MetricCard label={<InfoTip text="Compound annual growth of the carry sleeve alone, normal costs.">CAGR (BASE)</InfoTip>} value={pct(edge.headline_base?.cagr)} />
                  <MetricCard label={<InfoTip text="Deepest peak-to-trough drop of the carry sleeve, normal costs.">Max DD (BASE)</InfoTip>} value={pct(edge.headline_base?.max_drawdown)} />
                  <MetricCard
                    label={<InfoTip text="How reliably each coin's funding stays positive month to month. Higher = the carry is repeatable, not a fluke.">Funding persistence</InfoTip>}
                    value={num(edge.controls?.funding_persistence?.pooled_corr)}
                    sub={`${edge.controls?.funding_persistence?.n_coin_positive ?? '—'}/27 coins positive`}
                  />
                  <MetricCard
                    label={<InfoTip text="How much the book moves for a 1% Bitcoin move. Near zero = genuinely delta-neutral; price direction doesn't matter.">BTC beta</InfoTip>}
                    value={num(edge.controls?.delta_neutrality_check?.btc?.beta, 3)}
                    sub="delta-neutrality check"
                  />
                  <MetricCard
                    label={<InfoTip text="Where the real strategy's Sharpe sits vs 300 random-entry placebos. 100% = it beat every placebo; p is the chance the edge is luck.">Placebo percentile</InfoTip>}
                    value={pct(edge.controls?.random_eligibility_placebo?.real_percentile, 0)}
                    sub={`p=${num(edge.controls?.random_eligibility_placebo?.empirical_p_one_sided, 3)}`}
                  />
                  <MetricCard
                    label={<InfoTip text="How many calendar years the sleeve finished green out of the years tested.">Positive years</InfoTip>}
                    value={`${edge.headline_base?.positive_years ?? '—'}/${edge.headline_base?.n_years ?? '—'}`}
                  />
                </div>
                {edge.headline_base?.per_year_return ? (
                  <div className="overflow-x-auto">
                    <table className="text-[11px] font-mono">
                      <tbody>
                        <tr className="text-muted">
                          {Object.keys(edge.headline_base.per_year_return).map((y) => (
                            <td key={y} className="px-2 py-0.5 text-right">{y}</td>
                          ))}
                        </tr>
                        <tr>
                          {Object.values(edge.headline_base.per_year_return).map((v, i) => (
                            <td
                              key={i}
                              className={`px-2 py-0.5 text-right tabular-nums ${
                                v > 0 ? 'text-positive' : v < 0 ? 'text-negative' : 'text-muted'
                              }`}
                            >
                              {spct(v, 0)}
                            </td>
                          ))}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <p className="text-[10px] text-muted">
                  Phase 96's carry backtest is survivorship-biased (today's 27-coin universe applied
                  backward) — the real edge is a little thinner and the real tail a little fatter than
                  shown. That is exactly what the forward tracker above is for.
                </p>
              </div>
            </details>
          </SectionCard>
        </div>
      ) : null}
    </PageContainer>
  )
}

const CMP_TIP: Record<string, string> = {
  'Weeks': 'How many weeks of data each column covers. The forward column grows by one each weekly refresh.',
  'Ann. funding': 'Annualised funding yield collected — the raw engine of the carry, before costs and basis.',
  'Ann. return (net)': 'Annualised return after costs and basis drag. This is what actually lands in the account.',
  'Sharpe': 'Return above cash ÷ volatility. If the forward Sharpe is well below the backtest, the edge is decaying.',
  'Positive weeks': 'Share of weeks that closed green. Carry should be positive most weeks.',
  'Cumulative': 'Total compounded return of the sleeve since the start of each window.',
}

function CmpRow({
  label,
  b,
  f,
  fmt,
}: {
  label: string
  b: number | null
  f: number | null
  fmt: (v: number) => string
}) {
  const tip = CMP_TIP[label]
  return (
    <tr className="border-t border-border-subtle/50">
      <td className="py-1 pr-3 font-sans text-muted">
        {tip ? <InfoTip text={tip}>{label}</InfoTip> : label}
      </td>
      <td className="py-1 pr-3 text-right tabular-nums text-secondary">{b === null ? '—' : fmt(b)}</td>
      <td className="py-1 text-right tabular-nums text-primary">{f === null ? '—' : fmt(f)}</td>
    </tr>
  )
}
