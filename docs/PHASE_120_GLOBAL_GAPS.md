# Phase 120: the big-gap fade at other markets' own opens (Europe, Asia-Pacific)

Run 2026-10-09. Code: [`phase120_global_gaps.py`](../phase120_global_gaps.py). The NQ/ES gap fade
(Phases 116–118) triggers only ~45 times a year per index and its edge was visible only in
2025–26. To get more setups and a fresh test, the **same rule** was run at nine index CFDs that
open at other times, at each market's own cash open. Rules fixed before running.

## Rule (adapted to each market's local clock)

Gap = local cash open vs the previous local cash close, size = |gap| / mean cash-session range of
the previous 14 sessions; BIG ≥ 0.7 (0.5 also reported). Entry 15 minutes after the open (the US
09:45 equivalent) only if the gap is still unfilled, **toward** the previous close; target = previous
close; stop A = 1:1 (wide) or B = beyond the open-to-entry extreme (tight); exit at target / stop /
2.5 hours after the open. Costs = bar spread + 0.002% slippage. Server clock converted through
New York → UTC → local time (handles US/EU/AU daylight-saving mismatches).

Markets: DAX (GER30), CAC (FRA40), Euro Stoxx 50 (EUSTX50), SMI (SWI20), AEX (NTH25), FTSE (UK100),
Nikkei (JP225), Hang Seng (HK50), ASX 200 (AUS200); 3.5–4.3 years of 1-minute data.
Markets in a region trade the same day, so **each region counts once per day** (the average R of
its qualifying markets), the lesson from the Phase 118 correction.

## Results (gap ≥ 0.7, stop A, after costs)

| Region | Days / year | Mean per trade | 95% range | 2023–24 | 2025–26 |
|---|---|---|---|---|---|
| Europe (6 markets) | 74 | **−0.03R** | −0.08 … +0.03 | +0.02R | −0.07R |
| Asia-Pacific (3 markets) | 137 | **−0.06R** | −0.10 … −0.02 | −0.09R | −0.04R |

Per market: DAX −0.01R, FTSE −0.02R, CAC −0.04R, SMI −0.07R, Euro Stoxx −0.09R, AEX −0.11R,
Nikkei −0.04R, Hang Seng −0.07R, ASX 200 −0.07R. Tight stop B: Asia −0.33R, Europe −0.05R.
At gap ≥ 0.5 (more days: Europe 127/yr, Asia 178/yr) it is worse: Europe −0.10R, Asia −0.06R.

**PASS: neither region.** Asia is significantly negative. Europe is indistinguishable from zero.

Clock check: the biggest bar-range jump matched the cash open for DAX, AEX, FTSE, Nikkei and
Hang Seng; for CAC, Euro Stoxx and SMI the biggest jump is an hour later (10:00) and for the ASX
10 minutes earlier, probably pre-open activity or data releases; the open used is still the real
cash open, and the verified markets give the same answer.

## Verdict

| | |
|---|---|
| More setups from other markets | **Yes**: ~290 distinct market-opens a year across US, Europe and Asia |
| Does the gap fade work there? | **No**: Europe −0.03R, Asia −0.06R |
| What it says about the NQ/ES result | The 2025–26 US result did **not** replicate on nine other indices. It is most likely a US-open pattern of that period or chance. Treat it as **unconfirmed, probably noise** |

Frequency was never the problem: the rule has no measurable edge outside the US, where it was
barely above zero to begin with.
