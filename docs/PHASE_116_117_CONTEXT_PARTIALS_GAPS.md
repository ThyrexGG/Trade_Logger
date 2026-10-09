# Phases 116–117: what is TJR's setup missing? Context, win-rate optics, opening gaps

Run 2026-10-09. Code: [`phase116_regime_context.py`](../phase116_regime_context.py),
[`phase116b_partials_optics.py`](../phase116b_partials_optics.py),
[`phase117_gap_fill.py`](../phase117_gap_fill.py),
[`phase117b_gap_drift.py`](../phase117b_gap_drift.py). Same data, clock handling
and costs as phases 101–115 (NQ/ES 1-minute, 2023-04 → 2026-10; explore 2023–24,
confirm 2025–26). Rules and pass bars were fixed before each run.

Question from the user: phases 101–115 found no mechanical edge, so *what is
missing*, and what similar thing can be traded by hand?

## 116 — does any context make TJR's setup work?

The Phase 115 trades (TJR-faithful set and the better SWEEP-stop set, NQ + ES,
one per day) were sliced by things known before entry: volatility regime, weekday,
stop size vs ATR, gap size, trade vs 20-day trend, trade vs yesterday's direction,
after-win / after-loss, long/short, entry hour.

| Result | |
|---|---|
| Slices with ≥30 trades in both halves | 96 |
| Positive in BOTH halves | **1** (NQ Mondays, +0.01R / +0.02R: noise) |
| Survived the correction for 96 tests | **0** |
| Monthly strategy R vs the month's volatility (correlation) | NQ −0.02, ES +0.02 |

The 2025–26 half is negative in almost every slice (about −0.2R): the setup
doesn't hide a good pocket, it loses broadly.

**Was Jan–May 2026 a special market?** No. NQ's average daily range was **1.39%**
vs **1.33%** in 2023–25 (ES 1.00% vs 0.98%). NQ rose 19% and ES 10% over those five
months, a strong but not unusual stretch. Volatility doesn't explain TJR's
results, and the setup's results don't depend on it.

## 116b — a 64% win rate without an edge

TJR reports a ~64% win rate and an average win/loss of ~1.2–1.4. He takes partials
at nearby draws on liquidity and moves the stop to breakeven. The same Phase 115
entries (EITHER sweep, stop beyond the 2nd high/low, 09:30–11:30, one per day) were
re-scored with scale-out ladders; "win" = net R > 0, as TradeZella counts it.

| Ladder (NQ) | Win rate | Avg win / avg loss | Mean R after costs |
|---|---|---|---|
| Half at first draw ≥1R (Phase 115) | 31% | +1.91 / −1.10 | −0.16 |
| Half at 1R, rest 2R | 48% | +0.88 / −1.11 | −0.14 |
| Thirds at 1R, 2R, 3R | 48% | +0.85 / −1.11 | −0.16 |
| Quarter 0.5R, quarter 1R, half 2R | 57% | +0.49 / −0.91 | −0.12 |
| **Half at 0.5R, rest 2R** | **64%** | +0.42 / −1.10 | **−0.12** |

ES gives the same picture (64% win rate, −0.13R). Taking a partial at 0.5R produces
**TJR's exact win rate on entries that lose money**. A high win rate comes from how
the trade is managed, not from the entry being good. Every ladder sits on the same
trade-off (win rate × payoff ≈ the same gross ≈ 0), and none reaches his claimed
pairing of 64% *and* wins 1.2–1.4× the size of losses. That pairing implies
about +0.4–0.5R per day, which our entries can't produce.

## 117 — the opening gap, tested as a trade

Phase 109 measured that small gaps fill ~70% by noon. Priced as a trade (entry
09:45 or 10:00 if the gap is still unfilled, direction toward the previous close,
target = previous close, stop 1:1 or beyond the opening extreme, flat 12:00, costs
included), 24 cells:

- **Fill rates from the entry time are lower than the headline**: small gaps
  34–48%, mid 20–26%, **big (≥0.7 of the 14-day average range) only about 10–13%**. Most
  small-gap fills happen before 09:45. Small and mid gaps: no edge (confirm
  −0.15…+0.15R, every CI spans zero).
- **Big gaps are the exception.** The target rarely fills, but price drifts toward
  the previous close and most trades end at the noon time exit in profit.
  **1 of 24 cells passes** the pre-registered bar (ES, big gap, 09:45, 1:1 stop:
  +0.18R, 95% range corrected for 24 cells +0.005…+0.345, 2025 +0.26, 2026 +0.09).
  The other big-gap cells point the same way (NQ +0.12…+0.13R, ES +0.16…+0.18R) with
  intervals that include zero.

### 117b — is it a stable pattern?

Raw drift toward the previous close after entry (no stop, target or costs), in units
of the 14-day average range:

| Big gap ≥ | ES, entry 09:45, exit 12:00 | NQ, entry 09:45, exit 12:00 |
|---|---|---|
| 0.5 | 2023–24 −0.02 (t −0.5) · **2025–26 +0.11 (t 2.6)** | +0.01 · **+0.09 (t 2.1)** |
| 0.7 | −0.03 (t −0.5) · **+0.23 (t 3.6)** | −0.06 (t −1.0) · **+0.18 (t 3.0)** |
| 1.0 | −0.08 (t −0.9) · **+0.28 (t 3.0)** | −0.03 · **+0.16 (t 1.9)** |

- **In 2025–26 it's a plateau, not a spike:** every entry time (09:45, 10:00), exit
  time (11:00 → 15:55) and threshold (0.5, 0.7, 1.0) points the same way, the drift
  **grows with gap size**, and the share of days moving toward the fill is 51–73% (higher for bigger gaps).
  By month, most months were positive. Not driven by outliers (the median trade is
  positive; the top 5 days aren't carrying it).
- **In 2023–24 the sign was flat to slightly opposite** (big gaps drifted on).
  It's a **regime**, not a constant.
- NQ and ES are one observation, not two (same days, correlation 0.91).
- The 2025–26 half is **no longer a clean holdout**: it has been looked at through
  17 phases. One passing cell in 24, a sign flip between halves and a repeatedly
  used holdout together mean: **promising, not established**.
- It doesn't rescue TJR's setup: his sweep trades on big-gap days are still
  negative (−0.13R to −0.19R, Phase 116 gap slices).

## Verdict

| Question | Answer |
|---|---|
| Does context (regime, weekday, stop size, trend…) make the setup work? | **No** (0 of 96 slices) |
| Was Jan–May 2026 an unusual market? | **No** |
| Is his 64% win rate evidence of entry edge? | **No**: early partials reproduce it on entries that lose |
| New candidate | **Fade big opening gaps toward the previous close from 09:45, hold to ~noon**: real in 2025–26, absent in 2023–24 → forward-track |

## What this means for trading it by hand

The candidate rules, written down today so a forward test can't be accused of
hindsight: gap = 09:30 open vs the prior 16:00 close; size ≥ 0.7 × the average
daily range of the last 14 sessions; at 09:45, if the gap is still unfilled and price
hasn't moved through the previous close, trade **toward** the previous close; the
natural stop is wide (1:1 to the target distance, ~257 points on NQ and ~47 on ES,
so the position must be small); exit at ~12:00 or when the previous close is
reached. About 40–55 qualifying days a year per market.

It needs ~25–50 forward trades before it can be called anything. It also says
nothing about the user's own edge, which only their journal can show.
