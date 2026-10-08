# Phase 101: NY-open liquidity sweep + reversal (TJR-style) on NQ and ES

Run 2026-10-08. Code: [`phase101_ny_open_sweep.py`](../phase101_ny_open_sweep.py)
(`python -m phase101_ny_open_sweep [--fetch]`). Tests:
`tests/test_phase101_ny_open_sweep.py`.

## Verdict (first)

**`NO_EDGE`**: none of the 16 pre-registered versions passed. None reached even
"promising".

- **Out of sample (the last 40% of days, since 2026-03-17)**, 13 of 16 versions
  lost money after costs; the other three were within ±0.08R of zero with
  wide error bars. Five were negative with a 95% confidence interval wholly
  below zero.
- **Before any costs** the setups are roughly break-even: NQ pooled −0.05R
  per trade, ES +0.06R. After a realistic spread and slippage, NQ is −0.13R
  and ES −0.06R. Costs alone (0.03–0.15R per trade) are bigger than any
  raw edge.
- **No version beat random direction:** with the same entry times, stops and
  targets but a coin flip for long/short, every placebo p-value was ≥ 0.12
  (needed < 0.05).
- **The 4-year check on 15-minute bars (Apr 2023 → Oct 2026)** agrees: the
  simple sweep-and-reclaim version is negative on 7 of 8 level/instrument
  pairs. The TJR entry almost never forms on 15-minute bars (2–9 trades in 4
  years), so it can't be replicated there.

In plain words: **at 2R targets, fading the first sweep of these levels after
the 9:30 open did not make money on NQ or ES over the last 17 months**, and
over 4 years on coarser data. The TJR sequence (sweep, then structure shift,
then fair value gap) fired on only 15–58 of ~350 days and didn't do better
than the simple version.

This is consistent with the earlier killzone result (664 trades, PF < 1; see
the memory note) and with Phase 75 (opening-range breakout, no edge). Per
standing practice, **don't add filters to rescue it**. With 16 versions
already tested, extra filters mostly find luck.

## What was tested (fixed before looking at any result)

| | |
|---|---|
| Instruments | NQ = `NDX100`, ES = `SPX500` (FundedNext MT5 CFDs) |
| Main data | 5-minute bars, 2025-05-13 → 2026-10-08 (~350 trading days each) |
| Replication | 15-minute bars, usable from 2023-04 (earlier bars miss the open) → 2026-10-08 |
| Split | in-sample = first 60% of days; out-of-sample from 2026-03-17 |
| Levels | **OR** first 5 min after 09:30 · **ON** overnight 18:00→09:30 · **LDN** London 02:00→05:00 NY · **PD** previous day's 09:30→16:00 high/low |
| RECLAIM entry | price trades beyond the level, then a bar closes back inside within 30 min → enter at that close |
| TJR entry | sweep → a close beyond the low/high of the 3 bars leading into the sweep extreme (within 60 min) → the fair value gap in that move → limit order at the gap's near edge (valid 60 min; cancelled if the sweep extreme breaks first) |
| Risk | stop at the sweep extreme, target 2R, sweeps 09:30–11:00, entries before 11:00, flat at 12:00 NY, one trade per day per version |
| Costs | recorded bar spread (NQ ≈ 1.6 pts, ES ≈ 0.6 pts), plus slippage on every market fill (NQ 0.50, ES 0.10). Stops tighter than 2× spread are skipped |
| Pass bar | CANDIDATE needs out-of-sample N ≥ 30 and mean > 0 with the Bonferroni-widened CI (16 versions) above 0, in-sample > 0, placebo p < 0.05, and the 15-minute 4-year run also positive |

Conservative conventions: a bar touching both stop and target counts as a
stop, and a limit fill's own bar only checks the stop. Both were confirmed by
tracing individual trades by hand.

## Results

R = profit in multiples of the risk taken (stop distance), after costs.

| Mkt | Level | Entry | N | Win% | Mean R | In-sample | OOS N | OOS mean [95% CI] | Placebo p | 15m 4y N | 15m 4y mean | Cost R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ | OR | RECLAIM | 284 | 36% | −0.12 | −0.09 | 117 | −0.15 [−0.40, +0.09] | 0.77 | 549 | −0.03 | 0.10 |
| NQ | OR | TJR | 47 | 38% | −0.15 | −0.13 | 26 | −0.16 [−0.48, +0.17] | 0.57 | 4 | +0.08 | 0.03 |
| NQ | ON | RECLAIM | 233 | 36% | −0.09 | −0.11 | 90 | −0.06 [−0.34, +0.22] | 0.40 | 504 | −0.08 | 0.10 |
| NQ | ON | TJR | 25 | 28% | −0.39 | −0.40 | 12 | −0.38 [−0.81, +0.10] | 0.56 | 2 | −0.06 | 0.03 |
| NQ | LDN | RECLAIM | 207 | 38% | −0.05 | +0.12 | 82 | −0.31 [−0.57, −0.05] | 0.83 | 455 | +0.07 | 0.07 |
| NQ | LDN | TJR | 34 | 32% | −0.24 | −0.08 | 14 | −0.47 [−0.85, −0.04] | 0.73 | 4 | +0.73 | 0.03 |
| NQ | PD | RECLAIM | 148 | 33% | −0.22 | −0.08 | 56 | −0.45 [−0.70, −0.17] | 0.95 | 297 | −0.05 | 0.07 |
| NQ | PD | TJR | 15 | 27% | −0.32 | −0.09 | 6 | −0.66 [−1.00, −0.31] | — | 3 | +0.56 | 0.03 |
| ES | OR | RECLAIM | 287 | 38% | −0.06 | +0.04 | 123 | −0.19 [−0.43, +0.05] | 0.23 | 558 | −0.13 | 0.15 |
| ES | OR | TJR | 58 | 47% | +0.02 | +0.08 | 21 | −0.09 [−0.53, +0.38] | 0.72 | 9 | +0.35 | 0.05 |
| ES | ON | RECLAIM | 197 | 38% | −0.03 | −0.06 | 80 | +0.01 [−0.31, +0.32] | 0.12 | 479 | −0.11 | 0.14 |
| ES | ON | TJR | 35 | 40% | −0.11 | −0.19 | 13 | +0.03 [−0.56, +0.70] | 0.65 | 5 | +0.40 | 0.04 |
| ES | LDN | RECLAIM | 212 | 35% | −0.10 | +0.05 | 88 | −0.32 [−0.57, −0.05] | 0.92 | 448 | −0.12 | 0.12 |
| ES | LDN | TJR | 42 | 33% | −0.20 | −0.21 | 15 | −0.18 [−0.70, +0.43] | 0.78 | 4 | +0.95 | 0.05 |
| ES | PD | RECLAIM | 135 | 41% | −0.03 | +0.14 | 47 | −0.34 [−0.66, +0.01] | 0.87 | 266 | −0.14 | 0.12 |
| ES | PD | TJR | 26 | 46% | +0.15 | +0.19 | 10 | +0.08 [−0.66, +0.89] | 0.55 | 3 | +1.02 | 0.05 |

A 2R target needs a win rate above ~34% plus costs to break even. Most
versions sit right at that line or below it.

The only positive-looking TJR rows (ES PD, ES OR, and the 15-minute TJR
column) rest on **3–58 trades**. That's far too few to separate skill from
luck, and none held up out of sample with a CI above zero.

## Data notes (worth knowing for any future MT5 research)

- **Broker clock:** FundedNext's server time is New York + 7 hours since the
  weekend of 2024-07-27, and was New York + 6 before. Both follow US
  daylight-saving time. This was measured from the data (the 09:30 open is
  the morning's biggest range jump) and is handled in `load()`. Getting it
  wrong shifts every session by an hour.
- **History cap:** the terminal's "Max bars in chart" is 100,000. That gives
  ~3 months of 1-minute, ~17 months of 5-minute and ~4 years of 15-minute
  history. Raising it (MT5 → Tools → Options → Charts → Max bars in chart →
  Unlimited) and running `--fetch` would give longer 1- and 5-minute samples.
- **Storage:** candles are cached in `.cache/phase101/` (git-ignored), never in
  the app database. Nothing here places or modifies orders.

## Follow-up: partial profit + stop to breakeven (101b)

Asked after the entry verdict: "take a partial at 1R or at a key level and
move the stop to breakeven". The **same entries and stops**, with three exit
plans fixed before running (`python -m phase101_ny_open_sweep --management`):

| Plan | Rule |
|---|---|
| **A: full to 2R** | the original: the whole position to 2R |
| **B: half at 1R** | close 50% at +1R, then stop → entry; the rest to 2R (flat at 12:00) |
| **C: half at a key level** | close 50% at the nearest of the day's marked highs/lows (OR / overnight / London / previous day) that is ≥ 0.5R away and short of 2R, else at 1R; then stop → entry; the rest to 2R |

The stop-to-breakeven applies from the bar after the partial. A bar touching
the stop before the partial is a full −1R. Slippage is charged on each
market exit, weighted by the size it closes.

**All 16 setups pooled (1,985 trades on 5-minute bars):**

| Plan | Win rate | Mean R / trade | Out-of-sample mean R | How trades ended |
|---|---|---|---|---|
| A: full to 2R | 36.9% | **−0.09** | −0.20 | 1,117 stopped · 498 hit 2R · 370 timed out |
| B: half at 1R + BE | **48.6%** | **−0.10** | −0.20 | 924 stopped · 418 partial→2R · 366 partial→breakeven · 277 timed out |
| C: half at key level + BE | **50.3%** | **−0.11** | −0.23 | 913 stopped · 406 partial→2R · 421 partial→breakeven · 245 timed out |

- **The win rate goes up by 12–13 points but the money doesn't change.** About
  190 trades that used to be full losses now bank +0.5R first. About 80 trades
  that used to run to the full 2R now give back their second half at
  breakeven. The two effects cancel.
- **Per setup:** B beat A in 6 of 16 setups and C in 8 of 16, a coin flip. It
  also cut the worst losing streak in some setups (e.g. NQ previous-day
  reclaim: drawdown 41R → 26R), but **no setup became positive out of
  sample** under B or C.
- **Expected outcome:** trade management changes the *shape* of the results
  (more frequent small wins, smoother equity). It can't create an edge the
  entries don't have, and the placebo above showed these entries pick
  direction no better than a coin.

Partials + breakeven can still be a **psychological** tool (fewer full
losers, so it's easier to stick to the plan), just not a profit tool here.
