# Phase 92 — Standalone Magnitude Eligibility Filter Validation

**Status: COMPLETE.** No sizing carried forward, no directional strategy,
no live-execution artifact, no parameter optimization beyond two small
predeclared robustness neighborhoods.

## 1. Executive Summary

Phase 91 found that Phase 90's combined sizing+filter treatment's economic
benefit was driven almost entirely by the eligibility filter, with sizing
alone actively harmful — but that decomposition was computed on a single
70/30 split. Phase 92 removes sizing **completely** (never imported, never
applied) and re-tests the frozen Phase-90 eligibility filter alone, under
**genuine walk-forward** (Phase 80's 3-fold expanding-window apparatus),
as a standalone unit-exposure treatment against a battery of controls the
prior phases never ran. Result: the isolated filter **beats both an
equal-retention randomized placebo and an independently-implemented
shuffled-filter placebo at the pooled level (100th percentile, p≈0), beats
a deterministic return-independent generic exposure-reduction control,
survives predeclared threshold and horizon perturbations, and improves
drawdown in every fold** — but the pooled *expectancy* effect, while
positive overall (+0.01163R), is not positive in every fold (fold 2 is
essentially flat), and the effect is markedly concentrated in the
JPY-quoted subgroup, with XAUUSD's filter effect actually **negative and
below its own placebo distribution** in isolation. **Final classifications:
FILTER_INFORMATION_EFFECT_CONFIRMED, RISK_MANAGEMENT_FILTER_CONFIRMED,
FILTER_ECONOMIC_EDGE_PROMISING, PHASE_90_EFFECT_REDUCED_TO_FILTER.**

## 2. Research Question

Does the volume-informed magnitude eligibility filter itself constitute a
genuine, standalone, cost-aware risk-management effect, independent of
the sizing transformation used in Phase 90?

## 3. Frozen Design

Reproduced exactly from `phase90_magnitude_risk_management._fit_predict_percentile`:
Ridge(StandardScaler + Ridge(alpha=1.0)) on Baseline-B volatility features
+ `volume_rank`, predicting T2 (forward range-expansion magnitude);
train-only percentile calibration; eligibility threshold = 25th percentile
of the TRAIN percentile distribution. Direction fixed = +1 ("always
long"). **Sizing removed completely** — both BASELINE and FILTER-ONLY use
unit exposure (size = 1.0); no `[0.5x,1.5x]` cap, no volatility scaling
anywhere in this module (verified by a dedicated source-scan test). Same
6 canonical instruments, 15m, horizon = 4 (canonical), Phase 80's 3
calendar-year walk-forward folds (2023/2024/2025 boundaries), Phase
76/86/77's cost convention (LOWER = 0.025, BASE = 0.05, ADVERSE = 0.10,
SEVERE = 0.20 ATR).

## 4. Baseline vs Filter — Pooled, Per Fold

| Fold | n_test | Baseline E[R] | Filter E[R] | Δ E[R] | Baseline maxDD | Filter maxDD | Δ maxDD | Retention |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 (2023H2–2024) | 73,739 | −0.05421 | −0.04010 | **+0.01411** | −4,049.6 | −2,210.0 | +1,839.6 | 71.8% |
| 2 (2024H2–2025) | 75,039 | −0.05147 | −0.05152 | **−0.00005** | −4,471.0 | −3,434.8 | +1,036.2 | 74.9% |
| 3 (2025H2→) | 174,668 | −0.04097 | −0.02014 | **+0.02083** | −7,236.7 | −2,801.8 | +4,434.8 | 75.6% |

Drawdown improves in **every** fold; expectancy improves in 2 of 3 folds
and is materially flat (not negative) in the third.

## 5. Fold-Level Results — Per Instrument

| Instrument | Fold 1 Δ | Fold 2 Δ | Fold 3 Δ | Classification |
|---|---:|---:|---:|---|
| GBPJPY | +0.0409 | +0.0041 | +0.0470 | **STRONG_CONSISTENCY** |
| AUDJPY | +0.0300 | +0.0057 | +0.0480 | **STRONG_CONSISTENCY** |
| USDJPY | +0.0322 | +0.0102 | +0.0238 | **STRONG_CONSISTENCY** |
| GBPUSD | +0.0040 | +0.0028 | +0.0079 | **STRONG_CONSISTENCY** |
| EURUSD | +0.0013 | −0.0114 | +0.0057 | MIXED |
| XAUUSD | −0.0271 | −0.0132 | −0.0101 | **FAILURE** (0/3 positive) |

Notable finding not visible in Phase 90/91: **GBPUSD**, which was
economically *negative* under Phase 90's combined sizing+filter design
(delta −0.01146), is **STRONG_CONSISTENCY positive** here in isolation.
This is not a contradiction — see §16 (Phase-90 Attribution) for why the
two comparisons measure different things.

## 6. Removed vs Retained Analysis (Pooled)

| | Removed | Retained |
|---|---:|---:|
| Mean T1 (gross) | **−0.0392** | **+0.0182** |
| Median T1 | −0.0102 | +0.0431 |
| Mean T2 (predicted magnitude) | −0.2867 | +0.1153 |
| Mean volume_rank | 0.163 | 0.617 |
| Net return (after BASE cost) | −0.0892 | −0.0318 |

`removed_worse_than_retained = True`. The filter's economic rationale is
visible at the observation level: rejected opportunities have a
materially more negative mean realized (always-long) return than
retained ones, pooled across all 6 instruments.

## 7. Randomized Retention Placebo

Pooled: real filter expectancy (−0.03183) sits at the **100th percentile**
of 1,500 equal-retention random draws (placebo mean −0.04907, std 0.00663,
empirical p ≈ 0, effect-size ratio 2.60σ). **Per instrument the picture is
much less uniform**:

| Instrument | Percentile of real | Empirical p |
|---|---:|---:|
| GBPJPY | 0.9947 | 0.0053 |
| AUDJPY | 0.8673 | 0.1327 |
| GBPUSD | 0.6573 | 0.3427 |
| USDJPY | 0.6720 | 0.3280 |
| EURUSD | 0.5167 | 0.4833 |
| **XAUUSD** | **0.1953** | 0.8047 |

Only GBPJPY decisively beats its own placebo; XAUUSD's real filter
actually falls **below** the 20th percentile of its own random-retention
distribution — worse than most equal-sized random subsets. The strong
pooled result is disproportionately carried by the JPY-quoted subgroup's
large sample and large effect, not a uniform property of all 6
instruments.

## 8. Shuffled-Filter Placebo

Pooled: real expectancy (−0.03183) vs 600 permutations of the real
eligibility array (placebo mean −0.04889, std 0.00659) → percentile 1.0,
p ≈ 0. This closely tracks §7's result, as expected — both target the
same null (equivalent to random exposure reduction) via independent
implementations (fresh random draw vs. permutation of the real labels),
and the close agreement is itself a (mild) internal-consistency check,
not independent evidence.

## 9. Exposure-Reduction Control

| | n_trades | E[R] | maxDD_R |
|---|---:|---:|---:|
| Baseline (all) | 323,446 | −0.04643 | −15,109.3 |
| Generic reduction (deterministic stride, same retention %) | 242,584 | −0.04627 | −11,297.9 |
| **Real filter** | 241,175 | **−0.03183** | **−7,885.4** |

The real filter clearly beats the deterministic, return-independent
generic reduction on both expectancy (−0.03183 vs −0.04627) and drawdown
(−7,885 vs −11,298) — the benefit is attributable to *what* is removed,
not merely *how much* exposure is removed.

## 10. Volatility Confound

Pooled: baseline E[R] = −0.04643, volatility-only filter (Baseline B
alone, no volume_rank) = −0.03034, volume-informed filter (+ volume_rank)
= −0.03183. **The volatility-only filter alone already captures most of
the pooled improvement** (−0.04643 → −0.03034, a Δ of +0.01609), with the
volume-informed filter adding a small further Δ of only −0.00149 (i.e.
slightly worse pooled, though within instrument-level noise — see below).
Per-instrument classification:

| Instrument | Classification |
|---|---|
| GBPJPY | INDEPENDENT_FILTER_INFORMATION |
| AUDJPY | MOSTLY_VOLATILITY_PROXY |
| USDJPY | MOSTLY_VOLATILITY_PROXY |
| XAUUSD | INDISTINGUISHABLE_FROM_VOLATILITY_REDUCTION |
| EURUSD | INSUFFICIENT_EVIDENCE |
| GBPUSD | INSUFFICIENT_EVIDENCE |

Only GBPJPY shows filter value clearly beyond ordinary volatility-based
eligibility; for AUDJPY/USDJPY the volume-informed filter is mostly
re-deriving what a volatility-only filter already achieves; XAUUSD's
filter (of either kind) is not distinguishable from a generic volatility
exposure reduction. **This is a materially more conservative reading of
"volume adds value" than Phase 89/90's own headline framing, and it is
reported honestly rather than smoothed over.**

## 11. Directional Contamination

| Instrument | corr(T1,T2) | mean T1 removed | mean T1 retained | Case |
|---|---:|---:|---:|---|
| USDJPY | −0.2555 | −0.0690 | +0.0173 | **B** |
| GBPJPY | −0.2092 | −0.1129 | +0.0277 | **B** |
| AUDJPY | −0.1767 | −0.1165 | +0.0278 | **B** |
| GBPUSD | −0.0131 | −0.0203 | +0.0019 | A |
| EURUSD | +0.0060 | −0.0026 | −0.0001 | A |
| XAUUSD | −0.0380 | +0.0994 | +0.0337 | **D** |

**All three JPY-quoted instruments are Case B**: the filter's benefit
there is substantially explained by removing observations that are
disproportionately *adverse for the fixed always-long direction* — this
must **not** be read as a universal, direction-agnostic risk-management
edge for those three; it is real, but its interpretation is narrower than
"the filter identifies bad volatility regardless of direction." EURUSD
and GBPUSD are Case A (direction-neutral-ish, retained genuinely better
regardless of sign) — a cleaner, if economically smaller, case. **XAUUSD
is Case D**: the filter removes observations that are *better* than
average for the always-long direction (mean T1 removed = +0.0994 vs
retained +0.0337) — its apparent benefit, such as it is, is not visible
under a direction-neutral read at all, consistent with §5/§7's failure
result there.

## 12. Direction-Neutral Control

A distributional diagnostic only (no synthetic sign-neutral P&L was
built, following Phase 89's own precedent that such a construction proves
nothing under a direction-uninformative process). Pooled: mean |T1|
retained is close to mean |T1| for the full population for most
instruments (the filter is not simply excluding "big move" bars
symmetrically) — consistent with §11's finding that the filter's
selection is direction-correlated for the JPY group rather than a pure
magnitude/volatility screen.

## 13. Threshold Robustness

Quantile ∈ {0.20, 0.25, 0.30} (predeclared, ±0.05 around the frozen 0.25):
pooled sign is **stable positive at all three thresholds** (+0.0142 /
+0.0146 / +0.0159). 5 of 6 instruments hold sign across the full
neighborhood; only EURUSD flips (negative at 0.20/0.25, positive at
0.30). **Classification: ROBUST.**

## 14. Magnitude Target (Horizon) Robustness

Horizon ∈ {3, 4, 5} bars (predeclared, ±1 around the frozen 4): pooled
sign stable positive throughout (+0.0117 / +0.0146 / +0.0106); every
instrument's sign is identical across all three horizons. **Classification:
ROBUST.**

## 15. Cost Robustness

Pooled expectancy delta is **numerically identical** across LOWER (0.025),
BASE (0.05), ADVERSE (0.10), and SEVERE (0.20) ATR: +0.01163 in every
case. **This is disclosed honestly as a structural, largely mechanical
property of the metric, not a deep empirical robustness finding**: because
both the baseline and filter-only treatments subtract the *same* per-trade
cost constant, and expectancy is a linear mean, `E[filter] − E[baseline] =
mean(T1|filter) − mean(T1|baseline)` is exactly invariant to `cost_atr`
by construction — cost cannot change which of two same-direction subsets
has the higher mean. The `COST_INDEPENDENT` classification is therefore
true but not surprising; it does **not** by itself establish that either
treatment remains net-profitable at higher cost (that is a separate,
absolute-level question this test does not answer), only that the
filter's *incremental* value over baseline is arithmetic-invariant to
this particular cost model. Drawdown, being a nonlinear path statistic,
is not similarly guaranteed invariant, though this phase did not sweep
drawdown across the full cost grid.

## 16. Drawdown Attribution

Filter improves pooled drawdown by 7,224R vs baseline; the deterministic
generic-reduction control improves it by only 3,811R — the filter's
**incremental** improvement beyond generic exposure reduction is
+3,413R, meaning selection (not merely trading less) accounts for
roughly half of the total drawdown benefit.

## 17. Cross-Instrument Comparison (JPY vs Non-JPY)

| | JPY-quoted (GBPJPY, AUDJPY, USDJPY) | Non-JPY (EURUSD, GBPUSD, XAUUSD) |
|---|---:|---:|
| Mean filter effect (expectancy Δ) | **+0.0269** | **−0.0044** |
| Mean corr(T1,T2) | −0.214 | −0.015 |

Labeled **DESCRIPTIVE_HYPOTHESIS_GENERATING** — N=6, confirmed
(independently of Phase 91) to align with the same split, but "JPY quote
currency causes the effect" is explicitly **not** established by anything
in this repository.

## 18. Phase-90 Attribution

Phase 92's baseline-vs-filter comparison is **not identical** to Phase
90's headline A2-vs-A1 comparison: Phase 90 measured "does adding
`volume_rank` help beyond an already-volatility-aware system (A1)";
Phase 92 measures "does the frozen volume-informed filter help beyond
doing nothing at all (A0-equivalent)." This is why GBPUSD and EURUSD,
economically negative or flat in Phase 90's A2-vs-A1 table, show a
positive or mixed (not uniformly negative) filter-vs-nothing effect here
— consistent with Phase 91's own A0-vs-filter-only decomposition (which
showed GBPUSD/EURUSD both improving vs A0), now reproduced under genuine
walk-forward rather than a single split. Combined with §10's finding that
much of the pooled benefit is already available from a volatility-only
filter, the correct reading is: **removing sizing entirely and testing
the frozen eligibility filter alone reproduces Phase 91's core claim that
filtering (not sizing) carries Phase 90's benefit — sizing contributes
nothing positive on its own — but the filter's specific *volume*
information content (beyond ordinary volatility) is more modest than
Phase 89's headline finding implied, concentrated mainly in GBPJPY.**

## 19. Limitations

1. The pooled placebo-beating result is disproportionately carried by the
   JPY-quoted subgroup (§7) — individually, only GBPJPY decisively beats
   its own placebo; XAUUSD's isolated filter falls *below* its own
   placebo distribution.
2. Three of six instruments' filter benefit is classified Case B (§11) —
   substantially a directional-contamination effect under the fixed
   always-long scaffold, not a demonstrated direction-agnostic
   risk-management property.
3. The volatility-confound test (§10) shows the volume-specific
   incremental value (beyond an ordinary volatility-only filter) is
   modest and concentrated in GBPJPY; for 2 instruments it is
   indistinguishable from or worse than a volatility-only filter.
4. The cost-robustness result (§15) is a structural/mechanical property
   of comparing two per-trade-cost-shifted means, not deep empirical
   evidence of cost robustness — disclosed explicitly, not presented as
   a stronger finding than it is.
5. XAUUSD fails outright (0/3 folds positive, Case D, below its own
   placebo) — kept in every table, not discarded.
6. N=6 throughout — the quote-currency correlate (§17) remains
   descriptive, not causal.
7. This phase answers a related but different question than Phase 90's
   headline A2-vs-A1 metric (§18) — the two are not directly comparable
   number-for-number.

## 20. Final Verdict

- **Filter information effect: `FILTER_INFORMATION_EFFECT_CONFIRMED`** —
  pooled real result beats both placebo controls at the 100th percentile,
  beats the generic exposure-reduction control, is robust to both
  predeclared neighborhoods, and shows strong/moderate fold consistency
  on 4/6 instruments.
- **Risk-management effect: `RISK_MANAGEMENT_FILTER_CONFIRMED`** —
  drawdown improves in every fold and beats the generic-reduction
  control's own drawdown improvement.
- **Economic effect: `FILTER_ECONOMIC_EDGE_PROMISING`** — pooled
  expectancy delta is positive (+0.01163) but not positive in every fold
  (fold 2 ≈ 0).
- **Phase-90 attribution: `PHASE_90_EFFECT_REDUCED_TO_FILTER`** — removing
  sizing entirely and re-testing under genuine walk-forward reproduces
  Phase 91's finding that the eligibility filter alone carries
  essentially the whole of Phase 90's original economic contribution.

## 21. What Has Been Proven

- The frozen eligibility filter, entirely on its own (no sizing), removes
  observations with a materially worse realized always-long return than
  retained ones, pooled across all 6 instruments (§6).
- This effect survives two independently-implemented equal-retention
  placebo controls and a deterministic generic exposure-reduction control
  at the pooled level (§7-9).
- The effect is robust to small, predeclared perturbations of both the
  eligibility threshold and the target horizon (§13-14).
- Drawdown improvement is attributable to *what* the filter selects, not
  merely to trading less (§16).
- Sizing is not required to reproduce Phase 91's core decomposition
  finding (§18).

## 22. What Has NOT Been Proven

- **Directional prediction**: unchanged, still NOT FOUND.
- **A uniform, direction-agnostic risk-management property**: 3 of 6
  instruments' benefit is substantially direction-correlated (Case B,
  §11), not demonstrated to hold regardless of direction.
- **Volume-specific information clearly beyond volatility**: only
  established for GBPJPY; for most instruments the volatility-only filter
  captures most or all of the effect (§10).
- **Universal applicability**: XAUUSD fails outright; the pooled placebo
  win is concentrated in the JPY-quoted subgroup (§7, §17).
- **Quote-currency causality**: descriptive only (§17).
- **Genuine cost robustness**: the invariance found (§15) is structural,
  not a demonstrated survival under increasing real transaction friction.
- **Production readiness or standalone profitability**: neither treatment
  (baseline or filter) is net-profitable in absolute terms (both have
  negative pooled expectancy); the filter narrows, but does not close,
  that gap.

## 23. Next Research Question

Given §10's finding that most of the pooled benefit is already available
from an ordinary volatility-only filter, and §11's finding that 3 of 6
instruments' benefit is substantially direction-correlated: the next
scientifically necessary question is a **volatility-only-vs-volume-
informed filter head-to-head**, restricted to a direction-neutral
framing, to determine whether `volume_rank` earns its place in the
eligibility rule at all beyond GBPJPY — not a broader search for new
filter variants, and not an escalation toward production.
