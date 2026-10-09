# Phases 129-130 - scale out at the marked highs / lows, and a runner past yesterday's close

Scripts: `phase129_structure_ladder.py`, `phase130_runner_past_target.py` (rows in `.cache/phase101/phase129_rows_*.csv`, `phase130_rows_*.csv`).
Same gap-fade entries as Phases 123-127 (NQ + ES, Mar 2023 - 25 Sep 2026, no time exit, 10 sessions max). EXPLORATORY.

- **LADDER** (a third at each of the two nearest 1m/5m swings, stop to breakeven after the first and behind the first level after the second,
  last third to yesterday's close): win rate 49-59%, average R between -0.12 and +0.10 (gap >= 0.2: Medium +0.02R, Wide -0.01R, Tight -0.02R;
  gap >= 0.7: Medium +0.10R, Wide +0.08R). Same as one half at the first level (HALF_L1) or no partial at all, within the noise.
- **RUNNER** (the last part is not closed at yesterday's close: its stop moves to yesterday's close and trails behind each new 5-minute
  swing): changes the average by <= 0.02R. Wide +0.015R vs +0.003R (gap >= 0.2). Max winner 3.5R instead of 1.0R, but the same average.
  Whole position with a Tight stop and a trailed runner: +0.14R (gap >= 0.2, interval [-0.01, +0.30]), 31% wins; the same as the plain Tight stop.
- **LADDER + RUNNER together** (the user's full description): Wide +0.01R, Medium +0.03R, Tight -0.01R (gap >= 0.2); +0.10R / +0.10R / +0.08R (gap >= 0.7).
- Pattern across Phases 123-130: every management variant moves the WIN RATE (31% to 59%) and none moves the average R away from about zero.
  Winners that "got away" are offset by the trades that reversed before the level was reached.

Pine: `tradingview/big_gap_fade_strategy.pine` has the ladder + runner as the default Target ("Ladder: a third at each of two structure levels,
the last third runs past yesterday's close"). The indicator does not have it.
