# Phase 91 — Magnitude Economic Divergence & Cross-Instrument Attribution

**Status: COMPLETE.** No new directional signal, no parameter optimization,
no live-execution artifact.

## 1. Executive Summary

Phase 90's `RISK_MANAGEMENT_EDGE_PROMISING` result was positive on 3 of 6
instruments (GBPJPY, AUDJPY, USDJPY) and negative on the other 3 (EURUSD,
GBPUSD, XAUUSD) — an inversion of Phase 89's own predictive-strength
ranking. This phase attributes that gap, without reopening prediction or
direction, to a specific, quantified mechanism in the decision-
transformation layer: the eligibility filter (not the sizing rule) drives
essentially all of the positive contribution, the sizing rule is
mildly-to-materially harmful on its own for 5 of 6 instruments, and the
divergence in *net* sign is explained by two things acting together — how
strongly a fixed-direction bet's realized return co-moves with predicted
magnitude (corr(T1,T2), materially more negative for the three
economically-positive instruments), and the size of each instrument's own
baseline "always long" drag, which the filter's improvement must
overcome. **Final verdict: `ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED`** —
a credible, quantified mechanism was found and corroborates a clean
quote-currency correlate, but per-instrument fold-level consistency is
imperfect, so the explanation is not complete.

## 2. Phase-90 Baseline

`RISK_MANAGEMENT_EDGE_PROMISING`. Pooled A2−A1 expectancy delta positive
in all 3 walk-forward folds (+0.00447/+0.00188/+0.00022), cost-stable
(BASE/ADVERSE/SEVERE ≈ +0.0022 throughout), placebo-separated (~6.4×). Per
instrument: GBPJPY +0.01145, AUDJPY +0.00412, USDJPY +0.00102 positive;
EURUSD −0.00044, XAUUSD −0.00369, GBPUSD −0.01146 negative.

## 3. Research Question

Why does the magnitude signal appear predictive across all six
instruments (Phase 89), while its risk-management economic utility
(Phase 90) is positive on only three — and why do those three not
coincide with the strongest predictors?

## 4. Repository State

`HEAD == origin/main == 5728155` confirmed before any change. Working
tree clean, 1954 passed / 6 skipped / 0 failed, holdout untouched, Gold
contract unchanged, live automation disabled, broker transmission
blocked.

## 5. Data and Scope

Same 6 canonical instruments, 15m, horizon 4. No new data. All analysis
reuses Phase 89/90's frozen dataset builders, baseline, targets, cost
model, and walk-forward folds unchanged.

## 6. Phase-90 Result Reconstruction

Reconstructed directly from the persisted `phase90_magnitude_risk_
management` artifact (never recomputed): the 3-positive/3-negative split
is confirmed exactly as reported, per-fold pooled deltas match, and the
placebo/cost-sensitivity figures match Phase 90's own report to the
decimal.

## 7. Cross-Instrument Comparison

| Instrument | ΔR² (Phase 89) | Economic Δ (Phase 89→90) | corr(volume_rank, T2) | corr(T1, T2) | Movement/Cost |
|---|---:|---:|---:|---:|---:|
| GBPJPY | 0.0077 | **+0.01145** | 0.395 | **−0.170** | 19.93 |
| AUDJPY | 0.0022 | **+0.00412** | 0.342 | **−0.161** | 20.10 |
| USDJPY | 0.0152 | **+0.00102** | 0.391 | **−0.183** | 21.61 |
| EURUSD | 0.0538 | −0.00044 | 0.592 | −0.014 | 21.04 |
| GBPUSD | 0.0307 | −0.01146 | 0.541 | −0.020 | 20.83 |
| XAUUSD | 0.0136 | −0.00369 | 0.523 | −0.024 | 21.40 |

Movement/cost ratio is essentially flat across all 6 instruments (19.9–21.6)
— H1 (cost-structure divergence) is **not** the explanation.

## 8. Predictive vs Economic Strength

Spearman ρ(ΔR², economic Δ) = **−0.657** (p=0.156, N=6 — descriptive
only, not a confirmatory test). More strikingly, `corr(volume_rank, T2)`
shows a **perfect, non-overlapping separation**: every economically-
negative instrument (0.52–0.59) exceeds every economically-positive
instrument (0.34–0.40). **Stronger raw predictive correlation is
associated with worse economic outcome under this specific risk-
management transformation** — predictive accuracy and economic
usefulness are empirically different properties here, exactly the
possibility Sec.18 asked to be tested honestly.

## 9. Cost Attribution

A1 and A2 remove a similar count of trades via their respective quartile
filters (46,157 vs. 44,259 out of 179,861) and apply the same [0.5×,1.5×]
size cap (mean size 0.878 vs. 0.882) — both systems bear a broadly similar
aggregate cost burden. This is *why* the BASE/ADVERSE/SEVERE cost sweep
barely moved the A2−A1 delta (Phase 90 §16): the comparison is between
two similarly-costed systems, so cost stress cancels in the difference.
This was disclosed as a limitation in Phase 90 and is confirmed
mechanically here, not overturned.

## 10. Baseline Interaction

Each instrument's fixed "always long" baseline (A0) has a different
structural drag: EURUSD −0.048R, GBPUSD −0.058R (largest), USDJPY −0.034R,
GBPJPY −0.043R, AUDJPY −0.039R, XAUUSD −0.018R (smallest, reflecting its
strong secular uptrend, mean T1 = +0.041 — 4–10× larger than the other
five instruments' own drift).

## 11. Sizing Attribution

Isolating the inverse/volatility-targeting sizing rule alone (no filter):
it **worsens** expectancy relative to baseline A0 on 5 of 6 instruments
(GBPJPY −0.063 vs −0.043; AUDJPY −0.060 vs −0.039; USDJPY −0.041 vs
−0.034; EURUSD −0.053 vs −0.048; GBPUSD −0.068 vs −0.058) and only
marginally helps XAUUSD (−0.016 vs −0.018). **Sizing alone is not the
source of Phase 90's benefit anywhere** — a materially different and more
precise finding than assuming the combined treatment's benefit came from
sizing.

## 12. Eligibility Attribution

Isolating the bottom-quartile eligibility filter alone (no sizing): it
**improves** expectancy relative to A0 on 5 of 6 instruments (GBPJPY
−0.043→+0.006; AUDJPY −0.039→+0.010; USDJPY −0.034→−0.013; EURUSD
−0.048→−0.043; GBPUSD −0.058→−0.050) and is the **sole exception at
XAUUSD**, where it makes things worse (−0.018→−0.026) — plausibly because
XAUUSD's low-predicted-magnitude periods are not disproportionately bad
for its strong uptrend, so excluding them removes genuinely fine trades.
**The eligibility filter, not sizing, is responsible for essentially all
of Phase 90's positive economic contribution.** The combined system (C,
matching Phase 90's literal design) tracks the filter-only result closely
everywhere.

## 13. Target/Stop Geometry

Phase 90 has no explicit price-level stop/target (no path-dependent
simulator exists in the 76-91 lineage) — the relevant "geometry" is the
relationship between the realized directional outcome (T1) and the
predicted magnitude (T2) under the fixed direction. `corr(T1,T2)` is
materially more negative for the three economically-positive instruments
(mean −0.171) than the three negative ones (mean −0.019) — an 8.8×
difference. This is the core geometric/mechanistic finding: where large
predicted magnitude co-occurs with an adverse move for "always long," the
risk-management layer's exclusions (and to a lesser extent its sizing)
are hitting genuinely bad opportunities; where magnitude is closer to
direction-neutral, they are not.

## 14. Session Attribution

Both instrument groups show a broadly similar session shape (LATE_US and
NEW_YORK favorable, LONDON unfavorable, TOKYO small), but the
positive-effect group's magnitudes are consistently larger in the same
direction (e.g. LATE_US: +0.085 positive-group vs. +0.022 negative-group)
and NEW_YORK is a clear divergence point (+0.037 vs. −0.005). Session is
not an independent explanation — it appears to track the same underlying
instrument-group difference rather than adding a separate mechanism.

## 15. Temporal Attribution

Per-instrument, per-fold sign consistency (3 walk-forward folds):

| Instrument | Folds positive | All same sign? |
|---|---|---|
| GBPJPY | 3/3 | **Yes** |
| EURUSD | 0/3 | **Yes** (consistently negative) |
| AUDJPY | 2/3 | No |
| GBPUSD | 2/3 | No |
| USDJPY | 1/3 | No |
| XAUUSD | 1/3 | No |

Only GBPJPY and EURUSD are *perfectly* consistent across every fold; the
other four show mixed signs fold-to-fold even though their pooled sign
matches their group. This imperfect consistency is the specific reason
the verdict is `PARTIALLY_EXPLAINED` rather than fully `EXPLAINED`.

## 16. Trade-Count Attribution

A0: 179,861 opportunities. A1 filter: 133,704 eligible (46,157 removed).
A2 filter: 135,602 eligible (44,259 removed) — a similar count, confirming
§9's cost-symmetry finding structurally, not just via cost proxy.

## 17. Risk Attribution

Pooled: A0 max drawdown −7,342R; filter-only −2,801R (a large, genuine
improvement); sizing-only −9,167R (**worse** than baseline); combined
−2,732R (best, tracking filter-only closely). The drawdown improvement is
overwhelmingly a **filter/selection effect** (avoiding a subset of bad
opportunities), not a sizing/exposure-reduction effect — sizing alone
increases drawdown, it does not reduce it, in pooled terms.

## 18. Placebo

Reused Phase 90's exact placebo architecture, split by instrument group:
positive-group placebo deltas (−0.00091, −0.00051, −0.00011) and
negative-group placebo deltas (+0.00126, +0.00020, +0.00003) are both
small relative to their respective real pooled effects (+0.01 range for
GBPJPY, −0.01 range for GBPUSD) — the real effect is clearly separated
from placebo noise in **both** groups, not just the pooled result.

## 19. Information → Decision → Economic Chain

**Information value** (Layer 1): intact and roughly comparable/somewhat
stronger for the negative-effect instruments (higher `corr(volume_rank,
T2)`). **Decision value** (Layer 2, the eligibility filter specifically):
positive for 5 of 6 instruments — the filter genuinely identifies less-
favorable-to-exclude opportunities almost everywhere. **Economic value**
(Layer 3, net sign): only crosses into positive territory where the
filter's real improvement is large enough to overcome that instrument's
own baseline drag (smaller baseline drag + genuine filter improvement =
net positive, as for USDJPY/GBPJPY/AUDJPY) — for EURUSD/GBPUSD the filter
still helps but not enough to overcome larger baseline drag; for XAUUSD
the filter itself is the one clear exception (mechanism, not magnitude,
breaks down there). **The chain breaks primarily at the size of Layer 2's
improvement relative to each instrument's own Layer-0 baseline drag, and
in XAUUSD's case, at Layer 2 itself.**

## 20. Structural Interpretation

The 3/3 split maps exactly onto quote currency: all three economically-
positive instruments are JPY-quoted; none of the three negative ones are.
This is reported as a clean, independently-verified **structural
correlate**, not asserted as the causal mechanism — the actual
quantitative driver identified is the T1-T2 correlation asymmetry (§13),
which happens to align with this grouping in the tested sample. Whether
JPY-quote convention itself has a causal role (e.g., via this broker's
own JPY-pair tick/pricing construction) is not established by anything in
this repository.

## 21. Limitations

1. N=6 throughout — every cross-instrument statistic here is descriptive
   attribution, not a confirmatory hypothesis test (Spearman p=0.156 is
   explicitly non-significant and not treated as decisive).
2. Fold-level consistency is imperfect for 4 of 6 instruments (§15) —
   the pooled group split is real but not iron-clad period-by-period.
3. XAUUSD's own large secular drift (+0.041 mean T1) may itself be a
   sample-period artifact (a multi-year gold bull market within this
   specific window) rather than a structural property of gold as an
   instrument — not verifiable from this data alone.
4. No causal test of the quote-currency hypothesis (e.g., comparing this
   broker's JPY-pair construction against another feed) was performed —
   correctly out of scope (no paid data, no new acquisition).

## 22. Final Verdict

**`ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED`**

## 23. What Has Been Proven

- The eligibility filter, not the sizing rule, drives essentially all of
  Phase 90's positive economic contribution (§11-12, §17) — a materially
  more precise attribution than treating the combined treatment as one
  undifferentiated layer.
- The sizing rule alone is mildly-to-materially harmful on 5 of 6
  instruments in isolation.
- A quantified mechanism (corr(T1,T2) asymmetry) separates the two groups
  by a large margin (−0.171 vs. −0.019 mean).
- Predictive strength (`corr(volume_rank,T2)`) is *inversely*, and
  perfectly rank-separated, related to economic benefit in this sample.
- The economic placebo separates cleanly from noise in both instrument
  groups independently, not only pooled.

## 24. What Has NOT Been Proven

- **Directional prediction**: unchanged, still `NOT FOUND`.
- **Economic utility as a settled, universal property**: explicitly
  contradicted — it is instrument-dependent and only partially explained.
- **Instrument selection as a solution**: not concluded — this phase
  establishes *why* the split exists, not that only GBPJPY/AUDJPY/USDJPY
  should ever be used; XAUUSD's filter-specific failure mode in
  particular deserves its own investigation before any such conclusion.
- **Production readiness**: unchanged from Phase 90 — still no.

## 25. Recommended Next Phase

Investigate the eligibility filter in isolation as its own, simpler
risk-management layer (dropping the sizing component entirely, since it
was shown here to be net-harmful on 5 of 6 instruments) — a smaller,
more precisely targeted follow-up than re-testing the full combined
Phase 90 design, directly motivated by §11-12's decomposition rather than
a new hypothesis.
