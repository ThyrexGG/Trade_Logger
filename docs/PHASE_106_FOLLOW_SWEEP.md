# Phase 106: Follow the sweep (breakout / continuation) with a trend filter

Run 2026-10-09. Code: [`phase106_follow_sweep.py`](../phase106_follow_sweep.py)
(`python -m phase106_follow_sweep`, ~40 min). It mirrors the TradingView
indicator's *Follow the sweep* mode. Motivation: the user's own NQ trades mostly
went **with** the sweep, the opposite of the fade tested in Phases 101–105.

## Verdict

**`NO_EDGE`.** Following the sweep loses in every market and with every trend
filter. Before costs it is break-even; after costs it's negative.

| Market | No trend filter | 1-hour structure | Daily trend |
|---|---|---|---|
| **NQ** | −0.14R (892) | −0.10R (525) | −0.11R (843) |
| **ES** | −0.21R (890) | −0.09R (505) | −0.14R (825) |
| **FX London** (5 pairs) | −0.25R (4,482) | −0.27R (2,488) | −0.26R (4,102) |
| **FX New York** (5 pairs) | −0.33R (4,485) | −0.28R (2,633) | −0.25R (4,272) |

Per trade, after costs; trades in brackets (first setup per day per market,
2023-04 → 2026-10).

- **Before costs ≈ 0:** NQ −0.01R, ES −0.02R. Costs are 0.13R (NQ, median
  stop 21.6 pts) to 0.19R (ES, 4.5 pts) per trade, and more on FX (median
  stop 7.8 pips).
- **No better than the opposite direction:** taking the reverse trade at the
  same moments scores about the same (placebo p 0.13–1.0). The breakout
  carries no directional information, just like the fade.
- **The 1-hour trend filter helps a little on indices** (ES −0.21 → −0.09R,
  NQ −0.14 → −0.10R), but the intervals include zero and no year is clearly
  positive (ES 2023 +0.01, 2024 +0.01; everything else negative).

## The user's own trades vs these setups

**11 of the user's 18** NQ/ES trades (24 Sep – 8 Oct 2026) match a
follow-the-sweep setup (same market and direction, within 10 minutes), compared
with 3 of 18 for the fade. So this *is* close to how the user trades.

But at those same moments, the mechanical version (stop below the 3 pre-sweep
bars, fixed 2R target) lost **−4.8R in total**, while the user's actual trades
were mostly winners (+$298 over all 18). On 30 Sep, 1 Oct and 7 Oct the
mechanical setup was stopped out while the user's trade won.

**Reading:** the user's results come from *how* the trade is managed (exact
entry, stop placement, where profits are taken), not from the trigger. A
mechanical trigger with a fixed stop/target doesn't reproduce them. That's a
discretionary skill that only a longer tracked record can confirm or reject.
18 trades over two weeks is far too few.

## Design (pre-registered)

| | |
|---|---|
| Setup | a level breached; within 15 min a 1-minute close beyond the highest (lowest) breached level → long (short) at that close |
| Stop / target | beyond the 3 minutes before the sweep (+ buffer); 2R; flat at session end |
| Trend | NONE · H1 (1-hour swing structure at session start) · DAILY (prev close vs 20-day avg) |
| Sessions | NQ/ES 08:30–11:00 (flat 12:00); FX London 02:00–05:00 (flat 07:00) and NY 08:00–11:00 (flat 12:00) |
| Costs | bar spread + slippage + $5/lot FX commission |
| Pass | pooled CI above 0, ≥ 3 of 4 years positive, beats the opposite direction (p < 0.05) |
