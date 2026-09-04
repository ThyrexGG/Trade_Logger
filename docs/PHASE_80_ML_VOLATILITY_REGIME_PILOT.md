# Phase 80 — ML Volatility Regime Prediction Pilot

**Status: COMPLETE.** The first phase in which a predictive ML model is
permitted. Still a research-only pilot: the goal is NOT a profitable trading
strategy — it is whether machine learning can predict the Phase 78/79 V2
volatility-regime target strictly out-of-sample, and whether it adds
information beyond trivial persistence/baseline predictors. No trading
signal, no execution, no live connection.

**Final verdict: `TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE`.** ML
clearly predicts V2 out-of-sample (AUC ≈0.70, stable across 3 calendar years,
6 instruments, 2 timeframes, well-calibrated, fully reproducible, leakage-
free — 7/8 gates passed). What it does NOT demonstrate is a validated
INCREMENTAL edge from the specific short-horizon persistence timing the V2
target was built to capture: a population-matched placebo control shows most
of the full model's AUC advantage over a trivial current-state model
survives even when that timing is deliberately broken, and permutation
importance shows the single most important feature by a wide margin is
`hour` (deterministic time-of-day volatility seasonality) — the model
appears to have substantially rediscovered known session structure rather
than the V2-specific phenomenon itself.

## 1. Objective

Phase 78 discovered, and Phase 79 certified `TARGET_INTEGRITY_READY`, a
non-directional volatility-regime-persistence phenomenon (V2). Phase 80 asks
the next question in the research chain: given a leakage-free target, can a
model trained strictly on past data predict it out-of-sample, and does doing
so contribute anything a human could not already get from "the regime tends
to persist"? A model that merely rediscovers persistence is not a finding —
Phase 80 is built specifically to distinguish the two (§10 of the master
prompt).

## 2. Phase 78 discovery (recap)

V2 = high-volatility-regime persistence: 12/12 (instrument × timeframe) cells
Bonferroni-significant, OOS-consistent, cross-year=1.0, cross-asset=1.0,
effect 10-30× a placebo control. Classified `ML_TARGET_READY`.

## 3. Phase 79 integrity (recap)

`TARGET_INTEGRITY_READY`: timestamp ordering, rolling-window safety,
future-shock invariance, past-shift decoupling, stable-ATR non-contamination,
placebo decoupling, purge/embargo (no crossings), leave-one-out (universal),
cross-year stability (sign+magnitude stable), full-pipeline determinism — all
verified, after a real bug in the audit code itself was caught and fixed.

## 4. Target definition — reused verbatim, not redefined

Event: any bar with trailing realized-vol percentile rank (`rv_rank`,
4-bar realized vol ranked over a trailing 200-bar window) `> 0.66`
(`phase78_market_behavior_discovery_ii._b_vol_bucket_high`, unchanged).
Target: `rv_rank[event_idx + h] > 0.66`, h ∈ {1,2,4,8} bars — the exact Phase
78/79 `V2-target-v1` formula, imported (`phase79_ml_target_integrity.
V2_TARGET_SPEC.version`), never recomputed from a new definition.
`prediction_timestamp = open_time(event_bar) + timeframe_seconds` (the same
convention Phase 79 established and `historical_data_store.get_candles
(as_of=...)` already uses).

## 5. Dataset construction

`phase80_ml_volatility_regime.build_dataset(instrument, tf, horizon)` returns
one auditable row per event × horizon, with `instrument`, `timeframe`,
`horizon_bars`, `event_idx`, `target_idx`, `prediction_timestamp`,
`target_end_timestamp`, `target`, `dataset_version`, `target_version`,
`feature_schema_version`, and one `feat__<name>` column per registry entry.
`build_pooled_dataset` concatenates all 6 instruments and adds
`feat__instrument_code` (a deterministic label encoding) for the pooled
model only. Rows with any non-finite feature (warm-up) or an
out-of-range target horizon are dropped, never imputed. Verified
deterministic (`test_build_dataset_deterministic`) and cross-checked against
Phase 79's own dev-set event counts (XAUUSD 15m full series N=33,862 vs.
Phase 79's dev-only 70% split N=23,716 — consistent).

| Horizon | 15m rows (pooled 6-instrument) | 15m positive rate | 1h rows (h=4 only) | 1h positive rate |
|---|---|---|---|---|
| h=1 | 203,410 | 0.775 | — | — |
| h=2 | 203,408 | 0.646 | — | — |
| h=4 (headline) | 203,401 | 0.481 | 121,022 | 0.417 |
| h=8 | 203,378 | 0.424 | — | — |

Positive rate falls smoothly as the horizon grows (0.775→0.424 on 15m) —
exactly the expected shape for a genuine, decaying persistence effect (a
regime is very likely still HIGH one bar later, less likely eight bars
later), and consistent with Phase 78/79's own h-by-h effect-size decay.

## 6. Feature registry

20 features across 5 groups — deliberately conservative, not "hundreds":

| Group | Features |
|---|---|
| PRICE (5) | `ret_1`, `ret_4`, `ret_8`, `abs_ret_1`, `ret_sign_1` |
| VOLATILITY (6) | `atr_ret`, `atr_rank`, `rv`, `rv_rank`, `rv_change_1`, `atr_rank_change_1` |
| REGIME (2) | `regime_high_duration`, `regime_code` |
| CANDLE (4) | `body_range_ratio`, `upper_wick_ratio`, `lower_wick_ratio`, `tr_atr` |
| TIME (3) | `hour`, `dow`, `session_code` |

Every entry carries `lookback_bars`, `uses_current_bar`, `future_safe` (all
`True` by construction — see §7), `formula`, and `version` metadata
(`feature_registry_dicts()`). `rv_rank` and `regime_high_duration` are
singled out as the **current-state** features: `rv_rank` is the identical
quantity the V2 event definition itself conditions on (restricted to
0.66-1.0 range in this dataset, but with real variance encoding "how
extremely HIGH"); `regime_high_duration` measures how long the HIGH state
has already run. Ablation sets are explicit, nested supersets:
`A_current_state_only` ⊆ `B_plus_volatility` ⊆ `C_plus_price` ⊆
`D_full_conservative` (= the whole registry, nothing hidden).
`feat__instrument_code` is added ONLY to the pooled dataset (not part of the
conservative registry — a context label, not a market feature) and is
EXCLUDED from every ablation set used in the headline analysis, so no result
in this document depends on the model being told which instrument a row
came from.

## 7. Leakage controls

- **Feature/target timestamp contract** (`assert_feature_target_contract`):
  every row's `target_end_timestamp` strictly after `prediction_timestamp`,
  by at least `horizon_bars × timeframe_seconds` (Phase 79's §19 lower-bound
  fix, reused).
- **Static rolling-window scan**: `_build_features`'s source contains no
  `center=True`, no negative `.shift()`, no `bfill`.
- **Future-shock invariance** (`check_feature_future_shock_invariance`):
  identical history through a cutoff, differing only after it — every
  feature column AND a model's predictions for events at/before the cutoff
  must be identical between the normal and shocked datasets.
- **Purge/embargo** (`split_fold`): TRAIN/VAL rows whose target window reads
  at or past the following boundary are dropped; the first `embargo_bars`
  of VAL/TEST after a boundary are dropped too.

**Results**: all 5 dataset variants (15m h∈{1,2,4,8}, 1h h=4; 203,378-
203,410 and 121,022 rows respectively) PASS the timestamp contract — every
row's target ends strictly after its prediction timestamp, by at least
`horizon_bars × timeframe_seconds`. Static rolling-window scan: clean (no
`center=True`, no negative shift, no `bfill`, verified by
`test_no_forward_looking_pandas_patterns_in_feature_builder`). Future-shock
invariance: PASS — every feature AND a fitted model's predictions are
byte-identical for events at/before a synthetic cutoff regardless of a 50×
future shock inserted after it.

## 8. Split methodology

Calendar-YEAR walk-forward, not a random split, not a fixed 70/30: fold *i*
trains on everything before Jan 1 of `boundary_years[i]`, validates on H1 of
that year, and tests on H2 of that year through (exclusive) the next
boundary year. This makes each fold's TEST window a distinct calendar
period — the walk-forward (§16) and the cross-year analysis (§19) are the
SAME experiment, not two. Primary (15m): boundary years 2023/2024/2025 → 3
folds, test windows H2-2023 / H2-2024 / H2-2025-onward. Secondary (1h):
boundary years 2024/2025 → 2 folds (1h has far more history, so fewer,
larger folds were used to bound compute rather than because the data is
scarce). A quantile-based scheme was tried FIRST and rejected: any small
number of expanding-window quantile folds necessarily has ALL its test
windows in the tail of the data, structurally unable to report genuine OOS
performance for 2023/2024 — an honest limitation documented rather than
silently worked around (see `make_folds`'s docstring).

## 9. Purge/embargo — exact methodology

Purge: a TRAIN/VAL row is dropped if `target_end_timestamp >=` the boundary
that separates it from the next split (its label would otherwise depend on
information that split is supposed to own). Embargo: the first
`embargo_bars = max(horizons) = 8` bars' worth of wall-clock time
immediately after a boundary is additionally dropped from VAL/TEST, so a
val/test row's backward-looking feature window cannot closely straddle a
training row on the other side of the boundary.

**Results** (15m, h=4 dataset, all 3 folds):

| Fold | Train raw → purged | Val raw → purged | Test N |
|---|---|---|---|
| 1 (2023H2) | 18,681 → 18,669 (12 removed) | 24,944 → 24,941 (3 removed) | 25,087 |
| 2 (2024H2) | 68,712 → 68,712 (0 removed) | 24,845 → 24,845 (0 removed) | 25,481 |
| 3 (2025H2+) | 119,056 → 119,056 (0 removed) | 24,882 → 24,882 (0 removed) | 59,449 |

Purging is a real, exercised mechanism (fold 1 removed 15 boundary-crossing
rows out of ~43,600) — not a theoretical no-op as it happened to be in
Phase 79's own V2/V1 audit. Later folds show zero crossings simply because
the horizon (max 8 bars ≈ 2 hours on 15m) is tiny relative to a half-year
test window.

## 10. Overlap / effective sample size

Not separately re-derived here — Phase 79 already quantified V2's overlap
structure exhaustively (§8/§15 of `docs/PHASE_79_ML_TARGET_INTEGRITY.md`):
heavy overlap at h≥4 (effective N ≈ 37-74% of raw N by h=8). Phase 80's raw
row counts should be read with that same discount in mind; the walk-forward
test windows (whole calendar half-years) are large enough that this does not
change any qualitative conclusion, but it is why single-row bootstrap CIs
are not used as a precision claim anywhere in this document.

## 11. Baselines

Four baselines, computed on each fold's TRAIN set and scored on that fold's
TEST set:

1. **Majority class** — constant prediction = the more common TRAIN label.
2. **Persistence** ("future_HIGH = current_HIGH") — because EVERY V2 event
   row already has current state = HIGH by construction (that is the event
   definition), this baseline is the constant predictor P(HIGH)=1.0 in this
   population — a structural fact, not a modelling choice
   (`test_persistence_baseline_is_constant_in_this_population`). Both
   constant baselines therefore have **AUC = 0.5 by mathematical necessity**
   — an important interpretive point: in this pre-conditioned population,
   ANY AUC above 0.5 is already informative, unlike a typical use of this
   target formulation on an unconditioned population.
3. **Simple volatility rule** — a single-feature logistic regression on
   `rv_rank` alone, fit on TRAIN. This is the first baseline with genuine
   ranking power, and the real comparison point for "does full ML beat a
   trivial current-state rule" (§10).
4. **Random** — reproducible-seed uniform predictions.

**Headline fold (2025 H2 onward, N=59,449) results:**

| Baseline | ROC-AUC | Accuracy | Log loss | Brier |
|---|---|---|---|---|
| Majority class (always NOT-HIGH) | 0.500 | 0.534 | 6.439 | 0.466 |
| Persistence (always HIGH) | 0.500 | 0.466 | 7.377 | 0.534 |
| Simple volatility rule (`rv_rank` only) | 0.591 | 0.566 | 0.681 | 0.244 |
| Random | 0.501 | 0.498 | 0.997 | 0.333 |

Note majority-class accuracy (0.534) slightly EXCEEDS persistence accuracy
(0.466) — a genuinely counter-intuitive fact of this conditioned population
(slightly more HIGH-conditioned bars revert than persist by h=4), which is
exactly why raw accuracy is not used as the deciding metric anywhere in this
document (§13/§20).

## 12. Models

`LogisticRegression` (wrapped in a `StandardScaler` pipeline — an unscaled
fit failed to converge on the first run, fixed), `RandomForestClassifier`,
`HistGradientBoostingClassifier` — all `sklearn` (already a project
dependency via `requirements.txt`/`ml_trainer.py`; `HistGradientBoosting`
avoids adding `xgboost`/`lightgbm` as new dependencies, §11). Fixed,
sensible defaults; no hyperparameter grid, no OOS tuning (§12/§32).

## 13. Metrics

ROC-AUC, PR-AUC, log loss, Brier score (primary); accuracy, balanced
accuracy, precision, recall, F1, confusion matrix (secondary); a 10-bin
reliability table + expected calibration error (calibration). Reported for
every model/ablation/fold/horizon combination, never accuracy alone.

## 14. Walk-forward — fold-by-fold results

Primary (15m, h=4, ablation D, HistGradientBoosting — the reference model):

| Fold | Test period | N train | N test | ROC-AUC |
|---|---|---|---|---|
| 1 | 2023 H2 | 18,669 | 25,087 | 0.7104 |
| 2 | 2024 H2 | 68,712 | 25,481 | 0.7152 |
| 3 | 2025 H2 onward | 119,056 (capped to 50,000) | 59,449 | 0.6971 |

Remarkably stable across three independent calendar-year OOS windows
(0.697-0.715) — see §16 for the formal cross-year consistency verdict.

Secondary (1h, h=4, ablation D, all 3 models):

| Fold | Test period | N train (capped) | N test | LR AUC | RF AUC | HGB AUC |
|---|---|---|---|---|---|---|
| 1 | 2024 H2 | 50,000 | 6,474 | 0.664 | 0.704 | 0.718 |
| 2 | 2025 H2 onward | 50,000 | 14,708 | 0.641 | 0.690 | 0.705 |

1h results are consistent with 15m (§18): the phenomenon is not an artifact
of one timeframe's resolution.

## 15. Cross-asset

Headline fold (2025 H2), pooled model, per-instrument AUC:

| Instrument | AUC (pooled model, evaluated on its own rows) | AUC (leave-this-instrument-out) |
|---|---|---|
| AUDJPY | 0.684 | 0.674 |
| EURUSD | 0.711 | 0.707 |
| GBPJPY | 0.689 | 0.684 |
| GBPUSD | 0.712 | 0.709 |
| USDJPY | 0.684 | 0.677 |
| XAUUSD | 0.695 | 0.686 |

No single instrument dominates (all 6 sit in a tight 0.68-0.71 band, both
with and without that instrument in the training set) — `no_single_
instrument_dominance = True`, `all_positive_auc_under_loo = True`.
`feat__instrument_code` was never given to any model in this table, so this
consistency is NOT explained by the model simply memorising instrument
identity via an explicit label — see §17 for what the model likely uses
instead.

## 16. Cross-year

Because each walk-forward fold's TEST window IS a distinct, non-overlapping
calendar period, §14's fold table above already answers this directly:
0.7104 (2023H2) → 0.7152 (2024H2) → 0.6971 (2025H2+). `consistent_across_
periods = True` (all three AUCs exceed 0.5, and the spread — 0.018 — is
small). The phenomenon is not a one-year fluke.

## 17. Ablation — and the pilot's central finding

Headline fold (2025 H2), 15m, h=4, all 3 models:

| Ablation | # features | LR AUC | RF AUC | HGB AUC |
|---|---|---|---|---|
| A — current-state only (`rv_rank`, `regime_high_duration`) | 2 | 0.5924 | 0.5907 | 0.5919 |
| B — + volatility | 7 | 0.6247 | 0.6301 | 0.6299 |
| C — + price | 12 | 0.6269 | 0.6343 | 0.6360 |
| D — full conservative | 20 | 0.6476 | 0.6834 | 0.6971 |

Reading top-to-bottom, AUC climbs steadily as features are added — the
naive reading is "ML clearly adds value beyond the trivial current-state
model." **The population-matched placebo control (§19) shows this naive
reading is largely wrong.** Re-running ablations A and D with the SAME
feature rows but the target relabelled 200 bars further into the future
(decoupling the genuine short-horizon timing while holding the population
fixed):

| Ablation | Real AUC | Matched-placebo AUC (shift=200 bars) | Genuine timing effect (real − placebo) |
|---|---|---|---|
| A — current-state only | 0.592 | 0.518 | **+0.074** |
| D — full conservative | 0.697 | 0.665 | **+0.032** |

The genuine, timing-specific effect (the part of the AUC that a
condition-decoupled shuffle CANNOT reproduce) is actually SMALLER for the
full model than for the trivial current-state model. Permutation importance
on the full model (headline fold, HGB) confirms the mechanism:

| Feature | Permutation importance (ΔAUC, fold 3) |
|---|---|
| `hour` | **0.0862** |
| `atr_rank` | 0.0329 |
| `tr_atr` | 0.0255 |
| `rv` | 0.0112 |
| `rv_rank` | 0.0102 |
| `regime_code` | 0.0036 |
| `ret_8` | 0.0037 |
| everything else | ≤ 0.0024, several ≈ 0 or slightly negative |

`hour` (UTC hour-of-day) dwarfs every other feature, including `rv_rank`
itself — the feature the whole V2 phenomenon is built on. This is
consistent with Phase 76's own literature entry (L-INTRADAY-VOL,
Andersen-Bollerslev 1997): volatility has a strong, DETERMINISTIC intraday
seasonality tied to session structure, independent of any genuine
regime-persistence mechanism. `atr_rank`/`tr_atr` plausibly act as
secondary session/instrument "fingerprints" the same way. **The pilot's
central finding: most of "ablation D beats ablation A" is the model
rediscovering known, deterministic session/time-of-day volatility structure
— not a new, validated short-horizon predictive capability about the V2
persistence phenomenon specifically.** This is exactly the failure mode §10
of the master prompt warns against, just one level more subtle than a
naive baseline comparison would have caught.

## 18. Calibration

Headline fold reliability table (10 bins): predicted probabilities track
actual frequencies closely across the full 0-1 range (e.g. bin
predicted≈0.45 → actual≈0.43; predicted≈0.75 → actual≈0.69), with a mild,
consistent OVER-confidence in the upper bins (predicted running ~5 points
above actual from bin 6 upward). **Expected calibration error = 0.0254** —
low, comfortably under the 0.15 threshold used for Gate G. The model's
probability outputs are usable as calibrated-ish estimates, not merely a
ranking score.

## 19. Placebo/null controls

Three independent controls, headline fold (2025 H2), 15m, h=4, ablation D,
HistGradientBoosting:

| Control | AUC | Interpretation |
|---|---|---|
| Real (unperturbed) | 0.697 | — |
| **Shuffled target** (§26 — same rows, TRAIN labels permuted) | 0.519 | Collapses to chance — the pipeline has NO leakage (a properly-behaved control; had this stayed high, §26 says STOP) |
| **Population-decoupled placebo** (§27 literal reading — random events from the WHOLE series) | 0.727 | **CONFOUNDED, diagnostic only** — HIGHER than the real result, traced to a population-breadth artifact (its own ablation-A AUC of 0.629 already exceeds the real data's 0.592), NOT evidence of leakage. Documented in §17 above and not used for Gate H. |
| **Population-matched placebo** (§27, corrected — same rows, target relabelled 200 bars later) | 0.665 | The valid decoupling control: real (0.697) only exceeds this by +0.032, below the 0.05 margin used for Gate H |
| Future-shock invariance | pass | features AND a fitted model's predictions are byte-identical for events at/before a cutoff, regardless of what happens after it |

The shuffled-target control is unambiguous evidence against a leakage bug.
The placebo comparison is where the pilot's real finding lives: the FIRST
(population-decoupled) placebo implementation was itself a methodological
error, caught by noticing the suspicious fact that it scored HIGHER than the
real result — investigated rather than dismissed, exactly the discipline
this project has applied at every prior phase (§20 below has the full
diagnostic trail).

## 20. Determinism

Two levels, both confirmed:

1. **In-process headline signature** (`_headline_fit_signature`): fold 3,
   ablation D, all 3 models, re-fit twice within the same `run()` call —
   identical SHA-256 signature both times (`determinism.match = True`).
2. **Cross-process, full pipeline**: `python -m phase80_ml_volatility_regime`
   run as two fully independent OS processes produced
   `content_hash = dc147df602be96f8cda2dcbfbacbe2ebb2254a5749b17a59030a825d4ee55684`
   both times (a third, earlier run under the pre-scaling-fix `LogisticRegression`
   config produced a different hash purely because that config was later
   corrected for a convergence bug, §19-methodology-note below — not a
   determinism failure).

Every `sklearn` model is constructed with a fixed `random_state=42`; `numpy`
RNGs (label shuffle, placebo sampling) use explicit seeded generators;
`_cap_train_rows`'s stride subsample is a pure function of array length (no
randomness).

## 21. Holdout

| | Value |
|---|---|
| Before Phase 80 | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` |
| After Phase 80 | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` |
| Result | **MATCH** |

No holdout data (`gold_strategy_baseline.HistoricalVsForwardComparator.
LOCKED_HISTORICAL_BASELINE`) was read, imported, or referenced anywhere in
`phase80_ml_volatility_regime.py` — verified by static source inspection
(`test_frozen_holdout_never_accessed`).

## 22. Safety

| Flag | Value |
|---|---|
| `xauusd_market_conditions.FROZEN_CONTRACT_HASH` | unchanged (§21) |
| `ForwardExecutionLifecycleEngine.LIVE_AUTOMATION_ENABLED` | `False` |
| `ForwardExecutionLifecycleEngine.LIVE_BROKER_TRANSMISSION` | `"BLOCKED"` |
| Execution/broker/risk/signal-generation code in Phase 80 | none (`test_no_execution_broker_or_signal_code`) |
| Deep-learning / GPU libraries | none — `sklearn` only, already a project dependency (`test_no_deep_learning_libraries`) |
| Credentials / API keys / secrets added | none |
| New API endpoints | `GET /api/research/ml-volatility-regime` only, read-only; `POST` → 405 |

## 23. Final verdict

**`TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE`**

Gate scorecard (7/8 passed):

| Gate | Result |
|---|---|
| A — Leakage | PASS |
| B — Reproducibility | PASS |
| C — Baseline (beats simple-volatility baseline) | PASS |
| D — OOS (AUC > 0.5 out-of-sample) | PASS |
| E — Cross-asset (no single-instrument dominance) | PASS |
| F — Cross-year (consistent across 2023/2024/2025) | PASS |
| G — Calibration (ECE < 0.15) | PASS (0.025) |
| **H — Placebo** (real must materially outperform a valid decoupled control) | **FAIL** (0.697 vs. 0.665, a +0.032 margin below the 0.05 threshold used elsewhere in this pilot) |

This was not a foregone conclusion picked to fit a comfortable narrative —
the FIRST placebo implementation (population-decoupled, literally following
§27's "reuse Phase 79's methodology") produced the OPPOSITE, alarming signal
(placebo AUC 0.727 > real AUC 0.697), which triggered the investigation in
§17/§19 that led to the corrected, population-matched control and this more
nuanced (and, if anything, LESS flattering) final reading.

## 24. Phase 81 recommendation

Per §48 of the master prompt, since the verdict is
`TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_ML_VALUE`: **do not force more ML
model development for V2.** Investigate instead whether the
persistence/simple-volatility baseline (`rv_rank` alone, or `rv_rank` +
session/`hour`, both of which are already fully understood, cheap,
deterministic quantities) is sufficient as a market-context feature for a
future non-ML use (e.g. conditioning a strategy's risk sizing or filter
logic on "currently HIGH-vol regime + typically-volatile hour", without
needing a trained model). Per §49, V1 (15m compression-duration → range
persistence) is explicitly NOT instantiated in this same reusable framework
yet — the master prompt's own gate ("only after the V2 pipeline is complete
and validated") is satisfied on completeness but not on validation, since
V2's own verdict was a qualified negative; the reusable architecture (target
adapter → dataset builder → feature registry → purged walk-forward →
baseline evaluator → model trainer → evaluator → calibration → ablation →
robustness → report) is nonetheless ready to be pointed at V1 in a future
phase if independently justified. No third target. No trading strategy. No
model connected to any live system.
