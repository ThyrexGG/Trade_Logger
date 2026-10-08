# Phase 103: Why the mechanical NY-open sweep loses, and TJR's rules on 1-minute bars

Run 2026-10-08. Code: [`phase103_tjr_diagnostics.py`](../phase103_tjr_diagnostics.py)
(103a) and [`phase103b_tjr_m1.py`](../phase103b_tjr_m1.py) (103b). Follows
[Phase 101](PHASE_101_NY_OPEN_SWEEP.md) and [Phase 102](PHASE_102_TJR_FILTERS.md).

## Summary

1. **The 5-minute version loses because the sweep doesn't predict direction,
   not because of the stop, target or timing.** Trades start well (62% reach
   +0.5R, 45% reach +1R) but only 25% reach 2R before the stop. Stopped trades
   that later hit the original target (30%) happen just as often with a
   random direction (32%), so this isn't stop hunting peculiar to the setup.
   It's normal intraday swing size. No feature bucket (time, stop size,
   volatility, weekday, level, side) cleared the pre-set in-sample bar
   (N ≥ 40, mean ≥ +0.15R). The closest was "wide stops" at +0.14R.
2. **Coded as TJR describes it** (1-hour structure bias, untouched liquidity,
   1-minute sweep + fast shift + retrace entry), **the setup is rare: 1–2
   trades per index in ~73 trading days.** Three months of 1-minute history
   can't say whether it works. It needs years.

## 103a: diagnosis of Phase 101's 1,985 trades (5-minute bars)

| Question | Answer |
|---|---|
| How far do trades get before the stop / noon? | ≥0.5R 62% · ≥1R 45% · ≥1.5R 33% · ≥2R 25% · ≥3R 15% |
| Share stopped out | 63% |
| Stopped, then price reached the original 2R target anyway | 29.6% (random-direction placebo: 31.8%, so no difference) |
| In-sample buckets promoted (N ≥ 40, mean ≥ +0.15R) | none; best: stop > 20% of yesterday's range +0.14R (N 480) |

In-sample means by bucket (before 2026-03-17): first 15 minutes +0.01R ·
09:45–10:15 −0.12R · 10:15–11:00 +0.02R · tight stops −0.21R · wide stops
+0.14R · Friday +0.08R, other days −0.05 to +0.01R · ES +0.02R, NQ −0.06R.
These are the variations you'd expect from chance across ~1,200 trades.

## 103b: TJR's rules as written in public breakdowns, on 1-minute bars

| | Rule |
|---|---|
| Bias | 1-hour swing structure (fractal swings, last 5 days): both swing highs and lows rising → longs only; both falling → shorts only; mixed → no trade |
| Liquidity | previous day / week high-low, Asia and London highs/lows, untouched 1-hour swing points (last 48h); levels already traded through by 08:30 are excluded, and a level is spent after its first breach |
| Sweep | 1-minute bar through the level, close back inside within 2 bars |
| Shift | within 5 bars, a close beyond the 3-bar high/low before the sweep extreme |
| Entry | limit at the displacement origin (last opposite candle), valid 15 bars, must be a retrace (not already through the market) |
| Stop / exits | a few ticks beyond the wick; half at +1R, rest at the nearest opposite liquidity ≥ 2R (cap 5R); flat 12:00 |

**Data:** 2026-06-29 → 2026-10-08 (~73 trading days; the terminal holds only
100k 1-minute bars).

**How often each step happens (days):**

| | NQ | ES |
|---|---|---|
| days with a clear 1H bias | 51 | 45 |
| no bias-side level swept 08:30–11:00 | 29 | 22 |
| swept but no close back inside | 4 | 5 |
| reclaimed but no fast shift | 16 | 13 |
| a valid limit order placed | 2 | 4 |
| **filled trades** | **1** (+1.1R) | **1** (−0.1R) |

The first 1-minute run showed 51 trades (NQ +0.17R, ES −0.11R), but tracing
a trade by hand found two implementation errors against the written rules:
already-taken levels were still treated as liquidity, and some "limit"
entries were already through the market (chases). The corrected run above is
the one that counts.

## What would actually settle it

- **More 1-minute history.** In MT5: Tools → Options → Charts → *Max bars in
  chart* → Unlimited, restart MT5, then run `python -m phase101_ny_open_sweep
  --fetch` (fetch M1 too) and `python -m phase103b_tjr_m1`. Several years of
  1-minute data would give ~50–100 strict setups per index.
- **Your own tagged trades.** Discretion (which sweeps look "clean", which
  days to skip) is the part no code captures. Tag NQ/ES trades "TJR sweep" in
  the Journal; Analytics reports win rate and average R per tag after 30–50
  trades.
