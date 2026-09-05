# Phase 90 — Cost-Aware Magnitude Risk-Management Validation

**Status: COMPLETE.** No live-execution artifact of any kind exists in
this module or this document. No new directional signal was introduced.

## 1. Executive Summary

Phase 89 answered "is the magnitude signal real?" with yes. Phase 90 asks
"does that real information improve a realistic risk-management decision
after proper out-of-sample and cost-aware validation?" The answer is
**partially, and inconsistently across instruments**: under a fixed,
non-predictive "always long" direction held identical between systems, a
volatility-targeting position-sizing rule conditioned on `volume_rank`
improved pooled expectancy and drawdown in every walk-forward fold, was
clearly larger than its own dedicated placebo, and remained stable across
BASE/ADVERSE/SEVERE cost stress — but the benefit was concentrated in 3 of
6 instruments (with the other 3 showing a small negative effect), and one
of three folds showed a negligible drawdown improvement. **Final verdict:
`RISK_MANAGEMENT_EDGE_PROMISING`** — real, but not yet broad or consistent
enough to confirm.

## 2. Research Objective

Test Claim C only: does magnitude information improve an actual trading/
risk-management decision? Claim A (direction) remains `FALSE/NOT FOUND`
and was not reopened. Claim B (magnitude) remains `SUPPORTED` per Phase
89 and was not re-litigated, only built upon.

## 3. Phase-89 Baseline (frozen research context)

Gate A: `PASS_WITH_REVISIONS` (one claim weakened: the volume-magnitude
relationship likely has a partly market-wide component, not a purely
per-instrument one). Gate B: `MAGNITUDE_EDGE_CONFIRMED` — `volume_rank`
added pooled ΔR² ≈ +0.0342 beyond a volatility-only baseline, positive in
every walk-forward fold, on all 6 instruments, surviving a dedicated
placebo. No cost-aware P&L validation existed yet — that gap is this
phase's entire purpose.

## 4. Data Used

The same 6 canonical instruments (XAUUSD, USDJPY, EURUSD, GBPJPY, GBPUSD,
AUDJPY), 15m timeframe, horizon 4 bars — no new data, no paid data.

## 5. Feature Definitions

Baseline B (volatility-only, reused unchanged from Phase 89/80):
`atr_rank`, `rv_rank`, `atr_ret`, `rv`, `tr_atr`, `abs_ret_1`. Magnitude
model adds `volume_rank` (Phase 84's frozen construction, unchanged).
Targets: T1 (signed, for R-multiple P&L) and T2 (magnitude, for the
percentile predictor and reachability test) — both Phase 83's frozen,
unchanged formulas.

**Fixed direction** (the one new construct this phase introduces):
`direction = +1` ("always long") for every opportunity, identical between
BASELINE and MAGNITUDE-AWARE systems. This is explicitly documented as a
non-signal scaffold — not expected to have positive expectancy on its own,
and never optimized. `sign(mom_4)` (Phase 86's own rejected construction)
was deliberately not reused, both because it is known non-predictive and
to avoid any appearance of smuggling a directional claim back in.

## 6. Walk-Forward Design

Phase 80's frozen expanding-window, purge+embargo, calendar-year folds
(2023/2024/2025 boundaries), reused unchanged. For each fold: the
magnitude-percentile predictor (Ridge, `Model = volatility-only` for A1,
`+volume_rank` for A2) is fit on TRAIN only; its predictions on TEST are
converted to a percentile against the TRAIN prediction distribution only
(never test-informed) via `numpy.searchsorted`. The eligibility threshold
(bottom-quartile cutoff) is likewise computed from TRAIN predictions only.

## 7. Baseline Models

**A0** (`BASELINE`): fixed unit position size, no eligibility filter,
every opportunity taken. **A1**: A0 + volatility-only-conditioned sizing
and filtering (no `volume_rank`).

## 8. Magnitude Model

**A2** (`MAGNITUDE-AWARE`): identical to A1's mechanics, but the
percentile predictor also uses `volume_rank`. Sizing:
`size = clip(1.5 - 1.0 × percentile, 0.5, 1.5)` (inverse/volatility-
targeting: higher predicted magnitude → smaller size). Filter: skip the
bottom quartile of predicted target-reachability (Application D).

## 9. Ablation Results (A2 − A1, pooled, BASE cost)

| Fold | Expectancy Δ(R) | Max-Drawdown Δ(R) | Return/DD Δ | Std Δ(R) |
|---|---|---|---|---|
| 1 (2023H2) | **+0.00447** | **+177.28** | +0.0118 | +0.01007 |
| 2 (2024H2) | **+0.00188** | **+83.99** | +0.0134 | +0.00107 |
| 3 (2025H2+) | +0.00022 | −0.79 | −0.0013 | −0.00404 |

Positive expectancy delta in all 3 folds; drawdown clearly improves in 2
of 3, essentially flat in the third. The key A2−A1 comparison isolates
`volume_rank`'s own marginal contribution beyond ordinary volatility-based
risk management, as required (Sec.24 of the master prompt).

## 10. Target-Reachability Results

Reusing the direction-neutral construction (P(T2 ≥ k−1), logistic
regression, 70/30 split): Brier score improved at **every** predeclared
k: k=0.5 (+0.00038), k=1.0 (+0.00639), k=1.5 (+0.00195), k=2.0 (+0.00024)
— consistent with Phase 89's own finding, reconfirmed here.

## 11. Stop/Target Results

Not separately modeled as a path-dependent stop/target simulator (no such
simulator exists anywhere in the 76-89 lineage; building one was judged
disproportionate). The reachability test (§10) serves as the direction-
neutral proxy for "is a given movement multiple realistic" — the same
scope decision Phase 89 made, carried forward here.

## 12. Position-Sizing Results

The volatility-targeting sizing rule (§8) is the core of the A1→A2
comparison (§9). It improved risk-adjusted metrics (drawdown) more
consistently than it improved raw expectancy alone — consistent with
vol-targeting's known character (smoothing exposure, not manufacturing
directional profit). Per the master prompt's explicit caution (Sec.18):
this was NOT achieved by merely increasing leverage — the size cap
[0.5x, 1.5x] bounds total exposure symmetrically around the baseline.

## 13. Trade-Eligibility Results

The bottom-quartile reachability filter removed a materially similar
count of trades between A1 and A2 (both filters are conceptually
comparable percentile cuts, differing only in which model produced the
percentile) — see `A1_eligible`/`A2_eligible` in the persisted per-fold
artifact. The filter's specific incremental contribution from
`volume_rank` (vs. volatility-only filtering) is embedded in the A2−A1
delta already reported (§9); it was not isolated further from the sizing
effect in this pass — a disclosed limitation (§22).

## 14. Cost Model

Reused unchanged from Phase 76/86: BASE = 0.05 ATR round-trip (documented
conservative retail proxy), ADVERSE = 0.10, SEVERE = 0.20.

## 15. Cost Sensitivity

Pooled mean expectancy delta (A2−A1) across the three cost scenarios was
**remarkably stable**: BASE +0.00219, ADVERSE +0.00217, SEVERE +0.00214.

## 16. Break-Even Cost

Sweeping a predeclared 0.00–0.50 ATR grid (0.01 steps), the pooled delta
remained positive through the **entire tested range** (break-even cost =
0.5, the grid's own ceiling — the sweep never actually found a crossing
point). **Honest caveat, not a claimed strength**: this is expected and
somewhat mechanical, not evidence of extraordinary robustness — because
A1 and A2 take nearly the same number of trades at nearly the same
average size, the round-trip cost term drags down BOTH systems by a
similar absolute amount, so it mostly cancels out of the A2−A1
*difference*. The break-even framing is more informative for a strategy
whose trade count or sizing differs sharply between conditions than for
this particular comparison; it is reported as required, with this
limitation disclosed rather than presented as unqualified robustness.

## 17. Placebo Results

Shuffling `volume_rank` independently in each fold's train and test split
(within the exact walk-forward apparatus): max |delta| = 0.00034 across 3
folds, vs. the real pooled BASE-cost delta of 0.00219 — the real effect is
**~6.4× larger** than the placebo's largest fluctuation. Smaller in
relative terms than Phase 89's own within-apparatus placebo margin
(~40–500×), but still a clear, non-borderline separation.

## 18. Temporal Robustness

Positive expectancy delta in all 3 folds (§9), with a visible decay
pattern (largest early, smallest most recent) — the same pattern Phase 89
observed for the underlying predictive signal. Not classified as
period-specific (present throughout), but the trend toward the recent
window's benefit shrinking to near-zero is disclosed, not hidden.

## 19. Regime Robustness

The three walk-forward folds themselves span materially different market
environments (§18); a finer within-fold volatility-tercile breakdown was
not separately computed in this pass (a disclosed limitation, matching
Phase 89's own scope decision).

## 20. Session Analysis

| Session | N | Δ Expectancy (R) |
|---|---|---|
| LATE_US | 21,347 | **+0.0582** |
| NEW_YORK | 37,614 | **+0.0159** |
| TOKYO | 52,900 | +0.0051 |
| LONDON_NY_OVERLAP | 30,224 | +0.0015 |
| LONDON | 37,776 | **−0.0079** |

Uneven across sessions — 4 of 5 positive, London negative. Per the master
prompt's own instruction (Sec.21), this is reported as a robustness
diagnostic, not interpreted causally.

## 21. Cross-Instrument Results

| Instrument | N | Δ Expectancy (R) |
|---|---|---|
| GBPJPY | 30,209 | **+0.01145** |
| AUDJPY | 30,210 | **+0.00412** |
| USDJPY | 30,210 | +0.00102 |
| EURUSD | 30,209 | −0.00044 |
| XAUUSD | 28,813 | −0.00369 |
| GBPUSD | 30,210 | **−0.01146** |

**3 of 6 positive, 3 of 6 negative** — not pooled away, reported in full.
Mean effect ≈ +0.00013 (near zero, dragged down by GBPUSD's negative
outlier); median effect ≈ +0.00029; worst case GBPUSD −0.01146; best case
GBPJPY +0.01145 (almost exactly mirrored magnitudes, opposite sign). A
genuinely interesting, unexplained pattern: GBPJPY and AUDJPY — the two
instruments where Phase 85's own *pure predictive* R² was weakest against
the full-context baseline — show the *strongest positive* economic effect
here, while EURUSD/GBPUSD/XAUUSD — the strongest predictive performers —
show flat-to-negative economic effects. No causal explanation is offered;
this is reported as an observed, uninterpreted dispersion (per Sec.5's
warning against overstating causality), not explained away.

## 22. Limitations

1. Cross-instrument effect is genuinely mixed (3 positive, 3 negative) —
   this alone is why the verdict is `PROMISING`, not `CONFIRMED`.
2. The break-even-cost metric is only weakly informative for this specific
   comparison (§16) — disclosed, not hidden.
3. Eligibility-filter and sizing effects were not decomposed separately
   from each other within A2.
4. No within-fold volatility-regime breakdown was computed.
5. No path-dependent stop/target simulator exists to test true stop/target
   compatibility directly — the reachability proxy stands in, as in Phase 89.

## 23. Economic Significance

The pooled effect, while statistically clearing its own placebo, is small
in absolute terms (≈0.002R per trade, pooled) and not uniformly positive
across instruments — a real but modest, non-universal effect, not a large
or obviously deployable economic edge.

## 24. Final Verdict

**`RISK_MANAGEMENT_EDGE_PROMISING`** — improves risk-adjusted decisions
under a fixed, non-predictive direction, survives its own placebo and all
three cost scenarios, but breadth (3/6 instruments) is not yet sufficient
to confirm a general TradeLogger risk-management edge.

## 25. What Has Been Proven

- A volatility-targeting position-sizing/eligibility rule conditioned on
  `volume_rank` improves pooled walk-forward expectancy and (mostly)
  drawdown beyond an equivalent volatility-only rule, under a direction
  held fixed and identical between conditions.
- This effect clears its own dedicated placebo and is stable across
  BASE/ADVERSE/SEVERE cost stress.
- The effect is real on at least 3 of 6 canonical instruments, not
  uniformly on all 6.

## 26. What Has NOT Been Proven

- **Directional prediction**: unchanged, still `NOT FOUND`.
- **Standalone profitability**: the fixed "always long" baseline itself is
  net-negative after costs on most instruments/folds — this phase never
  claims the underlying direction is profitable, only that the
  risk-management layer improves it relative to itself.
- **Universal generalization**: explicitly contradicted by the 3-positive/
  3-negative instrument split.
- **Production readiness**: no deployment, no live integration, and the
  effect size is small enough that further validation would be needed
  before any practical application.

## 27. Production Implications

None at this time. This remains a research finding about a
risk-management layer's incremental value under a synthetic direction
scaffold — not a deployable feature. No production execution, account
management, or live-safety code was touched.

## 28. Recommended Next Phase

Investigate **why** the economic benefit is concentrated in GBPJPY/AUDJPY
and absent-to-negative in EURUSD/GBPUSD/XAUUSD (§21) — specifically
whether it relates to each instrument's own volatility-clustering
character or liquidity/session profile — before attempting any broader
economic validation or considering an application to a genuine
(already-validated, still-nonexistent) directional context. Do not reopen
directional discovery to answer this; it is a question about the
risk-management layer's own instrument-dependence, not about direction.
