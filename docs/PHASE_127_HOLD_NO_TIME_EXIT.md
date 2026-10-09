# Phase 127 - no time exit, half at +1R, stop to breakeven (the user's management)

Script: `phase127_hold_no_time_exit.py` (rows in `.cache/phase101/phase127_rows_<thr>.csv`). EXPLORATORY.
Same gap-fade entries as Phases 123-126, NQ + ES, Mar 2023 - 25 Sep 2026. Each entry is managed three ways: TIME12 (half at
+1R/BE, closed at 12:00), HOLD (stop or yesterday's close, up to 10 sessions, no time rule), HOLD_H1R (half at +1R, stop to
breakeven, rest to yesterday's close, up to 10 sessions). Stop before target within one 1-minute bar. Net of spread + slippage.

## Findings
- **Dropping the 12:00 exit changes nothing meaningful.** Medium stop + half at 1R: +0.03R with the time exit, +0.03R without.
  Gap >= 0.2 (1,055 trades): every HOLD_H1R row is between -0.13R and +0.03R; the best (Medium) has a 95% interval of [-0.04, +0.10].
- **Half at +1R / BE raises the win rate (about 31-37% to 53%) and leaves the average where it was** (Tight +0.10R plain vs 0.00R
  with the half). It trades fewer, bigger losses for more, smaller wins.
- **Gap >= 0.7 (315 trades):** Medium +0.08R, Tight +0.10R with the half, intervals include 0; positive mostly in 2025.
- With no time rule, big-gap trades with the Wide stop run a median 20 hours and 42% last past one session.
- The Pine strategy now defaults to this management (target "half at +1R", exit time "Never").
- **Half at the chart structure near +1R** (HOLD_HSTR: the 1m/5m swing, of the last 3 each, closest to +1R and 0.7R-1.5R away, else exactly +1R) is the same as a fixed +1R: Medium +0.04R vs +0.03R (gap >= 0.2), +0.08R vs +0.08R (gap >= 0.7). Reading structure for the half changes nothing measurable.
