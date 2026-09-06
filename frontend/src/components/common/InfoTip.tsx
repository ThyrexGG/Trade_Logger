import { useId, useState, type ReactNode } from 'react'

/**
 * Plain-English explanations for the jargon that shows up around the app.
 * Keys are matched case-insensitively; `<Term>` looks a label up here.
 */
export const GLOSSARY: Record<string, string> = {
  sqn: "System Quality Number — expectancy ÷ standard deviation of trade results, ×√N. Van Tharp's scale: <1 hard to trade, 1.6–2 good, 2.5+ excellent, 3+ superb.",
  expectancy: 'Average profit (or loss) per trade, in account currency. Positive = the strategy makes money on average.',
  'expectancy r': 'Average profit per trade measured in R — multiples of the amount risked. +0.3R means each trade nets 0.3× the risk on average.',
  r: 'One R = the amount risked on a trade (entry to stop). Results in "R" are risk-normalised so trades of different size compare directly.',
  'r-multiple': 'A trade result divided by the amount risked. +2R = made twice what was risked; −1R = hit the stop.',
  'profit factor': 'Gross profit ÷ gross loss. Above 1 is profitable; 1.5+ is solid; below 1 loses money.',
  'win rate': 'Share of trades that closed in profit. A low win rate can still be profitable if winners are much bigger than losers.',
  drawdown: 'The largest drop from an equity peak to a later trough. Measures the worst losing stretch you would have sat through.',
  'max drawdown': 'The largest peak-to-trough equity decline over the period — the deepest hole the account went into.',
  'wilson ci': 'Wilson score confidence interval — a robust range for the true win rate given a small sample. Wide interval = not enough trades to be sure.',
  'bootstrap ci': 'A confidence range built by resampling the actual trades thousands of times. If the lower bound is above zero, the edge is unlikely to be luck.',
  'f*': 'The recommended fraction of capital to allocate — here, the largest size where a single venue failing still costs ≤12% of the whole book.',
  rrs: 'Research Ranking Score — a decomposable sorting aid for candidate strategies. NOT a trading signal; just orders the leaderboard.',
  'delta-neutral': 'Long and short offsetting positions so the book barely moves with price — the return comes from the funding/carry spread, not direction.',
  'funding carry': 'Holding spot long and the perpetual future short to collect the funding rate perps pay longs. Delta-neutral; the edge is the funding yield over cash.',
  'oos': 'Out-of-sample — data the strategy was NOT fitted on. Out-of-sample results are the honest test of an edge.',
  wfo: 'Walk-forward optimisation — repeatedly fit on a window, test on the next unseen window, roll forward. Guards against curve-fitting.',
  holdout: 'A slice of data sealed away and never looked at during research, kept for one final unbiased check.',
  hawkish: 'Leaning toward tighter monetary policy (higher rates) — usually supportive of the currency.',
  dovish: 'Leaning toward looser monetary policy (lower rates) — usually a drag on the currency.',
  surprise: 'Actual release vs the consensus forecast. A "beat" or "miss" and its direction for the economy / for policy.',
  cot: "CFTC Commitments of Traders — weekly report of how large speculators are positioned. A crowded position can signal a turning point.",
  'risk of ruin': 'Modelled probability that the account falls below a chosen floor (e.g. −70%) over the horizon, given the strategy and tail assumptions.',
  calmar: 'Annualised return ÷ max drawdown. Higher = more return per unit of worst-case pain.',
  sharpe: 'Return above cash ÷ volatility. Higher = smoother path to the same return. >1 is good, >2 is very good.',
}

export function glossaryLookup(term: string): string | undefined {
  return GLOSSARY[term.trim().toLowerCase()]
}

/**
 * A small "?" that reveals an explanation on hover / focus / tap. Dependency-free.
 */
export function InfoTip({ text, children }: { text: string; children?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span className="relative inline-flex items-center">
      {children}
      <button
        type="button"
        aria-label="Explanation"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => {
          e.preventDefault()
          setOpen((v) => !v)
        }}
        className="ml-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-border-subtle text-[9px] leading-none text-muted hover:border-accent hover:text-accent"
      >
        ?
      </button>
      {open ? (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-0 z-30 mb-1 w-64 rounded-md border border-border bg-surface-elevated px-2.5 py-2 text-[11px] font-normal leading-snug text-secondary shadow-lg"
        >
          {text}
        </span>
      ) : null}
    </span>
  )
}

/** A label whose meaning is in the glossary — renders the label + an InfoTip. */
export function Term({ label, explain }: { label: string; explain?: string }) {
  const text = explain ?? glossaryLookup(label)
  if (!text) return <>{label}</>
  return <InfoTip text={text}>{label}</InfoTip>
}
