import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { IntelligenceSummary, OpportunityMapItem, OpportunityMapResponse } from '../../types/intelligence'
import type { Section } from '../../lib/useIntelligence'
import { assetName, driverInPlainWords, factorAgreement, marketLean, marketMood, usdFromScore, type Tone } from '../../lib/plainEnglish'
import { Term } from '../common/InfoTip'
import { SectionCard, SectionError, SkeletonRows } from './primitives'

const TONE_TEXT: Record<Tone, string> = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  neutral: 'text-secondary',
}
const TONE_PILL: Record<Tone, string> = {
  positive: 'border-positive/40 bg-positive/10 text-positive',
  negative: 'border-negative/40 bg-negative/10 text-negative',
  warning: 'border-warning/40 bg-warning/10 text-warning',
  neutral: 'border-border bg-surface-elevated text-secondary',
}
const SHOW_FIRST = 8

function howSure(pct: number): string {
  if (pct >= 70) return 'fairly sure'
  if (pct >= 45) return 'somewhat sure'
  return 'not very sure'
}

function upDownSentence(s: IntelligenceSummary): string {
  const up = Math.round(s.breadth_bullish_pct)
  const down = Math.round(s.breadth_bearish_pct)
  const flat = Math.round(s.breadth_neutral_pct)
  if (flat >= 50) {
    const rest = up === down ? 'the rest are split evenly' : up > down ? `of the rest, more lean up (${up}%) than down (${down}%)` : `of the rest, more lean down (${down}%) than up (${up}%)`
    return `Most markets (${flat}%) have no clear direction right now — ${rest}.`
  }
  if (up >= 60) return `Most markets are leaning up (${up}% up, ${down}% down).`
  if (down >= 60) return `Most markets are leaning down (${down}% down, ${up}% up).`
  if (Math.abs(up - down) <= 10) return `Markets are split — about as many leaning up (${up}%) as down (${down}%).`
  return up > down ? `Slightly more markets lean up (${up}%) than down (${down}%).` : `Slightly more markets lean down (${down}%) than up (${up}%).`
}

function named(symbol: string): string {
  const n = assetName(symbol)
  return n ? `${n} (${symbol})` : symbol
}

/** The beginner's view of Market Intelligence: the mood in words, then each market's lean and why. */
export function MarketPlainView({
  summary,
  opportunity,
  onRetry,
}: {
  summary: Section<IntelligenceSummary>
  opportunity: Section<OpportunityMapResponse>
  onRetry: () => void
}) {
  const s = summary.data
  const opp = opportunity.data
  const [showAll, setShowAll] = useState(false)

  const ranked: OpportunityMapItem[] = (opp?.ranked_assets ?? [])
    .filter((a) => a.ranking_eligible)
    .sort((a, b) => Math.abs(b.edge_score) - Math.abs(a.edge_score))
  const visible = showAll ? ranked : ranked.slice(0, SHOW_FIRST)

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <SectionCard title="The big picture">
        {summary.state === 'loading' && !s ? (
          <SkeletonRows rows={4} />
        ) : summary.state === 'error' && !s ? (
          <SectionError message={summary.error} onRetry={onRetry} />
        ) : s ? (
          <BigPicture s={s} />
        ) : null}
      </SectionCard>

      <SectionCard title="Markets at a glance">
        {opportunity.state === 'loading' && !opp ? (
          <SkeletonRows rows={6} />
        ) : opportunity.state === 'error' && !opp ? (
          <SectionError message={opportunity.error} onRetry={onRetry} />
        ) : ranked.length === 0 ? (
          <p className="text-sm text-secondary">There isn&rsquo;t enough fresh data to rate any market right now.</p>
        ) : (
          <>
            <p className="mb-3 text-xs text-muted">
              Strongest leans first. The bar shows how strong the lean is. Tap a market for the full story.
            </p>
            <ul className="divide-y divide-border-subtle">
              {visible.map((a) => {
                const lean = marketLean(a.context_state)
                const agree = factorAgreement(a.conflict_state)
                const strength = Math.min(100, Math.abs(a.edge_score))
                const name = assetName(a.symbol)
                return (
                  <li key={a.symbol}>
                    <Link
                      to={`/research/intelligence/asset/${encodeURIComponent(a.symbol)}`}
                      className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-md px-1 py-2.5 transition-colors hover:bg-surface-hover"
                    >
                      <div className="w-full min-w-0 sm:w-56">
                        <div className="font-medium text-primary">{a.symbol}</div>
                        {name ? <div className="truncate text-xs text-muted">{name}</div> : null}
                      </div>
                      <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_PILL[lean.tone]}`}>{lean.label}</span>
                      <div className="flex min-w-[8rem] flex-1 items-center gap-2" title={`Strength ${strength.toFixed(0)} out of 100`}>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-elevated">
                          <div
                            className={`h-full rounded-full ${a.edge_score >= 0 ? 'bg-positive' : 'bg-negative'}`}
                            style={{ width: `${Math.max(4, strength)}%` }}
                          />
                        </div>
                        <span className="w-14 text-right text-[11px] text-muted">
                          {strength >= 50 ? 'strong' : strength >= 25 ? 'moderate' : 'weak'}
                        </span>
                      </div>
                      <p className="w-full text-xs text-secondary">
                        Mainly driven by {driverInPlainWords(a.dominant_driver)}.
                        {a.conflict_state.toUpperCase() !== 'ALIGNED' ? (
                          <span className={TONE_TEXT[agree.tone]}> {agree.label} — {agree.explain.toLowerCase()}</span>
                        ) : null}
                      </p>
                    </Link>
                  </li>
                )
              })}
            </ul>
            {ranked.length > SHOW_FIRST ? (
              <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-2 text-xs text-accent hover:underline">
                {showAll ? 'Show fewer' : `Show all ${ranked.length} markets`}
              </button>
            ) : null}
          </>
        )}
      </SectionCard>
    </div>
  )
}

function BigPicture({ s }: { s: IntelligenceSummary }) {
  const mood = marketMood(s.primary_regime)
  const second = s.secondary_regime && s.secondary_regime !== s.primary_regime ? marketMood(s.secondary_regime) : null
  const usd = usdFromScore(s.usd_strength_score)
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Market mood</p>
        <p className={`mt-1 text-lg font-semibold ${TONE_TEXT[mood.tone]}`}>{mood.label}</p>
        {mood.explain ? <p className="mt-1 leading-relaxed text-secondary">{mood.explain}</p> : null}
        {second ? (
          <p className="mt-1 text-secondary">
            {String(s.primary_regime).toUpperCase() === 'MIXED_REGIME' ? 'If anything, ' : 'Also, '}
            <span className="text-primary">{second.label.toLowerCase()}</span>.
          </p>
        ) : null}
        <p className="mt-1 text-xs text-muted">
          The model is {howSure(s.regime_confidence_pct)} about this ({s.regime_confidence_pct.toFixed(0)}%).
        </p>
      </div>

      <div className="border-t border-border-subtle pt-3">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Up or down?</p>
        <p className="mt-1 text-secondary">{upDownSentence(s)}</p>
      </div>

      <div className="border-t border-border-subtle pt-3">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">The US dollar</p>
        <p className="mt-1 text-secondary">
          The dollar looks <span className="font-medium text-primary">{usd.label}</span>. {usd.explain} Because so many pairs are priced in
          dollars, this moves a lot of markets at once.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-border-subtle pt-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Strongest right now</p>
          <Link to={`/research/intelligence/asset/${encodeURIComponent(s.strongest_asset)}`} className="mt-1 block font-medium text-positive hover:underline">
            {named(s.strongest_asset)}
          </Link>
        </div>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Weakest right now</p>
          <Link to={`/research/intelligence/asset/${encodeURIComponent(s.weakest_asset)}`} className="mt-1 block font-medium text-negative hover:underline">
            {named(s.weakest_asset)}
          </Link>
        </div>
      </div>

      {s.overall_data_quality < 70 ? (
        <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
          Some of the data behind this is missing or out of date, so take it with a pinch of salt.
        </p>
      ) : null}

      <p className="border-t border-border-subtle pt-3 text-xs text-muted">
        This is background to help you understand the market — it does not tell you when to buy or sell. See <Term label="risk-on" /> and{' '}
        <Term label="safe haven" /> for the basics.
      </p>
    </div>
  )
}
