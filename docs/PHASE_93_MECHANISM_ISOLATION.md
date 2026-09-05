# Phase 93 — Full Magnitude / Volatility / Volume Mechanism Isolation & Attribution

**Status: COMPLETE.** Information ablation only — no filter search, no
parameter optimization, no instrument selection, no directional strategy,
no live-execution artifact.

## Executive Summary

The Phase-92 standalone eligibility-filter effect is explained by the
**raw realized-magnitude features alone** (`atr_ret`, `rv`, `tr_atr`,
`abs_ret_1`). A magnitude-only filter not only reproduces but **exceeds**
the canonical filter's pooled walk-forward expectancy effect (+0.01883R
vs +0.01163R), generalizes **better** across instruments (5 of 6
consistent vs 4 of 6), beats its own randomized-retention placebo on more
instruments individually, and produces the **largest** drawdown
improvement of any treatment tested. Volatility-rank features alone
(`atr_rank`, `rv_rank`) explain a material but non-dominant ~55%.
**Adding `volume_rank` contributes no isolable value and is slightly-to-
materially harmful**: it degrades the magnitude-only pooled effect by
−0.00738R, is positive on only 2 of 6 instruments (both JPY-quoted), and
specifically destroys the magnitude signal on EURUSD and GBPUSD. The
minimum sufficient mechanism is **Scenario A — magnitude-only; volume is
unnecessary.** The filter mechanism itself is real (beats a generic
exposure-reduction control by a clear margin — Hypothesis E rejected),
but remains **directionally dependent** (4 of 6 instruments' benefit is
substantially "removing adverse-for-always-long observations") and only
**partially generalizes** (XAUUSD fails in every single treatment).

## Research Question

What information is *necessary and sufficient* to explain the Phase-92
standalone eligibility-filter effect — magnitude, volatility, volume,
their interaction, mere exposure reduction, or directional contamination?

## Prior Evidence

Phase 89 confirmed MT5 tick-volume as a walk-forward-validated predictor
of forward *magnitude* (not direction). Phase 90 built a combined
magnitude-prediction + sizing + eligibility treatment
(`RISK_MANAGEMENT_EDGE_PROMISING`, 3/6 instruments). Phase 91 showed
sizing was harmful and filtering carried the benefit
(`ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED`). Phase 92 removed sizing
entirely and confirmed the filter survives alone under genuine
walk-forward (`FILTER_INFORMATION_EFFECT_CONFIRMED`,
`PHASE_90_EFFECT_REDUCED_TO_FILTER`), while disclosing that an ordinary
volatility-only filter already captured most of the pooled benefit.

## Canonical Reproduction

The Phase-92 canonical result (unit-exposure baseline vs unit-exposure
frozen filter, per-fold pooled expectancy deltas +0.01411 / −0.00005 /
+0.02083) was reproduced **exactly** (max absolute difference = 0.0)
before any decomposition. Determinism confirmed (`match = True`).

## Treatment Definitions

Phase 89's frozen 6-column Baseline B is partitioned by an objective,
predeclared criterion — **percentile-rank-of-a-200-bar-window (volatility
regime) vs raw realized-movement value (magnitude)** — a split new to this
phase, disclosed as a necessary operational choice (prior phases treated
Baseline B as one atomic block):

- `MAGNITUDE_FEATURES = (atr_ret, rv, tr_atr, abs_ret_1)`
- `VOLATILITY_FEATURES = (atr_rank, rv_rank)`
- `VOLUME_FEATURES = (volume_rank)`
- `MAGNITUDE_FEATURES ∪ VOLATILITY_FEATURES == BASELINE_B_COLUMNS` exactly.

Eight treatments run through the **identical** frozen Phase-90 machinery
(Ridge on StandardScaler, train-only percentile calibration, 25th-
percentile eligibility threshold, unit exposure, direction fixed = +1,
Phase 80's 3-fold genuine walk-forward) — only the feature set varies:

| Treatment | Features | Identity |
|---|---|---|
| T0 baseline | none (no filter) | reference |
| T1 canonical | Baseline B + volume_rank | == Phase 90/92 frozen filter |
| T2 magnitude-only | atr_ret, rv, tr_atr, abs_ret_1 | new |
| T3 volatility-only | atr_rank, rv_rank | new |
| T4 volume-only | volume_rank | new |
| T5 magnitude + volume | MAGNITUDE + volume_rank | new |
| T6 magnitude + volatility | Baseline B | == Phase 92 "volatility-only filter" |
| T7 full | Baseline B + volume_rank | == T1 canonical (consistency check ✓) |

Equal-retention property: because every treatment applies the same
25th-percentile rule to its own model's percentile distribution,
per-fold retention stays in a tight ~72–76% band across all treatments —
no separate retention-matching mechanism was needed.

## Core Attribution Table

Pooled walk-forward expectancy delta (filter − baseline), BASE cost:

| Instrument | T1 canonical | T2 magnitude | T3 volatility | T4 volume | T5 mag+vol | T6 mag+volat |
|---|---:|---:|---:|---:|---:|---:|
| GBPJPY | +0.03064 | +0.02572 | +0.02143 | +0.01055 | +0.02675 | +0.02550 |
| AUDJPY | +0.02789 | +0.03213 | +0.02428 | +0.00479 | +0.02886 | +0.02960 |
| USDJPY | +0.02205 | +0.01191 | +0.01433 | +0.01596 | +0.02352 | +0.02270 |
| EURUSD | −0.00143 | **+0.01618** | −0.00178 | −0.01034 | −0.00027 | +0.00244 |
| GBPUSD | +0.00492 | **+0.02467** | +0.00826 | −0.01035 | +0.00290 | +0.01044 |
| XAUUSD | −0.01678 | −0.00533 | −0.03006 | −0.01746 | −0.01599 | −0.01820 |
| **Pooled** | **+0.01163** | **+0.01883** | **+0.00641** | **−0.00097** | **+0.01145** | **+0.01243** |

The single most important row: **EURUSD and GBPUSD, negative or flat under
every other treatment, are clearly positive under magnitude-only** and
revert to flat/negative the moment `volume_rank` is added (T5).

## Information Ablation

- E(canonical) = +0.01163; E(magnitude-only) = +0.01883;
  E(volatility-only) = +0.00641; E(volume-only) = −0.00097.
- Incremental magnitude over volatility: **+0.00522** (magnitude adds real
  value beyond volatility-rank features).
- Incremental volume over magnitude: **−0.00738** (volume *removes* value).
- Incremental volume over magnitude+volatility: **−0.0008** (negligible-
  negative).
- `canonical == full` consistency check: ✓ (both +0.01163).

**Necessary information:** the raw realized-magnitude features.
**Redundant/confounded:** the volatility-rank features add little beyond
magnitude and generalize worse (T3 pooled +0.00641, XAUUSD −0.03006).
**Harmful:** `volume_rank`.

## Incremental Volume Analysis

| Instrument | Δ vs magnitude-only | Δ vs magnitude+volatility |
|---|---:|---:|
| GBPJPY | +0.00103 | +0.00514 |
| USDJPY | +0.01161 | −0.00065 |
| AUDJPY | −0.00327 | −0.00171 |
| XAUUSD | −0.01066 | +0.00142 |
| EURUSD | −0.01645 | −0.00387 |
| GBPUSD | −0.02177 | −0.00552 |
| **Pooled** | **−0.00738** | **−0.0008** |

Volume's only material positive contribution anywhere is to USDJPY
(vs magnitude-only). It is positive on 2/6 instruments against
magnitude-only, 2/6 against magnitude+volatility. It is strongly negative
for EURUSD and GBPUSD — the exact instruments magnitude-only rescues.
**Verdict: `VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED`.**

## Volatility Confound

Volatility-only (T3) reaches ~55% of canonical's pooled effect (+0.00641
vs +0.01163) and beats its own placebo pooled (percentile 0.994), so it
is a **material but not dominant** contributor. Its cross-instrument
behaviour is worse than magnitude's: EURUSD −0.00178, GBPUSD +0.00826
(both weaker than magnitude-only), and XAUUSD −0.03006 (the single worst
cell in the entire table, placebo percentile 0.0 — worse than every
random draw). **Verdict: `VOLATILITY_EXPLANATION_PARTIAL`.**

## Placebo Battery

Pooled randomized-retention percentile (1,500 reps/treatment):

| Treatment | Pooled percentile | Real E[R] vs placebo mean |
|---|---:|---|
| T2 magnitude-only | **1.000** | −0.02600 vs −0.04906 |
| T1 canonical / T7 full | 1.000 | −0.03183 vs −0.04896 |
| T6 magnitude+volatility | 1.000 | −0.03034 vs −0.04880 |
| T5 magnitude+volume | 1.000 | −0.03332 vs −0.04890 |
| T3 volatility-only | 0.994 | −0.03635 vs −0.04893 |
| T4 volume-only | **0.622** | −0.04736 vs −0.04882 |

Per-instrument randomized-retention percentile:

| | AUDJPY | EURUSD | GBPJPY | GBPUSD | USDJPY | XAUUSD |
|---|---:|---:|---:|---:|---:|---:|
| T1 canonical | 0.858 | 0.518 | 0.998 | 0.654 | 0.669 | 0.219 |
| **T2 magnitude** | **0.962** | **0.839** | **0.953** | **0.863** | 0.653 | 0.381 |
| T3 volatility | 0.774 | 0.479 | 0.892 | 0.680 | 0.661 | 0.000 |
| T4 volume | 0.551 | 0.174 | 0.648 | 0.372 | 0.662 | 0.167 |

Magnitude-only lifts EURUSD (0.52 → 0.84) and GBPUSD (0.65 → 0.86) from
near-chance to clear placebo winners. Volume-only barely clears chance
pooled and fails 4 of 6 instruments individually.

**Generic exposure-reduction control (Hypothesis E):** for *every*
treatment the deterministic same-retention generic reduction lands within
~0.0002R of the unfiltered baseline (e.g. T1 generic −0.04627 vs baseline
−0.04643) — mere exposure reduction explains essentially none of the
effect. The information filters beat generic reduction by ~0.02R
(magnitude-only filter −0.026 vs generic −0.047). **Hypothesis E is
rejected.**

## Directional Contamination

Case classification is **identical** for canonical and magnitude-only:

| Instrument | corr(T1,T2) | mean T1 removed | mean T1 retained | Case |
|---|---:|---:|---:|---|
| USDJPY | −0.256 | −0.025 | +0.007 | B |
| GBPJPY | −0.209 | −0.067 | +0.023 | B |
| AUDJPY | −0.177 | −0.099 | +0.025 | B |
| GBPUSD | −0.013 | −0.041 | +0.025 | A |
| EURUSD | +0.006 | −0.014 | +0.012 | A |
| XAUUSD | −0.038 | +0.089 | +0.043 | D |

**4 of 6 instruments (all 3 JPY-quoted, plus XAUUSD) are Case B/D** even
for the "clean" magnitude-only mechanism. The JPY-pair benefit is
substantially the filter removing observations that are, on average,
adverse for the fixed always-long direction — a real effect, but not a
demonstrated direction-agnostic risk property. Only EURUSD and GBPUSD
(Case A) show genuinely direction-neutral selection. Volume-only (T4) is
**6/6 Case B/D** — entirely direction-correlated.

**Verdict: `DIRECTIONALLY_DEPENDENT`.**

## Direction-Neutral Diagnostic

For the JPY pairs, `mean |T1| removed` is *lower* than `mean |T1|
retained` (e.g. AUDJPY 0.911 vs 1.035) — the filter is not simply
excluding big-move bars symmetrically; combined with the Case-B
signed-return asymmetry, the selection remains tied to directional
exposure for those instruments. For EURUSD/GBPUSD the absolute-movement
gap is larger and the signed asymmetry smaller — the cleaner cases.

## JPY Hypothesis

| Treatment | JPY mean effect | non-JPY mean effect | JPY / non-JPY n consistent |
|---|---:|---:|---:|
| T1 canonical | +0.02686 | −0.00443 | 3 / 1 |
| **T2 magnitude-only** | +0.02325 | **+0.01184** | 3 / **2** |
| T3 volatility-only | +0.02001 | −0.00786 | 3 / 1 |
| T4 volume-only | +0.01043 | −0.01272 | 3 / 0 |
| T5 magnitude+volume | +0.02638 | −0.00445 | 3 / 1 |
| T6 magnitude+volatility | +0.02593 | −0.00177 | 3 / 2 |

Magnitude-only is the **only** treatment that pulls the non-JPY group to
a positive mean effect. JPY mean corr(T1,T2) = −0.214 vs non-JPY −0.015
in every treatment. **Labelled descriptive / hypothesis-generating —
N=6, no causal claim.**

## XAUUSD Failure

XAUUSD is **Case D and FAILURE in every one of the seven treatments**.
Its filter-removed observations have a *higher* mean always-long return
than its retained ones under every treatment (e.g. magnitude-only: +0.089
removed vs +0.043 retained). The filter is systematically excluding
high-predicted-magnitude periods that, for XAUUSD's strong secular
uptrend within this sample, are disproportionately *favourable* for the
fixed long scaffold. Magnitude-only makes it least bad (−0.00533,
placebo percentile 0.38); volatility-only makes it worst (−0.03006,
placebo percentile 0.0). **This is direct evidence against a universal
magnitude-risk hypothesis — reported as a finding, not converted into an
optimization problem. XAUUSD is retained in every table.**

## Fold-Level Analysis

Per-instrument consistency classification (3 walk-forward folds):

| Treatment | STRONG | MODERATE | MIXED | FAILURE |
|---|---|---|---|---|
| T1 canonical | AUDJPY, GBPJPY, GBPUSD, USDJPY | — | EURUSD | XAUUSD |
| **T2 magnitude-only** | AUDJPY, GBPJPY, USDJPY | **EURUSD, GBPUSD** | — | XAUUSD |
| T3 volatility-only | AUDJPY, GBPUSD | GBPJPY, USDJPY | EURUSD | XAUUSD |
| T4 volume-only | USDJPY | AUDJPY, GBPJPY | — | EURUSD, GBPUSD, XAUUSD |
| T6 mag+volatility | AUDJPY, GBPJPY, GBPUSD, USDJPY | EURUSD | — | XAUUSD |

Magnitude-only is the **best-generalizing** treatment: 5 of 6 instruments
strong-or-moderate (only XAUUSD fails), and it is the only treatment that
moves EURUSD off MIXED. **Verdict: `CROSS_INSTRUMENT_PARTIAL`** (XAUUSD's
outright failure prevents `CROSS_INSTRUMENT_GENERAL`).

## Temporal Stability

Using the 3 walk-forward folds as the predefined boundaries: no treatment
has a single fold contributing >60% of the total absolute delta except
T6 (0.641, marginal). Magnitude-only: fold deltas +0.03052 / −0.00004 /
+0.02601 — balanced across folds 1 and 3, flat (not negative) in fold 2,
mirroring canonical's own fold-2 behaviour. The effect is **not**
concentrated in a single period.

## Cost Attribution

Pooled expectancy delta is numerically identical across LOWER/BASE/
ADVERSE/SEVERE (all +0.01163 for canonical). This is disclosed as a
**structural** property: baseline and filter subtract the same per-trade
cost constant and expectancy is a linear mean, so cost cancels exactly in
the delta regardless of value. **This is not "strong cost robustness" in
the sense of surviving increasing real transaction friction** — the
treatment contrast is simply mathematically insensitive to this
symmetric cost specification. Neither treatment is net-profitable in
absolute terms (baseline and filter both have negative pooled
expectancy).

## Drawdown Attribution

| Treatment | Filter DD improvement | Generic DD improvement | Incremental beyond generic |
|---|---:|---:|---:|
| **T2 magnitude-only** | **9,209R** | 5,156R | **4,053R** |
| T6 mag+volatility | 7,645R | 3,947R | 3,698R |
| T1 canonical / T7 full | 7,224R | 3,811R | 3,413R |
| T5 mag+volume | 7,044R | 3,947R | 3,097R |
| T3 volatility-only | 6,016R | 3,811R | 2,204R |
| T4 volume-only | 3,485R | 3,811R | **−326R** |

Magnitude-only produces the largest drawdown improvement *and* the
largest improvement beyond what generic exposure reduction achieves —
selection, not reduced exposure, is doing the work. Volume-only's
drawdown "improvement" is entirely explained by trading less (negative
incremental).

## Minimum Sufficient Mechanism

Walking the predeclared information hierarchy (generic reduction →
volatility → magnitude → magnitude+volatility → magnitude+volume → full),
the first level that reaches ≥80% of canonical's pooled effect **and**
beats its own randomized-retention placebo (percentile ≥0.90) is
**magnitude-only** (pooled +0.01883 = 162% of canonical, placebo
percentile 1.000).

**Scenario A — magnitude-only explains the effect; volume is
unnecessary.** (Volatility-rank features are also not required — magnitude
alone suffices and generalizes better.)

## Final Verdicts

- **Magnitude effect: `MAGNITUDE_EFFECT_CONFIRMED`** — magnitude-only
  reaches 162% of canonical's pooled effect and beats its own placebo at
  the 100th percentile.
- **Volatility explanation: `VOLATILITY_EXPLANATION_PARTIAL`** —
  volatility-rank features alone explain ~55% of canonical's effect;
  material but not dominant, and worse-generalizing than magnitude.
- **Volume incremental value: `VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED`**
  — adding `volume_rank` degrades the magnitude-only effect by −0.00738R
  pooled, is positive on only 2 of 6 instruments, and specifically
  destroys the EURUSD/GBPUSD magnitude signal.
- **Filter mechanism: `FILTER_MECHANISM_CONFIRMED`** — the canonical
  filter beats both its randomized placebo (100th percentile) and the
  generic exposure-reduction control by a clear margin, on 4 of 6
  instruments.
- **Directional dependence: `DIRECTIONALLY_DEPENDENT`** — 4 of 6
  instruments (all 3 JPY-quoted plus XAUUSD) show direction-correlated
  selection (Case B/D) even under magnitude-only.
- **Cross-instrument generalization: `CROSS_INSTRUMENT_PARTIAL`** — 5 of 6
  instruments show consistent benefit under magnitude-only, but XAUUSD
  fails outright in every treatment.

## What Has Been Proven

- The Phase-92 filter effect is reproduced exactly and is carried by the
  raw realized-magnitude features alone; magnitude-only *exceeds* the
  canonical filter pooled and generalizes to 5 of 6 instruments.
- Adding `volume_rank` to the magnitude features contributes no isolable
  value and is slightly-to-materially harmful (pooled −0.00738R, harmful
  on EURUSD/GBPUSD).
- Mere exposure reduction (Hypothesis E) explains essentially none of the
  effect — the generic control lands within ~0.0002R of the unfiltered
  baseline.
- Drawdown improvement is a selection effect, largest under
  magnitude-only, and exceeds what generic exposure reduction achieves.
- The magnitude/volatility/volume decomposition is deterministic and
  reproducible (`match = True`).

## What Has NOT Been Proven

- **Direction-neutrality** — the mechanism remains directionally
  dependent for 4 of 6 instruments; the JPY-pair benefit is substantially
  "removing adverse-for-always-long observations", not a demonstrated
  direction-agnostic risk property.
- **Universal applicability** — XAUUSD fails in every treatment; its
  removed observations are *favourable* for always-long.
- **Causality** — all deltas are controlled treatment contrasts, not
  causal coefficients.
- **Quote-currency causality** — descriptive correlate only, N=6.
- **Genuine cost robustness** — the invariance found is structural, not a
  demonstrated survival under increasing real friction.
- **Standalone profitability** — neither the baseline nor any filter
  treatment is net-profitable in absolute terms.
- **Production readiness** — unchanged: no.

## Next Research Question

The mechanism is now isolated to the raw magnitude features, with volume
shown to be unnecessary and harmful. The next scientifically necessary
question is whether the **magnitude-only** filter's benefit is genuinely
a *risk* property or an artefact of the always-long scaffold: a
direction-neutral re-test restricted to the four magnitude features
(dropping `volume_rank` and the volatility-rank features entirely),
evaluated on absolute-movement / adverse-excursion distribution rather
than always-long P&L, with XAUUSD's Case-D behaviour as the specific
falsification target. This is **not** an escalation toward a trading
strategy or a risk-management candidate — the directional dependence and
XAUUSD failure must be resolved first, and profitability has never been
established.
