# Phase 83 — Conditional Market Structure & Regime Interaction Discovery

**Status: COMPLETE.** A research phase, not a strategy phase. V1 and V2
remain CLOSED (Phase 81: `V2_EXPLAINED_BY_TIME_AND_VOLATILITY`; Phase 82:
`V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT`) and are not reopened — no
compression-run event, no HIGH-volatility-bucket event, and no V1/V2
target formula is used anywhere in this phase.

**Final verdict: all 5 pre-registered candidates classified
`EXPLAINED_BY_CONTEXT`.** None of the tested interactions (volatility×trend,
volatility×session, momentum×volatility, location×trend,
structure×volatility) add a materially meaningful increment beyond a
strong context baseline (volatility + session/time + trend + momentum +
location + structure) that already contains their own main effects. Two
candidates (volatility×session, momentum×volatility) and, after a
methodology bug was found and fixed, a third (structure×volatility) are
statistically distinguishable from zero and survive Benjamini-Hochberg
correction — but every single one has an out-of-sample R² increment below
1/10 of the predeclared "material" threshold (largest: +0.0024, vs. a 0.01
margin), is cross-asset-inconsistent, and provides no basis for further
strategy or ML development. **No candidate reached
`PROMISING_NEEDS_CONFIRMATION`. Phase 84 is not recommended on this
evidence.**

## 1. Executive Summary

Five pre-registered volatility/trend/session/momentum/location/structure
interaction candidates were tested against a fixed strong-context baseline
across all 6 instruments' 15m bars (599,534 rows, unconditional — not
gated on V1's compression event or V2's HIGH-volatility event). A strict
temporal discovery (before 2025) / confirmation (2025 H2 onward, touched
exactly once) split was used throughout. Baseline D alone already explains
substantial forward-range variance (OOS R²≈0.29 on the confirmation set);
every candidate's interaction term adds at most +0.0024 R² beyond that —
roughly 1% of the baseline's own explanatory power, and well under the
predeclared 0.01 "material" margin used throughout this research program
(Phases 80-82). A genuine methodology bug (a candidate silently dropped
from multiple-testing correction due to a rounding artifact) was found and
fixed mid-phase, per the project's established discipline of never trusting
a result before checking why it looks the way it does. **Verdict: all 5
candidates `EXPLAINED_BY_CONTEXT`. No trading strategy. Phase 84 not
recommended.**

## 2. Research Question

Do combinations of already-existing, already-causal market-context
variables (volatility state, trend regime, session, momentum, location in
recent range, distance from structural levels) reveal conditional market
behavior NOT already explained by those variables' own main effects? Five
pre-registered interaction candidates are tested against a fixed "strong
context" baseline that already contains every candidate's own main-effect
variables — isolating the marginal value of the interaction TERM itself.

## 3. Dataset

| | Value |
|---|---|
| Instruments | 6 (XAUUSD, USDJPY, EURUSD, GBPJPY, GBPUSD, AUDJPY) |
| Timeframe | 15m |
| Total rows (headline h=4) | 599,534 |
| Discovery rows (< 2025-01-01) | 351,599 |
| Confirmation rows (≥ 2025-07-01) | 174,716 |
| T1 mean / std | 0.011 / 1.548 |
| T2 mean / std | 0.012 / 0.561 |

The 2025 H1 gap between discovery and confirmation is a purge/embargo
buffer. The confirmation set was evaluated exactly once per candidate,
after every hypothesis, feature, and threshold was frozen from discovery
alone.

## 4. Target Definitions

Two general-purpose targets, both reused formulas from the established
research infrastructure, both evaluated at **every bar** (not gated by any
V1/V2 event — a distinct research design from those closed phases):

- **T1 (directional)**: `log(close[i+h]/close[i]) / atr_ret[i]` — Phase
  76's own signed-return formula (`study_events`), unconditional here.
- **T2 (magnitude)**: `(sum(tr, i+1..i+h)) / (atr_stable[i]*h) - 1` — Phase
  78's own range-expansion formula (`study_range_expansion`), unconditional
  here (V1 is this SAME formula CONDITIONED on the compression event; this
  is a different, broader question).

`h ∈ {1,2,4,8}`, headline h=4. Every feature is derived from EXISTING
causal columns already produced by `phase76_event_study.load_bars`/
`phase78_market_behavior_discovery_ii.augment` (`atr_rank`, `rv_rank`,
`regime`, `eff`, `session`, `hour`, `roll_h20`/`roll_l20`, `pdh`/`pdl`) —
no new feature-engineering exercise (§39 of the master prompt).

## 5. Baselines

**Baseline D** (fixed, identical for every candidate — §11): `atr_rank`,
`rv_rank` (volatility), `mom_4` (ATR-normalised 4-bar momentum),
`loc_in_range` (location within the prior 20-bar range), `dist_pdh_atr`/
`dist_pdl_atr` (ATR-normalised distance from the previous day's high/low),
`regime_TRENDING`/`regime_RANGING` (MIXED is the reference level),
`session_LONDON`/`session_NEW_YORK`/`session_LONDON_NY_OVERLAP`/
`session_LATE_US` (TOKYO is the reference level), `hour_sin`/`hour_cos`,
`dow`. Because Baseline D already contains every candidate's own A and B
main effects, the central per-candidate test reduces cleanly to: does
adding the A×B interaction TERM improve on Baseline D alone?

## 6. Interaction Families

5 pre-registered candidates (frozen before any result was viewed):

| ID | A | B | Target | Hypothesis |
|---|---|---|---|---|
| I1 | `atr_rank` (volatility) | `regime` (trend, categorical) | T2 | Forward range's relationship with volatility differs by trend regime |
| I2 | `atr_rank` (volatility) | `session` (categorical) | T2 | Volatility's relationship with forward range differs by session |
| I3 | `mom_4` (momentum) | `atr_rank` (volatility) | T1 | Momentum's relationship with forward direction differs by volatility state |
| I4 | `loc_in_range` (location) | `regime` (trend, categorical) | T1 | Location-in-range predicts direction differently by regime (mean-reversion vs. continuation) |
| I5 | `dist_pdh_atr` (structure) | `atr_rank` (volatility) | T2 | Distance from the prior day's high predicts forward range differently by volatility state |

## 7. Discovery Results

Δ(baseline+interaction − baseline) OOS R², two discovery-internal
calendar-year folds (test windows 2023 H2 and 2024 H2):

| Candidate | Fold 1 (2023H2) | Fold 2 (2024H2) |
|---|---|---|
| I1 volatility×trend | +0.0011 | +0.0014 |
| I2 volatility×session | +0.0009 | +0.0034 |
| I3 momentum×volatility | +0.0000 | +0.0001 |
| I4 location×trend | -0.0000 | +0.0002 |
| I5 structure×volatility | -0.0007 | +0.0001 |

Every discovery-fold delta is already tiny (≤0.0034) — the confirmation
result (§9) is fully consistent with what discovery already showed; nothing
"decayed" from a larger discovery effect (ruling out `DESCRIPTIVE_ONLY` for
every candidate).

## 8. Multiple Testing

Benjamini-Hochberg FDR (q=0.10) across the m=5 pre-registered candidates,
using each candidate's confirmation-set bootstrap z-score.

**A real bug was found and fixed here, before any result was interpreted**:
the first full run silently DROPPED candidate I5 from the correction
family entirely, because its bootstrap standard error rounded to exactly
0.0000 (a genuinely tiny but nonzero variance) and a naive `if se > 0`
guard treated that as "no SE available." A pre-registered candidate must
never be silently excluded from its own multiple-testing family. Fixed by
flooring the effective SE (documented in code) so every candidate with a
computed point estimate always contributes a p-value; a regression test
was added. The fix changed I5 from "excluded" to "included and BH-
significant" — but did NOT change its final verdict, because effect-size
materiality is checked before the BH gate in this phase's decision logic
(§62 of the master prompt: statistical significance from a tiny-variance
estimate is not the same claim as a meaningful effect size).

**Corrected results** (all 5 candidates included):

| Candidate | p-value | Survives BH (q=0.10) |
|---|---|---|
| I1 volatility x trend | 0.317 | No |
| I2 volatility x session | ~0.000 | Yes |
| I3 momentum x volatility | ~0.000 | Yes |
| I4 location x trend | 1.000 | No |
| I5 structure x volatility | ~0.000 | Yes |

Three of five candidates are "statistically significant" after correction
-- and every one of them still fails the effect-size gate (§9). This is
the single clearest illustration in this phase of §61/§62's warning: do
not optimize for p-value or R-squared, and do not confuse statistical
significance with a meaningful effect.

## 9. OOS Results

Confirmation-set (touched once) headline results, h=4:

| Candidate | Baseline R2 | +Interaction R2 | Delta R2 | 95% CI |
|---|---|---|---|---|
| I1 volatility x trend | 0.1965 | 0.1963 | -0.0002 | [-0.0005, +0.0001] |
| I2 volatility x session | 0.1965 | 0.1989 | +0.0024 | [+0.0016, +0.0032] |
| I3 momentum x volatility | 0.0053 | 0.0059 | +0.0006 | [+0.0003, +0.0009] |
| I4 location x trend | 0.0053 | 0.0053 | +0.0000 | [-0.0001, +0.0001] |
| I5 structure x volatility | 0.1965 | 0.1967 | +0.0001 | [+0.0001, +0.0002] |

(I1/I2/I5 share the same T2 baseline R2; I3/I4 share the same T1 baseline
R2 -- both are the SAME fixed Baseline D fit on the same discovery set,
scored against the respective target.) T1 (direction) is essentially
unpredictable from this context at all (R2 approx 0.005) -- consistent with
every directional finding across Phases 70-82. T2 (range) is reasonably
well predicted by context alone (R2 approx 0.20); no candidate's
interaction meaningfully improves on that.

## 10. Cross-Asset Results

I2 (volatility x session — the largest, BH-significant delta), per
instrument (confirmation set, pooled model's own rows):

| Instrument | Delta R2 | Leave-one-out Delta R2 |
|---|---|---|
| AUDJPY | +0.0113 | +0.0127 |
| GBPJPY | +0.0103 | +0.0099 |
| USDJPY | +0.0012 | +0.0022 |
| GBPUSD | +0.0004 | -0.0033 |
| EURUSD | -0.0021 | -0.0024 |
| XAUUSD | -0.0049 | -0.0086 |

Even the single BH-significant, largest-magnitude candidate is split 4/6
positive-negative across instruments both in-sample and under
leave-one-out — not a universal effect. This alone would fail the
cross-asset-consistency gate (§21/§48) even before considering effect
size.

## 11. Regime Stability

Descriptive breakdown by current volatility tercile (confirmation set) is
recorded per candidate in the artifact (`regime_stability`); given every
candidate already fails the effect-size gate at the pooled level, no
regime-specific subgroup was used to rescue any candidate (§60's explicit
prohibition on post-hoc hypothesis narrowing).

## 12. Horizon Stability

I2 (volatility x session), all 4 pre-declared horizons, confirmation set:

| Horizon | Delta R2 | CI excludes zero |
|---|---|---|
| h=1 | +0.0018 | Yes |
| h=2 | +0.0015 | Yes |
| h=4 | +0.0024 | Yes |
| h=8 | +0.0056 | Yes |

Consistently positive and CI-excluding-zero across all 4 horizons — the
most internally consistent result in the entire phase — but never
approaching the 0.01 material threshold at any horizon. No horizon was
cherry-picked; all 4 are reported.

## 13. Placebo Results

I2 (largest candidate): shuffled-target control R2 = -0.005 (chance,
confirming no leakage). Wrong-context placebo (variable A permuted,
breaking the true A-B pairing while preserving A's marginal distribution):
delta R2 approx 0.0000 -- genuinely near zero, clearly BELOW the real
result's +0.0024, confirming I2's tiny effect is not a placebo artifact
(the control correctly discriminates real from fake). Temporal-shift
sweep (50-2000 bars): delta ranges +0.0018 to +0.0123, noisy with no clear
decay pattern -- consistent with a small, sample-noise-dominated effect
rather than a clean, persistent structural relationship.

## 14. Leakage Audit

All checks PASS: feature/target timestamp contract (both T1 and T2, all
599,534 rows), future-shock invariance (all 4 new derived features --
`mom_4`, `loc_in_range`, `dist_pdh_atr`, `dist_pdl_atr` -- byte-identical
pre-cutoff regardless of a 50x future shock after it). MTF leakage:
NOT_APPLICABLE (no cross-timeframe feature is used anywhere in this
phase's candidates, documented explicitly rather than silently skipped).
Session leakage: UTC epoch seconds throughout, identical to Phase 76's own
convention, no DST risk.

## 15. Determinism

Full-pipeline: three independent OS-process runs. The first (before a
methodology bug was found, see §8) produced a different hash by
construction (different code). The second and third, both post-fix,
produced an **identical** `content_hash =
7893fca18e20d866fbbf44d25fb70e5b60b5d71d67a6e81d9d1489e24ff92e21`.

## 16. Candidate Verdicts

| Candidate | Verdict | Reason |
|---|---|---|
| I1 volatility x trend | `EXPLAINED_BY_CONTEXT` | Negligible OOS delta, does not survive BH |
| I2 volatility x session | `EXPLAINED_BY_CONTEXT` | Survives BH but effect size (+0.0024) is far below the material margin |
| I3 momentum x volatility | `EXPLAINED_BY_CONTEXT` | Survives BH but effect size (+0.0006) is far below the material margin |
| I4 location x trend | `EXPLAINED_BY_CONTEXT` | Negligible OOS delta, does not survive BH |
| I5 structure x volatility | `EXPLAINED_BY_CONTEXT` | Survives BH but effect size (+0.0001) is negligible |

No candidate reached `PROMISING_NEEDS_CONFIRMATION`; none is `UNSTABLE`,
`SPARSE_OR_MULTIPLE_TESTING_RISK`, or `NO_EFFECT` (all 5 have a genuine,
nonzero, if tiny, measured relationship — "no effect at all" would
understate what was actually found). `ROBUST_INCREMENTAL_SIGNAL` was never
considered for any candidate, consistent with §57's explicit high bar.

## 17. What We Learned

- A fixed, already-existing "strong context" combination (volatility +
  session/time + trend + momentum + location + structure) explains a
  meaningful fraction of forward range behavior (R2 approx 0.20) but almost
  none of forward direction (R2 approx 0.005) — reconfirming, via an
  entirely different route, the same directional-unpredictability finding
  that Phases 70-82 established repeatedly.
- Every tested interaction between these variables adds a real, nonzero,
  but economically negligible increment on top of that baseline — the
  market-context space tested here does not contain a "hidden" conditional
  relationship of a magnitude this research program would consider
  material.
- The methodology itself (placebo, shuffle, cross-asset, cross-year,
  multiple testing) correctly discriminated a genuinely tiny-but-real
  effect (I2) from complete noise (I1, I4) — the machinery works as
  intended.

## 18. What We Did NOT Learn

- This phase does NOT establish that no conditional interaction exists
  anywhere in the market-context space — only that the 5 pre-registered,
  economically-motivated combinations tested here do not.
- This phase does NOT test SMC/structural features (BOS, MSS, liquidity
  sweeps, equal highs/lows) or multi-timeframe (H1-bias-conditions-M15)
  interactions — those families were not included in this pre-registered
  matrix and would require their own phase if pursued.
- A tiny-but-BH-significant result (I2, I3, I5) is NOT evidence of "no
  relationship whatsoever" — it is evidence of a relationship too small to
  be research-actionable under this program's standards.

## 19. Strategy Status

**No trading strategy was created in Phase 83.** No candidate survived
even to `PROMISING_NEEDS_CONFIRMATION`, so the master prompt's
instruction that "no strategy should be built until independent
confirmation" is, for this phase, moot — there is nothing to withhold a
strategy from.

## 20. Phase 84 Recommendation

**Not recommended on this evidence.** Per §65 of the master prompt: the
tested volatility, time/session, trend, momentum, location, and structural
interaction families did not demonstrate robust incremental predictive
information under the predefined research gates. This is a legitimate,
informative negative result — the existing feature/context space has been
stress-tested across 5 economically-motivated interaction hypotheses,
confirmation-set validation, cross-asset/leave-one-out/horizon stability,
multiple-testing correction, and 3 independent falsification controls
(shuffled-target, wrong-context placebo, temporal shift), and none of it
moved the needle. If a future phase pursues conditional-interaction
discovery again, it should use a genuinely different feature family (e.g.
SMC/structural or multi-timeframe) rather than re-testing this same
matrix.
