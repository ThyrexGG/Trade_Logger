import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * Plain-English explanations for the jargon that shows up around the app.
 * Keys are matched case-insensitively; `<Term>` looks a label up here.
 */
export const GLOSSARY: Record<string, string> = {
  // --- performance / trade stats ---
  sqn: "System Quality Number — expectancy ÷ standard deviation of trade results, ×√N. Van Tharp's scale: <1 hard to trade, 1.6–2 good, 2.5+ excellent, 3+ superb.",
  expectancy: 'Average profit (or loss) per trade, in account currency. Positive = the strategy makes money on average.',
  'expectancy r': 'Average profit per trade measured in R — multiples of the amount risked. +0.3R means each trade nets 0.3× the risk on average.',
  'e[r]': 'Expected value in R — average profit per trade as a multiple of the amount risked.',
  'oos e[r]': 'Out-of-sample expected R — average profit per trade (in risk multiples) on data the strategy was not fitted on.',
  r: 'One R = the amount risked on a trade (entry to stop). Results in "R" are risk-normalised so trades of different size compare directly.',
  'r-multiple': 'A trade result divided by the amount risked. +2R = made twice what was risked; −1R = hit the stop.',
  'r:r': 'Reward-to-risk ratio — the take-profit distance divided by the stop distance. 2:1 means the target is twice as far as the stop.',
  'profit factor': 'Gross profit ÷ gross loss. Above 1 is profitable; 1.5+ is solid; below 1 loses money.',
  pf: 'Profit factor — gross profit ÷ gross loss. >1 profitable, 1.5+ solid.',
  'win rate': 'Share of trades that closed in profit. A low win rate can still be profitable if winners are much bigger than losers.',
  'win / loss ratio': 'Average winning trade ÷ average losing trade. 2.0 means winners are twice the size of losers.',
  drawdown: 'The largest drop from an equity peak to a later trough. Measures the worst losing stretch you would have sat through.',
  'max drawdown': 'The largest peak-to-trough equity decline over the period — the deepest hole the account went into.',
  'gain %': 'Return over the period as a percentage of the starting balance.',
  'period returns': 'Return over rolling windows (day / week / month / annualised), relative to now.',
  cagr: 'Compound annual growth rate — the smoothed yearly return that would take you from start to end value.',
  'excess over cash': 'Annual return above whatever the idle cash earns — the actual enhancement the strategy buys.',
  // --- statistics / research rigour ---
  'wilson ci': 'Wilson score confidence interval — a robust range for the true win rate given a small sample. Wide interval = not enough trades to be sure.',
  'bootstrap ci': 'A confidence range built by resampling the actual trades thousands of times. If the lower bound is above zero, the edge is unlikely to be luck.',
  'ci lower': 'Lower bound of the confidence interval. If it stays above zero the edge is unlikely to be chance.',
  oos: 'Out-of-sample — data the strategy was NOT fitted on. Out-of-sample results are the honest test of an edge.',
  wfo: 'Walk-forward optimisation — repeatedly fit on a window, test on the next unseen window, roll forward. Guards against curve-fitting.',
  'wfo stability': 'How consistent the strategy stays across walk-forward windows. Low stability = the edge only worked in some periods.',
  'monte carlo': 'Thousands of simulated alternative histories (reshuffled trades / random paths) to see the range of outcomes, not just the one that happened.',
  holdout: 'A slice of data sealed away and never looked at during research, kept for one final unbiased check.',
  placebo: 'A deliberately meaningless version of the strategy (random entries / shuffled signals). If the real one barely beats the placebo, the "edge" is noise.',
  'n (sample)': 'Number of trades / observations. More is better — small samples make any metric unreliable.',
  rrs: 'Research Ranking Score — a decomposable sorting aid for candidate strategies. NOT a trading signal; just orders the leaderboard.',
  'sample floor': 'The minimum number of trades a candidate needs before it is ranked at all. Below it, results are "insufficient evidence".',
  // --- crypto carry ---
  'f*': 'The recommended fraction of capital to allocate — here, the largest size where a single venue failing still costs ≤12% of the whole book.',
  'delta-neutral': 'Long and short offsetting positions so the book barely moves with price — the return comes from the funding/carry spread, not direction.',
  'funding carry': 'Hold spot long and the perpetual future short to collect the funding rate perps pay longs. Delta-neutral; the edge is the funding yield over cash.',
  'funding rate': 'A small payment exchanged between perpetual-future longs and shorts every few hours to keep the perp price near spot. When positive, shorts get paid.',
  'funding persistence': 'How reliably a coin\'s funding stays positive month to month. High persistence = the carry is repeatable, not a one-off.',
  'basis': 'The price gap between the perpetual future and spot. A drag on the carry when it moves against the position.',
  'btc beta': 'How much the book moves for a 1% move in Bitcoin. Near zero = genuinely delta-neutral (price-direction doesn\'t matter).',
  'risk of ruin': 'Modelled probability that the account falls below a chosen floor (e.g. −70%) over the horizon, given the strategy and tail assumptions.',
  'single-venue loss of book': 'What it costs the whole portfolio if one exchange simply disappears with the funds parked there.',
  'tail': 'The rare, severe outcomes (exchange failure, de-peg, gap). Judged separately because averages hide them.',
  'go-live anchor': 'The date forward-evidence tracking started. Everything after it is genuine out-of-sample, not backtest.',
  'forward evidence': 'Real results since the go-live date, compared against what the backtest predicted. The honest test that the edge is still there.',
  'shadow ledger': 'A paper record of what the strategy would have done, kept for evidence. No real orders are placed.',
  // --- macro ---
  hawkish: 'Leaning toward tighter monetary policy (higher rates) — usually supportive of the currency.',
  dovish: 'Leaning toward looser monetary policy (lower rates) — usually a drag on the currency.',
  surprise: 'Actual release vs the consensus forecast, read for its effect: a hot inflation print is currency-positive/hawkish; a weak jobs print is currency-negative/dovish.',
  'surprise momentum': 'Whether the recent run of data surprises is trending hawkish or dovish for this currency.',
  cot: 'CFTC Commitments of Traders — weekly report of how large speculators are positioned. A crowded position can signal a turning point.',
  'economic strength': 'A composite of growth / jobs / inflation readings for an economy, relative to trend and forecast.',
  'composite score': 'All the macro category scores combined into one number for the instrument. Positive = bullish lean, negative = bearish.',
  regime: 'The prevailing cross-asset market state (risk-on / risk-off / trending / ranging), inferred from DXY, equities, oil, yields, BTC.',
  breadth: 'What share of tracked instruments are bullish vs bearish — a market-wide participation gauge.',
  'data quality': 'How complete and fresh the inputs behind a score are (0–100). Low = treat the score with caution.',
  seasonality: 'The average historical tendency of an instrument at this point in the calendar — context only, not a signal.',
  smc: 'Smart Money Concepts — a price-structure read (liquidity sweeps, market-structure shifts, fair-value gaps).',
  'evidence coverage': 'How many of the signal categories actually have live data right now. A missing provider is "unavailable", not bearish and not neutral.',
  'evidence fusion': 'Combining several independent signal categories (technical, smart-money, macro, positioning, regime, seasonality, sentiment) into one weighted directional read.',
  // --- intraday co-pilot (Phase 100) ---
  'base rate': 'How often an outcome happened in the past in the same situation — the baseline before any skill or read is added.',
  'up rate': 'Share of past occurrences where price closed higher N bars later. 50% = no directional lean; a coin flip.',
  mfe: 'Maximum Favourable Excursion — how far price ran in your favour before the horizon, in R (ATR multiples). "Best case if it went your way."',
  mae: 'Maximum Adverse Excursion — how far price ran against you before the horizon, in R. "Worst drawdown you would have sat through."',
  'near coin flip': 'The up/down split is within ~4 points of 50/50 — no directional edge. Most conditions land here, and that is the expected result.',
  'weak skew': 'A small directional lean in the history (4–8 points off 50/50). Treat as a hypothesis, not a signal — many conditions are tested, so some look skewed by chance.',
  'notable skew': 'A larger directional lean in the history (>8 points off 50/50). Still just a hypothesis given how many condition/instrument/horizon combos are scanned.',
  'tr/atr': "The latest bar's range ÷ the average bar range (ATR). Below 1 = quieter than usual, above 1 = a bigger-than-normal bar.",
  session: 'Which trading session the bar falls in — Tokyo, London, New York, or the quieter gaps between them.',
  'vol contraction': 'Recent bar ranges are shrinking versus their average — the market is coiling / going quiet.',
  'vol expansion': 'Recent bar ranges are growing versus their average — the market is moving more than usual.',
  'trend up': 'Short-term moving-average structure is pointing up on this timeframe.',
  'trend down': 'Short-term moving-average structure is pointing down on this timeframe.',
  'pdh test': "Price is testing the prior day's high — a level a lot of traders watch.",
  'pdl test': "Price is testing the prior day's low — a level a lot of traders watch.",
  'sweep low': 'Price poked below a recent low and snapped back — often a stop-run below obvious sell stops.',
  'sweep high': 'Price poked above a recent high and snapped back — often a stop-run above obvious buy stops.',
  'failed breakout': 'Price broke a level, then reversed back through it — the breakout did not hold.',
  'range extreme high': 'Price is at the top of its recent range.',
  'range extreme low': 'Price is at the bottom of its recent range.',
  'session open london': 'The bar coincides with the London session open — a common volatility pickup.',
  'setup-skill tracker': 'Once you log real trades tagged to a setup, this compares your actual results on that tag to the historical base rate — telling you whether your read adds anything.',
  'n (occurrences)': 'How many times this exact situation occurred in the historical sample. More = a more reliable base rate.',
  // --- misc ---
  calmar: 'Annualised return ÷ max drawdown. Higher = more return per unit of worst-case pain.',
  sharpe: 'Return above cash ÷ volatility. Higher = smoother path to the same return. >1 is good, >2 is very good.',
  'annual vol': 'How much the return bounces around year to year (annualised standard deviation). Lower = smoother.',
  slippage: 'The difference between the price you expected and the price you got — modelled as a cost in backtests.',
  'setup state': 'Whether the market currently satisfies a validated strategy: READY only behind a validated edge with every mandatory condition met.',
  atr: 'Average True Range — a measure of how much price typically moves in a bar. Stops/targets are often sized in ATR multiples.',
  'mtf bias': 'Multi-timeframe bias — the directional read on each timeframe (1D→1M). Agreement across timeframes is stronger.',
}

export function glossaryLookup(term: string): string | undefined {
  return GLOSSARY[term.trim().toLowerCase()]
}

/**
 * A small "?" that reveals an explanation on hover / focus / tap.
 *
 * The panel is rendered in a portal with `position: fixed` so it is never
 * clipped by an ancestor's `overflow: hidden` and never sits behind a sibling
 * in the stacking order. Hovering the panel itself keeps it open (a short
 * close delay bridges the gap between the "?" and the panel).
 */
export function InfoTip({ text, children }: { text: string; children?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; placement: 'top' | 'bottom' }>()
  const id = useId()
  const btnRef = useRef<HTMLButtonElement>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const PANEL_W = 260

  const place = useCallback(() => {
    const el = btnRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const spaceBelow = window.innerHeight - r.bottom
    const placement: 'top' | 'bottom' = spaceBelow < 140 && r.top > 140 ? 'top' : 'bottom'
    let left = r.left + r.width / 2 - PANEL_W / 2
    left = Math.max(8, Math.min(left, window.innerWidth - PANEL_W - 8))
    setPos({
      top: placement === 'bottom' ? r.bottom + 6 : r.top - 6,
      left,
      placement,
    })
  }, [])

  const show = useCallback(() => {
    clearTimeout(closeTimer.current)
    place()
    setOpen(true)
  }, [place])

  const hide = useCallback((immediate = false) => {
    clearTimeout(closeTimer.current)
    if (immediate) return setOpen(false)
    closeTimer.current = setTimeout(() => setOpen(false), 140)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onScroll = () => setOpen(false)
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  useEffect(() => () => clearTimeout(closeTimer.current), [])

  return (
    <span className="inline-flex items-center">
      {children}
      <button
        ref={btnRef}
        type="button"
        aria-label="Explanation"
        aria-describedby={open ? id : undefined}
        onMouseEnter={show}
        onMouseLeave={() => hide()}
        onFocus={show}
        onBlur={() => hide(true)}
        onClick={(e) => {
          e.preventDefault()
          open ? hide(true) : show()
        }}
        className="ml-0.5 inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border border-border-subtle text-[9px] leading-none text-muted hover:border-accent hover:text-accent"
      >
        ?
      </button>
      {open && pos
        ? createPortal(
            <span
              id={id}
              role="tooltip"
              onMouseEnter={show}
              onMouseLeave={() => hide()}
              style={{
                position: 'fixed',
                top: pos.top,
                left: pos.left,
                width: PANEL_W,
                transform: pos.placement === 'top' ? 'translateY(-100%)' : undefined,
              }}
              className="z-[100] rounded-md border border-border bg-surface-elevated px-2.5 py-2 text-[11px] font-normal normal-case leading-snug tracking-normal text-secondary shadow-lg"
            >
              {text}
            </span>,
            document.body,
          )
        : null}
    </span>
  )
}

/** A label whose meaning is in the glossary — renders the label + an InfoTip. */
export function Term({ label, explain }: { label: string; explain?: string }) {
  const text = explain ?? glossaryLookup(label)
  if (!text) return <>{label}</>
  return <InfoTip text={text}>{label}</InfoTip>
}
