# Phase 123: how big are the gap-fade stops, and what do other placements do?

Run 2026-10-09. Code: [`phase123_stop_sizes.py`](../phase123_stop_sizes.py). Setups: gap ≥ 0.2 × the
14-session average range, still unfilled at 09:45, fade toward yesterday's close, target =
yesterday's close, exit 12:00, NQ and ES, 2023-04 → 2026-10. Exploratory (nothing here is a tested
edge). Every placement is judged by points made per trade as a % of the average daily range (R is
not comparable between stop sizes).

## How the stops are placed

| Option | Stop distance from the entry | Why |
|---|---|---|
| **Wide** (the default in Phases 117–122) | **the same distance as the target** (|entry − yesterday's close|) | 1:1 by construction; no structure involved. Its size is whatever is left of the gap at 09:45, so it is large (≈257 NQ points on the ≥0.7× gaps) |
| **Tight** | just beyond the high (gap up) / low (gap down) made between 09:30 and the entry; at least 0.10 × the average range | a structure-style stop |
| Medium (new) | 0.25 × the average daily range | a fixed fraction of normal movement |
| Fixed (new) | 0.21% of the entry price (≈ 64 NQ points at 31,000) | the user's usual stop size |

## Results (gap ≥ 0.2×)

| Mkt | Stop | Median stop | % of price | Stopped out | Win rate | Avg P&L (% of daily range) |
|---|---|---|---|---|---|---|
| NQ | Wide | 140 pts | 0.70% | 20% | 51% | +0.9% |
| NQ | Medium | 63 pts | 0.30% | 47% | 45% | +1.9% |
| NQ | Fixed | 43 pts* | 0.21% | 61% | 36% | +0.9% |
| NQ | Tight | 38 pts | 0.17% | 61% | 36% | +1.5% |
| ES | Wide | 25 pts | 0.45% | 20% | 49% | +0.7% |
| ES | Medium | 12 pts | 0.21% | 46% | 44% | +1.2% |
| ES | Fixed | 12 pts | 0.21% | 49% | 41% | 0.0% |
| ES | Tight | 7 pts | 0.12% | 63% | 34% | +0.5% |

\* the history includes lower index levels; the same 0.21% is ~64 points at today's 31,000.

**Reading it:** every placement averages within a fraction of one percent of the daily range per
trade, which is noise (the spread of single trades is far larger). Stop size changes the *shape*
(wide: rarely stopped, many small time exits; tight: stopped most of the time, fewer but larger
wins), not whether the rule makes money. The wide stop's R values look huge because 1R is large;
the same trade with a smaller stop is simply a bigger position for the same dollar risk.

## Indicator

`tradingview/big_gap_fade.pine` now offers all four (Wide / Medium / Fixed / Tight) in the "Stop"
setting, through one function (`calcRisk`) used by both the dashed plan and the live trade.

## Phase 124: stops and targets from internal structure (the user's own method)

Code: [`phase124_structure_stops.py`](../phase124_structure_stops.py). The user places stops and targets
on internal 1- and 5-minute swing highs and lows. Same setups, swings = TJR's two-candle definition,
all known at the 09:44 close (bars from 08:30). Stop = just beyond the NEAREST swing on the far side
(1-minute S1 or 5-minute S5; one closer than 0.05 × the range is skipped). Targets: yesterday's close
(PC), the nearest 5-minute swing at least 1R away (STR), or half off at the nearest 5-minute swing at
least 0.5R away with the stop to breakeven and the rest at yesterday's close (HALF). Average P&L per
trade as a % of the average daily range (gap ≥ 0.2×; the ≥0.7× runs say the same):

| Mkt | Stop (median size) | Target | n | Win rate | Avg P&L | 95% interval |
|---|---|---|---|---|---|---|
| NQ | Wide (140 pts) | yesterday's close | 526 | 50% | +0.8% | −2.7 … +4.3 |
| NQ | 1-min swing (21 pts) | close / 5m swing / half | 411 | 23% / 33% / 38% | +0.1 / −0.5 / +0.2% | all include 0 |
| NQ | 5-min swing (33 pts) | close / 5m swing / half | 368 | 33% / 43% / 48% | +0.1 / −0.2 / 0.0% | all include 0 |
| ES | Wide (25 pts) | yesterday's close | 543 | 49% | +0.6% | −2.6 … +3.9 |
| ES | 1-min swing (4 pts) | close / 5m swing / half | 422 | 22% / 34% / 39% | −1.3 / −0.7 / −0.9% | all include 0 |
| ES | 5-min swing (6 pts) | close / 5m swing / half | 387 | 31% / 39% / 47% | −1.6 / −1.9 / −1.4% | all include 0 |

**Reading it:** structure stops are small (about 21–33 NQ points, 4–6 ES points) and every combination
averages about zero. Taking half off at the first 5-minute level lifts the win rate to 38–51% without
moving the average, the same pattern as Phase 116b. On ES the very small stops cost a bit more in
spread and slippage relative to their size. Stop and target placement changes the shape of the results,
not whether the setup makes money.

**Indicator:** the "Stop" setting now also offers *Structure: beyond the nearest 1-minute swing* and
*… 5-minute swing*, and a new "Target" setting offers yesterday's close, the nearest 5-minute swing
(1R or more away), or half at the nearest 5-minute swing with the rest at yesterday's close (a dashed
aqua line marks the half-off level; the stop moves to breakeven after it). Swings are read from the 1-
and 5-minute data as of the end of the previous chart bar, so the entry bar only sees swings known before it.

## Phase 125: half off at +1R, stop to breakeven

Code: [`phase125_partial_1r.py`](../phase125_partial_1r.py). The user manages trades by taking half at
+1R and moving the stop to breakeven. The same setups were run twice per stop placement (the wide stop is
skipped, its 1R is yesterday's close): plain, and half at +1R with the rest at yesterday's close or 12:00.
Paired by day, NQ and ES, gap ≥ 0.2×:

| Stop | Win rate plain → with half-off | Average P&L (% of range) plain → with half-off | Difference, 95% interval |
|---|---|---|---|
| NQ tight | 36% → 54% | +1.5 → +0.9 | −0.6 (−1.9 … +0.6) |
| NQ medium | 45% → 53% | +1.8 → +0.9 | −0.9 (−2.1 … +0.3) |
| NQ 5-min swing | 33% → 52% | +0.1 → +0.1 | 0.0 (−1.4 … +1.5) |
| ES tight | 34% → 52% | +0.4 → −0.7 | −1.1 (−2.5 … +0.1) |
| ES 5-min swing | 31% → 51% | −1.6 → −1.2 | +0.4 (−0.8 … +1.7) |

(The other combinations and the ≥ 0.7× runs say the same: 10 of 10 win rates rise by 8–20 points, the
average changes by −2.7 to +1.0, every interval includes zero.) **Half off at +1R lifts the win rate
(fewer full losses) and leaves the average where it was, slightly lower on most stops.** It changes how the
trades feel, not whether the setup makes money, the same finding as Phases 101b and 116b.

Both the indicator and the strategy now offer *Half at +1R, stop to breakeven, rest at yesterday's close*
as a Target option.
