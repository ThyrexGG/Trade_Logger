# Phase 79 — ML Target Integrity, Leakage Audit & Pilot Readiness

**Status: COMPLETE.** This is a research-INTEGRITY phase, not a strategy-development
phase and not an ML-training phase. It asks one narrow question about the two
findings Phase 78 classified `ML_TARGET_READY` — V2 (high-volatility regime
persistence) and V1 (15m compression-duration → range expansion): **can they be
turned into rigorously defined, leakage-free, timestamp-correct ML targets?**

No model was trained. No third hypothesis was opened. Phase 77's large-bar
reversal was not reopened.

**Final verdict: V2 = `TARGET_INTEGRITY_READY`. V1 = `TARGET_INTEGRITY_READY`.**
Both targets passed every hard AND soft check in the gate (§23) — no downgrade,
no forced pass. Commit `0ee30e356181e4a789a9a48ce8ee4fa408d8c513` (Phase 78,
unchanged going into this phase) → this phase's own commit is recorded below
(§21/§38).

## §1 Objective

Phase 78 already established, with dev/OOS block-bootstrap CIs, Bonferroni
control, cross-year and cross-instrument stability, and a placebo null, that V2
and V1 are real, non-directional, statistically detectable phenomena. Phase 79
does **not** re-litigate that. It audits whether the way those phenomena are
*constructed into a target* — the exact timestamps, rolling windows, and
train/OOS boundary handling — is safe for a future model to learn from without
being handed information it should not have.

## §2 Phase 78 context

| | V2 | V1 |
|---|---|---|
| Name | High-volatility regime persistence | Compression-duration → range expansion |
| Timeframes carried forward | 15m, 1h (both — 12/12 cells `ML_TARGET_READY`) | **15m only** — Phase 78 did not find this universal on 1h and Phase 79 does not extend it without independent justification |
| Directional? | No — probability target | No — magnitude target |
| Phase 78 classification | `ML_TARGET_READY` | `ML_TARGET_READY` |

Both are carried forward with their Phase 78 event/target definitions
**unchanged** — Phase 79 formalizes and audits them, it does not redefine them.

## §3 Architecture note — what was reused and why

Before writing any new code, the full Phase 76 → 78 chain, the bootstrap/
multiple-testing/cross-year/cross-asset machinery, the holdout protection, the
data loaders, timestamp conventions, ATR implementations, existing MTF engine,
existing ML infrastructure, backtester and API/test architecture were inspected
(§0 of the master prompt). Findings:

- **Canonical market-data source**: `historical_data_store.get_candles()` (MT5
  candles only — non-`mt5`-sourced rows are dropped by `phase76_event_study.
  load_bars`, unchanged).
- **Canonical timestamp convention**: `historical_data_store` already defines a
  bar's `time` field as its **open** time and its close as
  `open_time + timeframe_seconds`, and its own `get_candles(as_of=...)` already
  truncates on that close time as the look-ahead boundary. Phase 79's target
  specifications (§7/§8) reuse this exact convention rather than inventing a
  new one: `prediction_timestamp = open_time(event_bar) + timeframe_seconds`.
- **Canonical ATR implementation**: `phase76_event_study.load_bars`'s 14-bar
  rolling true-range mean (`atr`), and its stable variant `atr_ret_stable`,
  and Phase 78's `atr_stable` (trailing-200-bar mean of `atr`, unconditioned) —
  all reused unchanged.
- **Canonical event indexing convention**: `phase78_market_behavior_discovery_ii.
  _b_vol_bucket_high` (V2) and `_b_compression_duration` (V1) — reused
  unchanged; Phase 79 does not redefine either event.
- **Canonical train/dev/OOS split logic**: `phase76_event_study._DEV_RATIO`
  (chronological 70/30 on bar index) — reused unchanged, plus a NEW
  purge/embargo check (§11) that Phase 76/77/78 did not need to perform (their
  horizons are short enough, and their reported effect sizes large enough,
  that boundary contamination was never separately quantified).
- **Canonical holdout protection**: the frozen Phase-74/Gold contract hash
  (`xauusd_market_conditions.FROZEN_CONTRACT_HASH`) is checked before and
  after, unchanged; no holdout data (`gold_strategy_baseline`'s locked N=82
  historical baseline) is read, imported, or referenced.
- **Existing MTF engine** (`strategies/mtf_engine.py`, `true_mtf_engine.py`):
  inspected. Not reused, and not applicable — V1/V2 are each defined on a
  SINGLE timeframe (15m or 1h), never blending features from one timeframe
  into a study on another. §12 below documents this explicitly as
  `NOT_APPLICABLE` rather than silently skipping it.
- **Existing ML infrastructure** (`ml_trainer.py`): inspected and explicitly
  **not reused**. It is a separate, pre-existing subsystem that trains a
  `RandomForestClassifier` on the user's own trade-journal history plus
  `yfinance` daily indicators to power a personal AI-analysis feature
  (`ai_analysis.py`) — a different purpose, different data, different
  pipeline than the MT5 read-only research chain this phase continues. Phase
  79 does not import `sklearn` or touch this module; see
  `test_no_ml_training_in_module`.
- **Existing backtester**: none of Phase 76-78's event-study framework is a
  backtester (no position/order/PnL simulation) and neither is Phase 79 — it
  remains a statistics-on-arrays framework, consistent with the prior phases.
- **Existing feature/target schema**: none existed prior to Phase 79. The
  `TargetSpec` dataclass (§7) is new, modeled directly on the `Hypothesis78`
  dataclass pattern already established in `phase78_market_behavior_discovery_ii.py`.

New code added by Phase 79 is therefore limited to: (1) the two formal,
versioned `TargetSpec` records; (2) temporal-metadata materialization for
audit purposes (`materialize_target_rows`); (3) the leakage / overlap / purge /
null-decoupling / cross-asset / cross-year audits themselves, none of which
existed before this phase.

## §4 V2 target definition (formal specification, `V2-target-v1`)

| Field | Value |
|---|---|
| Event definition | Any bar `i` whose trailing realized-vol percentile rank (4-bar log-return std, ranked over the trailing 200 bars) is `> 0.66` — the HIGH bucket (`_b_vol_bucket_high`, unchanged) |
| Feature timestamp | `close(event_bar)` = `open_time(i) + timeframe_seconds` |
| Prediction timestamp | identical to feature timestamp (both are the instant `rv_rank[i]` first becomes knowable) |
| Target start | = prediction timestamp |
| Target end | `close(event_bar + h)`, h ∈ {1,2,4,8} bars |
| Label | `1.0` if `rv_rank[i+h] > 0.66` else `0.0` |
| Scored effect | `label − P(rv_rank[·+h] > 0.66)` unconditionally over the same slice (baseline-centred) |
| Minimum data | `i ≥ 200` (warm-up); `i + max(h) < len(df)`; `n_events ≥ 20` for a bootstrap CI, `≥ 200` for the gate |
| Invalid/missing | non-finite `rv_rank` at event time, or a target beyond series end → dropped, never imputed |
| Overlapping labels | HIGH-vol bars cluster in runs; consecutive events' target windows overlap heavily at short `h` — quantified in §10, not treated as i.i.d. |

## §5 V1 target definition (formal specification, `V1-target-v1`)

| Field | Value |
|---|---|
| Event definition | The bar that FIRST reaches 3 CONSECUTIVE bars with ATR percentile rank ≤ 0.10 (`_b_compression_duration`, unchanged) |
| Feature timestamp | `close(event_bar)` |
| Prediction timestamp | identical to feature timestamp |
| Target start | = prediction timestamp |
| Target end | `close(event_bar + h)`, h ∈ {1,2,4,8} bars |
| Label | `true_range_sum(i+1..i+h) / (atr_stable[i] · h) − 1` |
| Scored effect | label − the SAME ratio's unconditional mean over every valid bar in the slice (baseline-centred) |
| Denominator | `atr_stable` = trailing-200-bar **mean of ATR(14)**, NOT the event-time ATR — re-verified adversarially in §14 |
| Minimum data | `i ≥ 200`; `i + max(h) < len(df)`; `n_events ≥ 20` / `≥ 200` as above |
| Invalid/missing | non-finite/non-positive `atr_stable` at event time, or target beyond series end → dropped |
| Overlapping labels | compression runs cluster, and the true-range-sum window itself overlaps for nearby events — quantified in §10 |
| Restriction | **15m only** (§2) |

## §6 Feature/target temporal semantics

For prediction timestamp `t`: `FEATURES(t)` depend only on information ≤ `t`;
`TARGET(t)` depends only on information > `t`, and that future information
never enters the feature set. Verified via `audit_timestamp_ordering`
(materialized per-event tables) plus the functional future-shock (§13) and
past-shift (§13) regression tests — the timestamp arithmetic is necessary but
not sufficient evidence; the functional tests are the actual proof.

## §7 Rolling-window analysis

Every rolling operation feeding V1/V2 (`load_bars`, `augment`,
`study_range_expansion`, `study_persistence`, `_b_vol_bucket_high`,
`_b_compression_duration`) was statically scanned (`audit_rolling_windows`)
for `center=True`, negative (forward) `.shift()`, or `bfill`. Result:
**all clean, zero hits** (see results block). The scanner's ability to catch a
genuine bad pattern was verified with injected examples
(`test_leakage_pattern_scanner_detects_injected_bad_patterns`).

## §8 Overlap analysis

Headline instrument shown (XAUUSD 15m); the pattern is representative of all
6 instruments.

**V2 (dev N = 23,716 HIGH-vol events)** — HIGH-vol bars cluster tightly:

| h | % neighboring pairs overlapping | avg overlap (bars) | effective N | effective N / raw N |
|---|---|---|---|---|
| 1 | 0.0% | 0.0 | 23,716.0 | 1.000 |
| 2 | 77.7% | 0.78 | 23,716.0 | 1.000 |
| 4 | 85.4% | 2.46 | 17,442.2 | 0.735 |
| 8 | 91.0% | 6.02 | 8,721.1 | 0.368 |

**V1 (dev N = 689 compression-duration events)** — events are structurally
much rarer (a bar must be the FIRST of 3 consecutive compressed bars), so gaps
between events (~101 bars average) dwarf even the largest horizon:

| h | % neighboring pairs overlapping | effective N | effective N / raw N |
|---|---|---|---|
| 1 | 0.0% | 689.0 | 1.000 |
| 4 | 0.0% | 689.0 | 1.000 |
| 8 | 2.6% | 689.0 | 1.000 |

**Conclusion**: V2's raw event counts at h≥4 substantially OVERSTATE
independent evidence (effective N is 37-74% of raw N by h=8) — this is exactly
why the block-bootstrap (block=h) is the correct tool, not an i.i.d. CI, and
why the reported dev/OOS z-scores should be read as block-bootstrap-adjusted,
not naive-i.i.d. V1's rarer, well-spaced events are close to independent even
at h=8.

## §9 Purge/embargo analysis

For every (instrument, timeframe, horizon) cell in both V2 and V1, the number
of DEV events whose target window (`event_idx + h`) reads at or past the
70/30 chronological split boundary was counted directly.

**Result: zero crossings at every horizon, for every cell.** E.g. XAUUSD 15m
V2 (dev N = 23,716): `h1`/`h2`/`h4`/`h8` all show `n_crossing_boundary = 0`.
Same for V1. `purge_required = False` everywhere; `purge_dev_indices` was
still exercised end-to-end (recomputing the dev headline statistic on the
purged set) as a live regression check, not just a dry count —
`purge_impact_on_headline_mean = 0.0` for both targets, confirming purging (a
no-op here) changes nothing. This makes sense structurally: the split
boundary sits deep inside a multi-year series and `h ≤ 8` bars is a tiny
window relative to it; boundary contamination would only be a live concern
for a much larger horizon or a much smaller dataset. Documented rather than
assumed.

## §10 ATR normalization audit

Two dedicated adversarial tests re-verify, independently of Phase 78's own
regression test, that `atr_stable` cannot be contaminated by the very
compression event it is meant to measure against:

1. **Synthetic-compression test** (`check_stable_atr_not_contaminated_by_compression`):
   a random walk with an artificially frozen (near-zero range AND flat close)
   segment inserted. `atr_stable` before the segment is byte-identical to an
   uncompressed control (it cannot see a future compression), and at the first
   qualifying event bar the spot `ATR(14)` visibly collapses while
   `atr_stable` (a 200-bar trailing mean) drifts by a fraction of a percent.
2. **Future-shock-on-the-denominator test**
   (`check_future_bar_does_not_change_stable_atr_at_t`): inserting a huge
   artificial future bar leaves `atr_stable[t]` exactly unchanged.

**Results** (synthetic random walk, 3000 bars, a 20-bar frozen-price
compression segment inserted at bar 2000):

| Check | Result |
|---|---|
| `atr_stable` before the compression segment vs. an uncompressed control | byte-identical |
| Spot `ATR(14)` relative drop at the first qualifying event bar | 16.3% (visible collapse — the theoretical ceiling at 3/14 compressed bars is ~21%) |
| `atr_stable` relative drift at the same bar | 0.23% (essentially flat) |
| 50x future-shock bar's effect on `atr_stable[t]` | `0.266008228241491` before == `0.266008228241491` after (exact) |

**Conclusion: `atr_stable` re-confirmed clean.** The exact bug class Phase 78
fixed (denominator depressed by the event it's supposed to normalize against)
does not recur — the spot ATR visibly reacts to the compression while the
200-bar trailing mean used as the actual denominator does not.

## §11 MTF audit

**NOT APPLICABLE.** V1 and V2 are each defined on a single timeframe (15m or
1h) using only that timeframe's own bars — no feature is ever computed on one
timeframe and consumed on another. `strategies/mtf_engine.py` /
`true_mtf_engine.py`'s closed-vs-forming-candle distinction is therefore not a
risk surface for these two targets. Documented explicitly rather than silently
skipped, per §12 of the master prompt.

## §12 Timezone/session audit

All timestamps are UTC end-to-end: `historical_data_store` stores epoch
seconds; `phase76_event_study.load_bars` converts via
`pd.to_datetime(..., unit="s", utc=True)`; Phase 79's materialized tables use
`pd.Timestamp(..., tz="UTC")`. UTC has no daylight-saving transitions, so no
DST-boundary risk exists in the stored timestamps themselves (session labels
such as `LONDON`/`NEW_YORK` are descriptive UTC-hour buckets, not local time —
unchanged from Phase 76). Weekend/holiday calendar gaps are real and were the
source of one bug caught during Phase 79 itself (§19).

## §13 Null controls, functional leakage tests, and label-shuffle degeneracy

Four adversarial regression tests plus two decoupling controls:

- **Future-shock invariance** — two datasets identical through a cutoff,
  differing only strictly after it; every causal feature at or before the
  cutoff must be byte-identical.
- **Past-shift decoupling** — perturbing only the bars inside the horizon
  window after an event must leave every feature at/through the event
  unchanged while the target (which genuinely depends on that future) changes.
- **Placebo/null control** (`_placebo_effect`, unchanged from Phase 78) — a
  matched-count random event set, decoupling the qualifying condition from
  the outcome.
- **Time-shift control** (new, §18) — the *same* target machinery evaluated at
  `idx + shift_bars` instead of `idx`, for shift ∈ {1,2,4,8}; a genuine effect
  should weaken as the shift grows.
- **Label-shuffle "control" — a documented mathematical degeneracy, not a
  gate.** Permuting an already-computed, fixed set of per-event effect values
  cannot change their arithmetic mean (permutation invariance of the sample
  mean); only the block-bootstrap standard error moves (down, since shuffling
  destroys the serial correlation the block length compensates for), which
  can even *raise* the apparent z-score. This was discovered empirically
  during Phase 79 (see §19) before being written up as a limitation rather
  than silently used as a pass/fail check. The placebo and time-shift controls
  above are the actual condition→outcome decoupling evidence used by the gate.

**Results (XAUUSD 15m headline cell, representative of all 6 instruments):**

| Control | V2 | V1 |
|---|---|---|
| Real effect (dev) | z=30.5, mean=+0.143, POSITIVE | z=-25.5, mean=-0.359, NEGATIVE |
| Placebo (random, condition-decoupled events) | z=0.59, mean=+0.002, **ZERO_CROSSING** | z=-0.84, mean=-0.017, **ZERO_CROSSING** |
| Time-shift +1 bar | z=27.1 | z=-20.5 |
| Time-shift +2 bars | z=24.2 | z=-17.8 |
| Time-shift +4 bars | z=19.3 | z=-15.0 |
| Time-shift +8 bars | z=7.2 | z=-8.8 |
| Naive label shuffle (documented degeneracy) | mean 0.143474 -> 0.143474 (unchanged); z 29.9 -> 44.4 | mean -0.358864 -> -0.358864 (unchanged); z -25.6 -> -28.9 |

The placebo control collapses BOTH targets' effects to statistical noise
(|z| < 1, `ZERO_CROSSING`) even though it draws the SAME NUMBER of events as
the real study — direct evidence that the effect requires the true
qualifying condition, not merely "any 23,716 (or 689) bars in this series."
The time-shift control shows a clean, monotonic decay in both targets as the
event trigger is moved away from its true position, most pronounced by
shift=8 (V2: 30.5 -> 7.2; V1: 25.5 -> 8.8) — both fully consistent with a
genuine, decaying, condition-dependent effect rather than a pipeline
artifact. The label-shuffle numbers make the documented degeneracy (§13, §19)
concrete: the mean is bit-for-bit unchanged by permutation in both cases,
while the z-score moves in the WRONG direction for a "does shuffling destroy
the signal" reading — exactly why this diagnostic is not used as a gate
criterion.

## §14 Baseline comparisons

**V2**: unconditional baseline P(HIGH at h) = 0.339; conditional P(HIGH at h |
currently HIGH) = 0.483; measured effect = +0.143; majority-class baseline
accuracy = 0.661 (i.e. "always predict NOT-HIGH" is right 66.1% of the time
unconditionally). **Interpretation, stated plainly**: the entire information
content of this target IS a persistence effect — "currently HIGH" beats the
unconditional base rate at predicting "still HIGH" by 14.3 percentage points.
Whether a future ML model can add anything BEYOND this naive persistence
signal (e.g., via additional features that discriminate WHICH high-vol
episodes persist longer) is untested — that is a model-training question,
explicitly out of scope for Phase 79.

**V1**: the baseline-centred design makes "predict zero excess expansion"
(0.0) the naive baseline by construction; the unconditional ratio itself is
+0.012 (bars are on average very slightly above their stable-ATR-implied
range) while the conditional (post-compression) ratio is -0.347 — i.e.
compression-duration predicts LESS range than the unconditional rate, not
more (confirming Phase 76's H7 finding that compression persists rather than
immediately releasing into expansion). Measured effect = -0.359.

## §15 Effective sample size

Reported per horizon inside the overlap analysis (§8) as
`effective_n_estimate` — a deliberately simple approximation
(`n × avg_gap / max(avg_gap, h)`), not a rigorous Newey-West estimator. Raw
event counts (tens of thousands) are explicitly NOT interpreted as that many
independent experiments.

## §16 Cross-asset analysis

Leave-one-instrument-out (`leave_one_asset_out`), reusing Phase 78's own
per-instrument dev-mean signs: for every instrument held out in turn, does the
remaining 5-instrument majority sign still agree?

**Result: universal for both targets.** Holding out ANY single one of the 6
instruments (AUDJPY, EURUSD, GBPJPY, GBPUSD, USDJPY, XAUUSD) in turn, the
remaining 5 agree on sign 100% of the time — for V2 (all positive) and for V1
(all negative). Neither finding is a single-instrument artifact wearing a
"universal" label.

## §17 Cross-year analysis

Chronological early/mid/late thirds BY YEAR (not by row count), computed from
freshly re-derived dev event rows (not shuffled).

**XAUUSD 15m (representative):**

| Target | early (2022-2023) | mid (2024) | late (2025) | Sign stable? |
|---|---|---|---|---|
| V2 | N=12,344, mean=+0.147, POSITIVE | N=8,040, mean=+0.144, POSITIVE | N=3,332, mean=+0.129, POSITIVE | **Yes** |
| V1 | N=351, mean=-0.383, NEGATIVE | N=237, mean=-0.377, NEGATIVE | N=101, mean=-0.233, NEGATIVE | **Yes** |

Both effects are remarkably STABLE in magnitude across three multi-year
periods (V2: 0.147→0.144→0.129; V1: -0.38→-0.38→-0.23), not just
sign-consistent — this is a stronger result than the gate strictly requires.

## §18 Determinism

Two levels were checked:

1. **Audit layer** (static rolling-window scan + all four adversarial checks),
   re-run in-process twice per `run()` call: `audit_layer_hash_a ==
   audit_layer_hash_b == 665c67e20c5fe467` — match.
2. **Full pipeline**, run as three independent OS processes end-to-end
   (`python -m phase79_ml_target_integrity`, ~170-200s each): the second and
   third full runs produced **byte-identical** `content_hash =
   204861037aa93b15c92172ef865cd82e23ef5aa53866615055eda5fbb113be89` — full
   determinism confirmed across independent process invocations, not merely
   within one process. (The FIRST run is excluded from this comparison
   because it used the pre-fix timestamp audit, §19 — it is not a
   determinism failure, it is a different, since-corrected code version.)

## §19 Two bugs caught and fixed during Phase 79 itself

In the spirit of Phase 76/78's own discipline of not trusting a "too clean" or
"too broken" result at face value:

1. **Timestamp-audit false positive on real (non-synthetic) data.** The first
   full run flagged `target_end_minus_prediction_equals_horizon_seconds` as
   failing for 5 of 6 instruments (only USDJPY passed). Root cause: the check
   asserted exact equality between elapsed wall-clock time and
   `horizon_bars × timeframe_seconds`, which holds only for a perfectly
   regular bar series (true of the synthetic test fixtures, false for real
   MT5 data, which has ordinary weekend/holiday calendar gaps between
   consecutive bars). This was **not** a leakage bug — `target_end >
   prediction` held for every row — it was an overly strict audit assertion.
   Fixed by relaxing the check to a lower bound
   (`gap_seconds ≥ horizon_bars × timeframe_seconds`), which is the actually
   correct invariant; re-run confirmed the fix. A synthetic-data-only test
   suite would never have caught this — it required running on real data,
   which is why the master prompt insists the research run itself is part of
   the deliverable.
2. **Label-shuffle degeneracy** (§13) — discovered by literally running the
   naive shuffle on real V2 data and observing the z-score *increase* rather
   than collapse. Diagnosed as permutation invariance of the sample mean
   (a mathematical certainty, not a bug to "fix"), and written up as a
   limitation rather than forced into a misleading pass/fail result.

## §20 Tests

`tests/test_phase79_ml_target_integrity.py` — **42 new tests, all passing**:
target-registry shape/versioning, no-third-target, timestamp-ordering audit
(pass case + an intentionally broken table to prove the detector isn't
vacuous), rolling-window static scan (clean on real modules + injected-bad-
pattern detection), future-shock invariance (+ a control proving the
comparison itself would catch a genuinely leaky column), past-shift
decoupling, the stable-ATR adversarial suite, overlap-stats shrink/no-overlap
cases, purge/embargo boundary-crossing detection, label-shuffle
permutation-invariance, time-shift weakening, baseline-comparison shapes,
leave-one-out universal/non-universal cases, cross-year period-split
states, the integrity gate's three outcomes (all-pass / hard-fail-rejects /
soft-fail-downgrades / all-fail-rejects), no-ML-training, holdout firewall,
frozen-hash/safety-flags, no-execution-imports, module-import cleanliness,
and audit-layer determinism.

**Full regression**: `pytest tests/ -p no:randomly` → **1578 passed, 6
skipped, 0 failed** (1536 passed pre-Phase-79 + 42 new Phase 79 tests; no
regressions in any existing suite).

**Frontend**: `npx tsc --noEmit` → exit 0. `npm run build` → exit 0, built in
2.11s. No frontend page was added — consistent with Phase 76/77/78 precedent
(none of those research phases has a dedicated frontend page either; §32 of
the master prompt explicitly discourages a UI added merely for its own sake).

## §21 Holdout verification

| | Value |
|---|---|
| Before Phase 79 | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` |
| After Phase 79 | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` |
| Result | **MATCH** |

No holdout data (the locked N=82 historical baseline in
`gold_strategy_baseline.HistoricalVsForwardComparator.LOCKED_HISTORICAL_BASELINE`)
was read, imported, queried, or referenced anywhere in
`phase79_ml_target_integrity.py`, verified by both static source inspection
(`test_frozen_holdout_never_accessed`) and by never once importing
`xauusd_forward_accumulation`, `xauusd_forward_validator`, or
`xauusd_forward_lifecycle` outside the one safety-flag check.

## §22 Safety verification

| Flag | Value |
|---|---|
| `xauusd_market_conditions.FROZEN_CONTRACT_HASH` | unchanged (§21) |
| `ForwardExecutionLifecycleEngine.LIVE_AUTOMATION_ENABLED` | `False` |
| `ForwardExecutionLifecycleEngine.LIVE_BROKER_TRANSMISSION` | `"BLOCKED"` |
| Execution/broker/risk/reconciliation imports in Phase 79 code | none (`test_no_execution_or_broker_imports`) |
| ML/DL training libraries imported | none — no `sklearn`, `tensorflow`, `torch`, `xgboost`, `lightgbm`, no `.fit(`/`.predict(` calls (`test_no_ml_training_in_module`) |
| Credentials / API keys / secrets added | none |
| Risk limits changed | none |
| New API endpoints | `GET /api/research/ml-target-integrity` only — read-only, mirrors the existing Phase 76-78 pattern; `POST` is not defined (405 by FastAPI default) |

## §23 Final verdict

| Target | Verdict | Failing checks |
|---|---|---|
| **V2** (high-volatility regime persistence) | **`TARGET_INTEGRITY_READY`** | none |
| **V1** (15m compression-duration → range expansion) | **`TARGET_INTEGRITY_READY`** | none |

Both targets passed all 8 hard checks (timestamp ordering, rolling-window
static scan, future-shock invariance, past-shift decoupling, stable-
denominator non-contamination, placebo-control decoupling, full-pipeline
determinism, holdout untouched) AND all 4 soft checks (time-shift decay,
negligible purge impact, universal leave-one-out, cross-year period
stability) — no forced pass, no downgrade required. This was not
predetermined: the FIRST full run genuinely returned `TARGET_REJECTED` for
both (§19), and only advanced to `TARGET_INTEGRITY_READY` after a real bug in
the audit code itself (not in the targets) was found and fixed.

## §24 Phase 80 recommendation

Per §36 of the master prompt, V2 is prioritized ahead of V1 (12/12 cell
coverage across both timeframes vs. V1's 15m-only scope, and a materially
larger, more strongly-decaying placebo/time-shift decoupling margin):

1. **ML VOLATILITY REGIME PREDICTION PILOT** (V2, `V2-target-v1`) — build the
   `V2_HIGH_VOL_REGIME_PERSISTENCE` target column end-to-end with strict
   chronological train/OOS separation; feature-engineering and a repeat
   leakage audit on any NEW feature added beyond `rv_rank` itself; explicitly
   test whether additional features add anything beyond the naive-persistence
   baseline established in §14. **No model training in the pilot's first
   phase.**
2. **15M COMPRESSION/EXPANSION ML PILOT** (V1, `V1-target-v1`) — same
   structure, restricted to 15m, for `V1_COMPRESSION_DURATION_RANGE_EXPANSION`.

No third item. No directional target exists to hand to any future
strategy-development phase — that chain (Market behavior → Statistical
evidence → OOS replication → Target integrity → Leakage-free ML target →
future ML model experiment → OOS predictive value → trading strategy
integration → backtesting → walk-forward → Monte Carlo → paper trading →
live) remains exactly where Phase 78 left it for direction: stopped at
"Target integrity", with the honest caveat that both integrity-ready targets
are non-directional forecasting problems, not the input to a buy/sell
strategy.
