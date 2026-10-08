# Phases 111–112: TJR's price-action video model, and the user's trade management on every strategy

Run 2026-10-09. Code: [`phase111_tjr_video_model.py`](../phase111_tjr_video_model.py),
[`phase112_manage.py`](../phase112_manage.py).

## Phase 111: "Once You Learn Price Action…" (TJR), exactly as taught

Source: transcript of TJR's video (YouTube `Xdu6j2E1DEI`, supplied by the user).
Three concepts: **manipulation** (a swing high/low is taken) → **break of
structure** (a close beyond the most recent opposite swing) → trade; plus a
**continuation** entry (the 15-minute retrace is a 5-minute mini trend that
breaks back).

Rules: 2-left/2-right swings (known only once confirmed); A = 15-minute sweep →
15-minute close through the last opposite swing within 1 hour, stop beyond the
sweep extreme; B = after A, a 5-minute counter-break then a 5-minute break back,
stop beyond the retrace extreme. Targets 2R or the next swing (≥ 1R, ≤ 4R).
Entries 09:30–12:00, flat 15:55, first per day.

| Cell | N | Mean R | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| NQ · A reversal · next-swing target | 410 | **−0.00** | −0.02 | −0.03 | **+0.09** | −0.08 |
| NQ · A reversal · 2R | 410 | −0.02 | −0.03 | −0.04 | +0.06 | −0.10 |
| ES · A reversal · 2R | 381 | −0.02 | −0.07 | +0.04 | −0.01 | −0.08 |
| ES · A reversal · next swing | 381 | −0.04 | | | | |
| NQ · B continuation · 2R | 52 | −0.15 | +0.30 | −0.22 | −0.51 | −0.32 |
| ES · B continuation · 2R | 44 | −0.02 | +0.15 | +0.06 | −0.30 | −0.14 |

**Verdict `NO_EDGE`, but the closest to break-even of all phases.** The
15-minute structure gives wide stops (NQ median ≈ 100–200 pts), so costs take
a much smaller bite. Continuation trades are rare (~15 a year) and negative in
2025–26.

## Phase 112: the user's trade management on every strategy

Plans: FIXED · HALF (half at 1R) · CUT (out at minute 15 if never +0.5R) · RUN
(breakeven at +1R, then trail 1R, no target) · CUT_RUN · HALF_CUT. For each
strategy the plan is **chosen on 2023–24**, and only its **2025–26** result counts.

| Strategy | Chosen plan | 2025–26 | 2025 | 2026 | Range of all plans in 2025–26 |
|---|---|---|---|---|---|
| NQ IFVG model (Ph107) | HALF_CUT | **+0.02R** | +0.07 | −0.03 | +0.02 … +0.08 |
| NQ TJR 15m reversal (Ph111) | CUT | **+0.01R** | +0.06 | −0.06 | −0.01 … +0.01 |
| NQ fade the sweep (Ph104) | FIXED | −0.04R | −0.05 | −0.02 | −0.04 … +0.08 |
| NQ pullback IFVG, morning (Ph108b) | RUN | −0.04R | −0.08 | +0.03 | −0.07 … −0.03 |
| NQ follow + 1h (Ph106) | FIXED | −0.11R | −0.21 | +0.00 | −0.12 … −0.02 |
| ES (all strategies) | | −0.03 … −0.17R | | | |

**Verdict: management changes results by only about ±0.05R and doesn't make
any strategy reliably profitable.** On NQ's IFVG model every plan was positive
in 2025–26 after all were negative in 2023–24: a change in how NQ behaved, not
proof of an edge.
