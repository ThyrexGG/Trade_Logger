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
