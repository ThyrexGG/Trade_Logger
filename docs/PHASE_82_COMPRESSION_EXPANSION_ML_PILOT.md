# Phase 82 — V1 15m Compression → Expansion ML Pilot

**Status: COMPLETE.** A research-integrity phase investigating V1 only
(V2 is closed, `V2_EXPLAINED_BY_TIME_AND_VOLATILITY`, Phase 81).

**Final verdict: `V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT`.** V1 (compression
persistence → subdued expansion) is real and reproducible, but compression
DURATION adds only a negligible, placebo-indistinguishable increment
(pooled OOS ΔR² = +0.0015, bootstrap CI **[-0.0025, +0.0056] — includes
zero**) beyond volatility + time/session alone, and that tiny increment
flips sign across years, instruments, and leave-one-out folds with no
consistent direction. 9/10 gates passed; Gate H (matched placebo) failed.

## 1. Executive Summary

A nested regression decomposition of Phase 78/79's V1 target
(compression-duration → range-expansion) resolved two genuine
methodological issues before any result could be trusted: (1) the literal
Phase 78 event definition makes "duration" a structural constant, requiring
a documented, minimal generalisation to study it at all; (2) Phase 78/79's
baseline-centred target is a non-causal, per-STUDY global constant, unsafe
as a per-row ML label — fixed by using the raw expansion ratio, matching
Phase 80's own precedent for V2. With both corrected, the central
comparison — compression+volatility+time (M6) vs. volatility+time (M5) —
shows only a **negligible incremental OOS R² gain (+0.0015, 95% CI
[-0.0025, +0.0056], including zero)**, and that tiny gain has NO consistent
sign across the 3 calendar years, the 6 instruments, or leave-one-out
folds. A population-matched placebo control (Phase 80/81's corrected
methodology) shows real M6 performance (R²=0.028) at or below the placebo's
own noisy range (R² -0.04 to +0.06 across shift values). Volatility alone
and time/session alone are each modestly predictive; nonlinear reference
models (RandomForest, HistGradientBoosting) reach much higher absolute R²
(~0.21-0.25) using the FULL feature set, but compression's OWN marginal
contribution stays small (+0.008 to +0.014) even there. **Verdict:
V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT. Further ML development for V1 is
not justified.**

## 2. Research Question

Does the duration of a volatility-compression episode contain predictive
information about subsequent range expansion beyond ordinary volatility
state, time/session structure, and recent price/range conditions? The
central out-of-sample comparison is **Compression + Volatility + Time
(M6)** vs. **Volatility + Time (M5)**.

## 3. Phase 78 V1 Discovery Background

Phase 78 found compression-DURATION → range-persistence (V1): compression
persists rather than immediately releasing into expansion, universal on
15m across all 6 instruments, classified `ML_TARGET_READY`.

## 4. Phase 79 Target Integrity Findings

Phase 79 certified V1 `TARGET_INTEGRITY_READY` (restricted to 15m):
timestamp ordering, rolling-window safety, future-shock invariance,
placebo decoupling, purge/embargo, leave-one-out, cross-year stability all
verified.

## 5. Exact Canonical V1 Definition

Reused unchanged: compression threshold = ATR percentile rank
(`atr_rank`, causal, trailing-200-bar) `<= 0.10`; minimum run = 3
consecutive compressed bars; target = `(sum of true range over the next h
bars) / (atr_stable(event) * h) - 1`, `atr_stable` = trailing-200-bar
**mean** of ATR(14), never the event-time ATR. 15m only. Horizons
`{1,2,4,8}`, h=4 headline. Target version `V1-target-v1`.

**A documented ambiguity and its resolution** (§1 of the module docstring):
Phase 78's literal event builder selects ONLY the bar where
`comp_run == 3` — the first bar of a qualifying streak — so under that
literal definition, "compression duration" at event time is a **constant**
(verified empirically: every literal event has `comp_run == 3`, no
exceptions). This phase's entire premise (studying duration as a variable)
is impossible on that population. Resolution: two datasets are built from
the SAME `comp_run` column with the SAME threshold and minimum run —
**canonical** (`comp_run == 3`, reproduced only as a continuity check
against Phase 78/79's own published numbers) and **duration-extended**
(`comp_run >= 3`, this phase's PRIMARY dataset, where `comp_run` itself —
3, 4, 5, ... naturally decaying — is the genuinely variable duration
feature). Verified: the canonical dataset's raw target minus its stored
`baseline_mean` reproduces Phase 78's own aggregate mean to 6 decimal
places.

**A second correction, found via the future-shock invariance test**: Phase
78/79's `study_range_expansion` centres its reported effect by subtracting
a `baseline_mean` computed once, non-causally, over the WHOLE dev/oos
slice — a legitimate convention for one-time aggregate hypothesis testing,
but not a valid per-row ML label (inserting a future shock changed the
reported target for events far before it, even though every feature and
model prediction stayed identical). Fixed by using the RAW ratio as the ML
target, matching Phase 80's own precedent (V2's ML target is the raw
label, not Phase 78/79's baseline-centred aggregate effect). `baseline_mean`
is retained as metadata only.

## 6. Dataset

| | Value |
|---|---|
| Instruments | 6 (XAUUSD, USDJPY, EURUSD, GBPJPY, GBPUSD, AUDJPY) |
| Timeframe | 15m only |
| Rows (extended, all horizons — event count is horizon-independent) | 49,915 |
| Canonical events (pooled, headline) | 6,341 |
| Target mean by horizon | h1: -0.307, h2: -0.285, h4: -0.246, h8: -0.191 |

Target means are negative and shrink toward zero as the horizon grows —
consistent with Phase 76/78's compression-persistence finding (the range
stays suppressed relative to the stable ATR baseline, gradually easing).

## 7. Event Construction

Every feature at event bar `i` uses only `df[..i]`; the event's own
qualification (`comp_run >= 3`) depends only on backward-looking data
(`comp_run` is a purely causal run-length counter). Verified functionally
(`event_selection_audit`): truncating the series strictly after an event
must not change whether that event still qualifies.

## 8. Overlap Structure

(single instrument, XAUUSD, headline horizon, for a representative check)

| Population | N events | Avg gap (bars) | % neighboring pairs overlapping |
|---|---|---|---|
| Canonical (`comp_run==3`) | 1,008 | 98.9 | 0.0% |
| Duration-extended (`comp_run>=3`) | 8,349 | 11.9 | 87.9% |

As expected and flagged in §1: the duration-extended population has heavy
within-streak overlap (consecutive bars of the same compression episode),
while the canonical population — one event per streak — has none. This is
accounted for via the block-bootstrap (block=horizon) throughout, but the
raw event COUNT for the extended population should not be read as that
many independent observations.

Event-selection audit: **PASS** (truncating the series after an event does
not change whether that event qualifies — verified functionally, and the
detector was independently confirmed to catch a deliberately forward-looking
builder in tests). Censored-event audit: **0 events dropped** for an
incomplete forward window (headline horizon).

## 9. Feature Registry

| Group | Features |
|---|---|
| COMPRESSION | `duration` (comp_run, capped at 60), `severity` (0.10 − atr_rank, so larger = deeper compression) |
| VOLATILITY | `rv`, `rv_rank`, `atr_ret` |
| RANGE_PRICE | `ret_1`, `ret_4`, `ret_8`, `abs_ret_1`, `tr_atr`, `body_range_ratio`, `upper_wick_ratio`, `lower_wick_ratio`, `dist_from_roll_high`, `dist_from_roll_low` |
| TIME | `hour_sin`, `hour_cos`, `dow`, `session_code` |
| REGIME | `regime_code` |

`atr_rank` (the quantity that DEFINES compression) is deliberately kept
out of the generic VOLATILITY group and instead transformed into
`severity` inside COMPRESSION, avoiding definitional double-counting.

## 10. Baseline Hierarchy

Headline (15m, h=4, fold 3 / 2025 H2 onward, N_test=14,742), Ridge (primary):

| Model | Features | OOS R² | MAE |
|---|---|---|---|
| M0 — constant | 0 | 0.000 | 0.270 |
| M1 — volatility | 3 | 0.034 | 0.264 |
| M2 — compression | 2 | 0.013 | 0.265 |
| M3 — compression+volatility | 5 | 0.036 | 0.261 |
| M4 — time/session | 4 | 0.006 | 0.268 |
| M5 — volatility+time | 7 | 0.027 | 0.265 |
| M6 — compression+volatility+time | 9 | 0.028 | 0.264 |
| M7 — +price/range | 19 | 0.058 | 0.257 |
| M8 — full (+regime) | 20 | 0.072 | 0.255 |

**The key comparison, M6 − M5 = +0.0015** — compression adds almost
nothing to volatility+time. Compression ALONE (M2, 0.013) is weaker than
volatility alone (M1, 0.034); M3 (compression+volatility, 0.036) barely
exceeds M1. Price/range (M7) and regime (M8) each add markedly more than
compression does (M5→M7: +0.031; M7→M8: +0.014).

Secondary reference models (RandomForest, HistGradientBoosting) reach much
higher absolute R² using the same feature groups — reported in §25 — but
the SAME qualitative pattern (compression's marginal contribution stays
small relative to the jump from adding price/range/regime) holds there too.

## 11. Duration Distribution

N=49,915. Min 3, max 60 (capped feature; raw streaks up to 60 bars
observed), mean 8.9. Geometrically decaying — 6,341 at duration=3, falling
smoothly to single digits by duration≈45 — exactly the shape expected from
a persistence process (each additional bar has some hazard of the
compression streak ending).

## 12. Duration Dose-Response

Predeclared bins {3, 4, 5, 6, "7+"}, pooled dataset:

| Duration | N | Mean target | Median | Bootstrap CI |
|---|---|---|---|---|
| 3 | 6,341 | -0.304 | -0.370 | [-0.313, -0.294] |
| 4 | 5,615 | -0.292 | -0.360 | [-0.303, -0.281] |
| 5 | 5,076 | -0.273 | -0.342 | [-0.284, -0.262] |
| 6 | 4,582 | -0.252 | -0.318 | [-0.264, -0.239] |
| 7+ | 28,301 | -0.219 | -0.281 | [-0.225, -0.213] |

**Monotonically increasing** (toward zero, i.e. less-suppressed range) as
duration grows — a clean, statistically well-separated dose-response
(every bucket's CI is disjoint from its neighbors). This is Statement A
from §51 of the master prompt ("longer compression is associated with
larger subsequent ranges") and it is TRUE. It is a materially different
claim from Statement C ("compression duration adds predictive information
BEYOND volatility and session") — §17 addresses that directly, and answers
NO.

## 13. Volatility Conditioning

| `rv_rank` tercile | Mean duration | N | Mean target |
|---|---|---|---|
| low | 8.56 | 35,611 | -0.281 |
| mid | 9.39 | 12,368 | -0.175 |
| high | 10.85 | 1,936 | -0.060 |

Compression events occurring during already-higher-volatility regimes tend
to (a) last slightly longer on average and (b) show markedly LESS
suppressed subsequent range. This partially explains why M1 (volatility
alone) already captures much of what M2 (compression alone) captures.

## 14. Session/Time Conditioning

| Session | Mean duration | N | Mean target |
|---|---|---|---|
| TOKYO | 9.15 | 19,558 | -0.200 |
| LONDON | 9.92 | 1,695 | -0.178 |
| LONDON_NY_OVERLAP | 9.59 | 1,193 | -0.078 |
| NEW_YORK | 7.19 | 11,247 | -0.294 |
| LATE_US | 9.49 | 16,222 | -0.289 |

A real session effect exists (target ranges from -0.078 in the overlap to
-0.294 in NY/late-US) — but as established directly in §10 (M4, time
alone, R²=0.006) this session effect is weak in absolute predictive terms
relative to volatility.

## 15. Compression Severity Analysis

Pearson correlation(duration, severity) = **-0.023** — essentially
uncorrelated. Duration and severity (how deep the compression is, `0.10 −
atr_rank`) are genuinely SEPARATE axes of information, not confounded
proxies for each other. In the residual-information regression (§17),
`severity`'s coefficient is much larger in magnitude than `duration`'s in
every specification — to the (limited) extent compression carries any
signal at all, severity appears more relevant than duration, though
neither survives out-of-sample (§17).

## 16. Range Conditioning

Recent-true-range terciles are heavily skewed by construction (compression
events inherently have LOW current true range, so the "high" tercile is
almost empty for this population): low tercile N=48,455 (mean target
-0.253), mid N=1,437 (mean target -0.028). Not independently decisive, but
consistent with volatility/severity already capturing most of what "recent
range" would add.

## 17. Residual Information

Train-only context models (Ridge on volatility+time, and separately on
volatility+time+range), residual scored on the headline fold's TEST split;
does `duration`+`severity` explain any of the residual (3-fold CV linear
regression R²)?

| Context removed | Residual R² explained by compression |
|---|---|
| Volatility + time | **-0.018** |
| Volatility + time + range | **-0.018** |

**Negative** — compression performs WORSE than predicting the residual's
own mean, i.e. no genuine out-of-sample explanatory power survives once
volatility and time (with or without recent range) are already known. This
is the single clearest piece of evidence against Statement C/H1 in this
entire phase.

## 18. ML Models

Ridge (primary, interpretable, `StandardScaler` pipeline) for the full
nested M0–M8 sweep; RandomForestRegressor and HistGradientBoostingRegressor
(secondary reference, matching Phase 80's model family) at the 3 key
comparisons (M5, M6, M8). All `sklearn`, already a project dependency. No
deep learning, no new dependency, no hyperparameter search.

## 19. Walk-Forward Methodology

Identical to Phase 80/81: calendar-YEAR purged walk-forward
(`phase80_ml_volatility_regime.make_folds`/`split_fold`, unchanged) — 3
folds, test windows 2023H2/2024H2/2025H2-onward.

## 20. Cross-Asset Results

Δ(M6−M5) OOS R², headline fold, pooled model's own rows per instrument:

| Instrument | Δ R² |
|---|---|
| USDJPY | +0.0160 |
| XAUUSD | +0.0121 |
| AUDJPY | +0.0019 |
| GBPJPY | -0.0024 |
| GBPUSD | -0.0122 |
| EURUSD | -0.0197 |

**Split 3 positive / 3 negative** — no consistent direction. One asset does
not drive the (already-negligible) pooled result; rather, the pooled
result being near-zero reflects genuine cancellation across instruments.

## 21. Cross-Year Results

| Test period | M5 R² | M6 R² | Δ |
|---|---|---|---|
| 2023 H2 | 0.034 | 0.033 | -0.0015 |
| 2024 H2 | 0.129 | 0.152 | +0.0222 |
| 2025 H2+ | 0.027 | 0.028 | +0.0015 |

2024 is a clear outlier year (both models reach much higher absolute R²
than 2023/2025 — likely a higher-volatility or more trending year overall)
and is also the only year with a delta that isn't essentially zero. The
sign flips from 2023 (slightly negative) to 2024 (positive) to 2025
(slightly positive) — not a stable, monotonic pattern.

## 22. Leave-One-Out Results

Refit on 5 instruments, evaluate on the excluded one (headline fold):

| Held-out instrument | M5 R² | M6 R² | Δ |
|---|---|---|---|
| XAUUSD | -0.072 | -0.043 | +0.0291 |
| USDJPY | 0.033 | 0.047 | +0.0148 |
| AUDJPY | -0.051 | -0.049 | +0.0016 |
| GBPJPY | 0.002 | -0.002 | -0.0032 |
| GBPUSD | 0.063 | 0.052 | -0.0105 |
| EURUSD | 0.109 | 0.088 | -0.0212 |

Again split — 3 positive, 3 negative, including two NEGATIVE base R² values
(XAUUSD, AUDJPY) for BOTH models, meaning volatility+time itself doesn't
even beat a constant predictor when generalizing to those held-out
instruments. Compression does not rescue this in either direction
consistently.

## 23. Horizon Results

Δ(M6−M5) OOS R² (Ridge), all 3 folds, all 4 horizons:

| Horizon | Fold 1 | Fold 2 | Fold 3 |
|---|---|---|---|
| h=1 | +0.0050 | +0.0162 | +0.0073 |
| h=2 | +0.0021 | +0.0200 | +0.0047 |
| h=4 | -0.0015 | +0.0222 | +0.0015 |
| h=8 | -0.0065 | +0.0154 | -0.0054 |

All four horizons reported, none cherry-picked. h=1 and h=2 show
consistently (if very small) POSITIVE deltas across all 3 folds; h=4 and
h=8 flip sign in fold 1 and/or fold 3. This is a genuine, honestly-reported
nuance: the very-short-horizon comparison is directionally more consistent
than the longer ones, though even its largest values (~0.02, fold 2 only)
remain well short of a "material" effect size, and fold 2's outlier
magnitude (§21) is present at every horizon — the consistency is in SIGN,
not in a stable, material magnitude.

## 24. Calibration

Regression-analog reliability check (error-by-prediction-decile, M6, Ridge,
headline fold): mean actual tracks mean predicted directionally across
deciles, with the usual regression-to-the-mean compression at the extremes
(Ridge's predictions have a narrower range than actual outcomes) — expected
for a linear model on a noisy target, not a defect. No probability
threshold was tuned on OOS data anywhere in this phase.

## 25. Feature Importance

Ridge coefficients (interpretable, primary model) and the reference-model
comparison, headline fold:

| Model group | Ridge OOS R² | RandomForest OOS R² | HistGradientBoosting OOS R² |
|---|---|---|---|
| M5 (volatility+time) | 0.027 | 0.207 | 0.208 |
| M6 (compression+volatility+time) | 0.028 | 0.215 | 0.222 |
| M8 (full) | 0.072 | 0.217 | 0.251 |

Nonlinear models capture SUBSTANTIALLY more structure overall than Ridge
(0.21-0.25 vs. 0.03-0.07) — meaning V1 is considerably more predictable
than the linear baseline hierarchy alone would suggest, driven by
interactions among volatility/time/price/candle/regime features. Critically,
though, compression's OWN marginal contribution (M6−M5) stays small even in
the nonlinear models: HGB +0.014, RF +0.008 — the same qualitative
conclusion as Ridge's +0.0015, just at a different absolute R² baseline.
Labelled explicitly as a predictive-attribution diagnostic, not causal
evidence.

## 26. Matched Placebo

Reuses Phase 80/81's corrected methodology: identical feature rows, target
recomputed at `event_idx + shift_bars` instead of `event_idx` — decouples
the true horizon timing while holding the evaluated population exactly
fixed.

**Results** (headline fold, shift=200 bars, Ridge):

| | Real | Matched placebo |
|---|---|---|
| M5 (volatility+time) | 0.027 | 0.052 |
| M6 (compression+volatility+time) | 0.028 | 0.046 |

The real result does NOT exceed the placebo for either model — **Gate H
fails outright** (not merely "below margin" as in Phase 80/81's V2 case,
the sign is actually reversed here). Combined with the noisy temporal-shift
sweep (§29), the honest reading is that this dataset (49,915 rows, ~4x
smaller than V2's) produces a high-variance placebo estimate, and the real
result sits comfortably inside that noise band rather than clearly above
or below it — either way, it provides no evidence FOR compression's
incremental value.

## 27. Shuffled Target

OOS R² = **-0.002** (M6, Ridge, headline fold) — at chance, confirming no
leakage (§18: had this stayed materially positive, the pipeline would need
to stop and be investigated).

## 28. Future Shock

**PASS** — after the target-centering correction (§5), features, targets
(for events before the cutoff), AND model predictions are all confirmed
identical between the normal and future-shocked synthetic datasets.

## 29. Temporal Shift

Sweeping the matched-placebo shift from 50 to 2,000 bars (M6, Ridge):
R² = -0.043, +0.037, +0.046, +0.060, +0.029 respectively — noisy, ranging
from negative to positive with no smooth decay pattern. Unlike Phase 81's
V2 finding (a stable ~0.60-0.63 AUC band across the same shift range,
attributed to slow-moving session/instrument structure), V1's smaller
sample size here produces a genuinely noisy placebo estimate rather than a
clean signature of persistent structure. Treated as a diagnostic, not a
definitive null, per the master prompt's own instruction (§33) — the
noise itself is reported honestly rather than over-interpreted in either
direction.

## 30. Bootstrap

Paired, block-bootstrap (block=4 bars, matching the horizon) CI for
Δ(M6−M5) OOS R², headline fold:

```
point = +0.0015
95% CI = [-0.0025, +0.0056]
```

**The CI includes zero.** This is the single strongest piece of evidence in
the entire phase against H1 — even before considering the placebo,
cross-year, or cross-asset instability, the primary comparison's confidence
interval cannot rule out a true effect of exactly zero.

## 31. Multiple Testing

The primary hypothesis (H1: compression duration adds incremental
information beyond volatility+time) is tested ONCE, on the pre-registered
M6-vs-M5 comparison. Cross-asset (6), cross-year (3), and horizon (4) cuts
are reported as descriptive stability checks on that SAME primary
comparison, not as independent hypothesis tests — no p-value correction is
applied because no additional formal significance claim is made from them;
they either corroborate or undermine the single primary comparison's
stability. No asset/year/horizon cell was selected post-hoc for emphasis.

## 32. Gate Results

| Gate | Result |
|---|---|
| A — Dataset integrity | PASS |
| B — Leakage (contract + future-shock) | PASS |
| C — Reproducibility | PASS (identical content_hash across 2 independent OS-process runs) |
| D — Residualization methodology | PASS |
| E — Event-selection validity | PASS |
| F — Cross-asset complete (all 6) | PASS |
| G — Cross-year complete (all 3) | PASS |
| **H — Matched placebo** | **FAIL** (real ≤ placebo for both M5 and M6) |
| I — Shuffled target collapses | PASS (-0.002) |
| J — Holdout protected | PASS |

9/10 passed; Gate H is the deciding failure, directly aligned with the
bootstrap CI (§30) and cross-cut instability (§20-22).

## 33. Limitations

- The dataset is materially smaller than V2's (≈50K vs. ≈200K rows),
  producing noisier placebo/shift estimates (§29) than Phase 81 saw for V2.
- The duration-extended event population has substantial within-streak
  overlap (§8); the block-bootstrap (block=horizon) partially but not
  fully accounts for this — a longer block would be more conservative but
  was not substituted for the project's established horizon-based
  convention (documented, not silently changed, §26 of the master prompt).
- The residual-information test (§17) is linear; nonlinear residual
  structure would not be caught by it, though the nested HGB/RF comparison
  (§25) — which CAN capture nonlinearity directly — tells the same
  qualitative story (small marginal compression contribution).
- 2024 is a clear outlier year in absolute R² terms (§21); with only 3
  years of 15m data available, this cannot be further decomposed.

## 34. Final Verdict

**`V1_PREDICTABLE_BUT_EXPLAINED_BY_CONTEXT`**

V1 (compression persists rather than immediately releasing into expansion)
remains a real, reproducible, monotonic dose-response phenomenon (§12).
Compression DURATION specifically, however, does not add meaningful
predictive information beyond volatility and time/session structure: the
central OOS ΔR² is statistically indistinguishable from zero, does not
exceed a population-matched placebo, and has no consistent sign across
years, instruments, or leave-one-out folds. This is a successful,
informative research outcome, not an inconclusive one — and, per §41 of
the master prompt, it was verified conservatively rather than rescued: the
first future-shock check failure was diagnosed and fixed as a genuine
methodological bug BEFORE any result was interpreted, and the resulting
numbers (both before and after that fix) told the same story.

## 35. V1 Research Decision

**Further ML development for V1 is NOT justified.** The evidence does not
meet the bar for `V1_INCREMENTAL_INFORMATION_CONFIRMED` (§49 of the master
prompt requires positive incremental OOS effect, non-negligible effect
size, survival of matched placebo and shuffled-target controls, cross-year
and cross-asset stability, and directional consistency — none of the
delta-related criteria are met here). This closes V1's predictive-modelling
line for now, alongside V2's closure in Phase 81 — both of the research
program's `ML_TARGET_READY` phenomena from Phase 78 have now been
decomposed and found to be fully explained by simpler, already-understood
context rather than yielding a validated incremental ML edge.

## 36. Recommended Next Phase

None automatically follows. Per the master prompt's own instruction (§70),
the default is more research, not strategy integration: if V1 is used at
all going forward, it should be as a documented descriptive phenomenon
(compression persistence, quantified by the dose-response table in §12) —
a market-context fact, not an ML feature or trading signal. No third
target is opened. No trading strategy of any kind exists anywhere in this
phase or its predecessors.
