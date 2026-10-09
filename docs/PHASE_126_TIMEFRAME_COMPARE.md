# Phase 126 - the gap-fade strategy on 1m / 5m / 15m, NQ + ES, Mar 2023 - Oct 2026

Script: `phase126_timeframe_compare.py` (rows in `.cache/phase101/phase126_rows_<thr>.csv`). EXPLORATORY, not pre-registered.
Same rule as `tradingview/big_gap_fade_strategy.pine`; the trade is simulated on the chart timeframe's bars (stop checked
before target when one bar touches both), costs = spread + slippage. Everything before the entry is identical on every timeframe.

## Findings
- **Timeframe barely matters.** Wide stop + yesterday's close: 1m +0.005R, 5m +0.003R, 15m -0.005R (all zero). Only the
  half-at-1R and 1-minute-structure-stop variants lose a bit more on 15m (a coarse bar can hit both levels).
- **Gap >= 0.2 x range (learning mode), 1,069 trades:** nothing. Default Wide/close = 0.00R, PF 1.0. Tight stop +0.08R and
  Medium +0.06R are inside the noise (95% interval includes 0). Structure stops are negative (-0.14R with 1m swings).
  Half at +1R lifts the win rate (about 35-45% to 53%) but not the average R.
- **Gap >= 0.7 x range, 318 trades:** Wide +0.07R, Medium +0.20R, Tight +0.29R (intervals just above 0), but by year pooled:
  2023 -0.29R, 2024 +0.01R, 2025 +0.27R, 2026 +0.18R. Same regime-dependence as Phases 116-125; ~24 configs examined.
- The user's TradingView run (NQ, Jul-Oct 2026, 47 trades, +17.6%) reproduces here: NQ 49 trades, +0.09R, 53% wins. ES in the same
  months was -0.13R. A good NQ stretch, not a stable edge.
