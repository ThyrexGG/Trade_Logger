# Phase 81 — V2 Incremental Information / Context Decomposition

**Status: COMPLETE.** A research-integrity phase, not a strategy phase and
not another attempt to maximize predictive performance.

**Final verdict: `V2_EXPLAINED_BY_TIME_AND_VOLATILITY`.** The full-context
model's AUC advantage over "volatility state + time/session" alone is tiny
(+0.009 pooled, block-bootstrap CI [0.008, 0.011] — statistically
distinguishable from zero but well below the 0.05 margin used everywhere
else in this pipeline for "material"), and fails the population-matched
placebo margin (Gate H). V2 remains a real, reproducible, well-calibrated,
cross-asset/cross-year-stable phenomenon — it is just explained almost
entirely by two already-understood ingredients (how deep the current
volatility state is, and what time of day/session it is), not by a new,
validated form of short-horizon predictive structure.

## 1. Executive summary

A nested decomposition (constant → current-state → volatility → time/session
→ +price → +candle+regime) of Phase 78/79's V2 target shows: (1) the literal
binary "current-state" feature is degenerate (AUC=0.5, zero variance, by
construction of the V2 event definition); (2) volatility state alone
(`rv_rank` + related) reaches AUC 0.630; (3) time/session alone (cyclic hour
+ day-of-week + session) reaches AUC 0.648 — nearly as much as volatility
alone, from purely deterministic calendar information; (4) volatility+time
together reach AUC 0.687; (5) adding price, candle, and regime context lifts
this only to AUC 0.697 — a **+0.009 pooled AUC gain**, bootstrap-CI-positive
but below the 0.05 "material" threshold used throughout this research
program, and not distinguishable from the population-matched placebo by that
same margin. Time is NOT merely a proxy for volatility (its effect on target
rate persists almost undiminished within fixed volatility buckets), but
volatility and time TOGETHER already explain nearly all of what a full
21-feature model can achieve. **Verdict: V2_EXPLAINED_BY_TIME_AND_VOLATILITY.
V1 decision: NO — do not proceed to further ML development on V2.**

## 2. Research question

Does the Phase 78 V2 high-volatility-regime-persistence phenomenon contain
predictive information beyond (a) current volatility state and (b)
deterministic intraday/session structure? This is deliberately narrower and
harder than Phase 80's question ("does ML add value") — it asks WHERE any
such value actually comes from.

## 3. Why Phase 80 required this investigation

Phase 80 trained real ML models on V2 and found: (1) a naive
population-decoupled placebo control scored HIGHER than the real result
(0.727 vs 0.697) — traced to a population-breadth confound, not a leak; (2)
the corrected, population-MATCHED placebo showed the full model's AUC
advantage over a trivial current-state model surviving only marginally
(+0.032) when the true short-horizon timing was broken; (3) permutation
importance showed `hour`-of-day dominating every other feature, including
`rv_rank` itself. Phase 80 concluded `TARGET_PREDICTABLE_BUT_NO_INCREMENTAL_
ML_VALUE` but could not say WHICH information (volatility state vs. session
timing vs. genuinely new structure) explained the predictability. Phase 81
answers that directly with an interpretable nested decomposition.

## 4. Exact V2 target — reused verbatim

Unchanged from Phase 78/79/80: event = any bar with trailing realized-vol
percentile rank (`rv_rank`) `> 0.66`; target = `rv_rank[event_idx + h] >
0.66`. Target version `V2-target-v1`. Not redefined anywhere in this phase.

## 5. Dataset

| | 15m | 1h |
|---|---|---|
| h=1 | 203,410 | — |
| h=2 | 203,408 | — |
| h=4 (headline) | 203,401 | 121,022 |
| h=8 | 203,378 | — |
| Positive rate (h=4) | 0.481 | ~0.42 |

6 instruments (XAUUSD, USDJPY, EURUSD, GBPJPY, GBPUSD, AUDJPY), unchanged
universe — reused via `phase80_ml_volatility_regime.build_pooled_dataset`,
which itself reuses `build_dataset`, `load_bars`, and `augment` verbatim
from Phases 76/78/80.

## 6. Feature groups

Phase 81 uses a DIFFERENT grouping from Phase 80's (organised by conceptual
role in the decomposition, not by measurement type):

| Group | Features | Role |
|---|---|---|
| CURRENT_STATE | `current_high_flag` | Literal binary "is this bar HIGH" — degenerate (constant) by construction, included to demonstrate rather than merely assert this |
| VOLATILITY | `rv_rank`, `regime_high_duration`, `atr_ret`, `atr_rank`, `rv`, `rv_change_1`, `atr_rank_change_1` | Continuous/ordinal volatility-level and volatility-regime-depth measures |
| TIME | `hour_sin`, `hour_cos`, `dow`, `session_code` | Deterministic intraday/weekly/session structure. `hour_sin`/`hour_cos` are NEW (cyclic encoding of the existing causal `hour` column, avoiding the artificial 23→0 discontinuity a raw integer hour creates) |
| PRICE | `ret_1`, `ret_4`, `ret_8`, `abs_ret_1`, `ret_sign_1` | Unchanged from Phase 80 |
| CANDLE | `body_range_ratio`, `upper_wick_ratio`, `lower_wick_ratio`, `tr_atr` | Unchanged from Phase 80 |
| REGIME | `regime_code` | Phase 76's TRENDING/RANGING/MIXED classification — a DIFFERENT "regime" concept from volatility-regime-depth, kept separate |

`regime_high_duration` moved from Phase 80's "REGIME" bucket into VOLATILITY
here — it measures how long the volatility state has been HIGH, which is
conceptually a volatility-depth measure, not a directional-trend regime
(Phase 76's `regime_code`, which stayed in its own bucket).

## 7. Nested model design

Headline (15m, h=4, fold 3 / 2025 H2 onward test period, N_test=59,449):

| Model | Features | LR AUC | HGB AUC (reference) |
|---|---|---|---|
| M0 — constant | 0 | 0.500 | 0.500 |
| M1 — current state | 1 (degenerate) | 0.500 | 0.500 |
| M2 — volatility | 7 | 0.625 | 0.630 |
| M3 — time/session | 4 | 0.586 | 0.648 |
| M4 — volatility + time | 11 | 0.637 | 0.687 |
| M5 — + price | 16 | 0.640 | 0.694 |
| M6 — full (+candle +regime) | 21 | 0.655 | 0.697 |

M1 (current state) is confirmed degenerate: the single feature
(`current_high_flag`) has zero variance in this dataset by construction of
the V2 event definition itself (every row already satisfies `rv_rank >
0.66`), so the fitted model reduces to an intercept, AUC exactly 0.5 —
demonstrated empirically (`test_model1_current_state_degenerates_to_
constant`), not merely asserted. Extended ablation (isolating candle's and
regime's own marginal contribution, HGB): D (time+vol+candle, no price) =
0.692; E (time+vol+regime, no price/candle) = 0.688 — regime_code adds
almost nothing on its own (0.687→0.688), candle features add a little more
(0.687→0.692), consistent with the roughly-additive price+candle+regime
contributions summing to M6's total lift over M4.

## 8. Time-of-day analysis

Is `hour` a volatility proxy, or does it carry independent information?
Unconditional spread (std) of `P(target=1)` across hours = **0.131**. When
the SAME hour-by-hour spread is computed WITHIN each fixed volatility bucket
(so volatility level is held constant), the spread barely shrinks — and in
the lowest bucket it is even slightly LARGER:

| Volatility bucket | Within-bucket hour-spread (std) |
|---|---|
| 0.66-0.75 | 0.140 |
| 0.75-0.85 | 0.136 |
| 0.85-0.95 | 0.124 |
| 0.95-1.00 | 0.092 |

(unconditional spread: 0.131). **Conclusion: hour is NOT primarily acting as
a volatility-level proxy** — its relationship with future persistence
survives almost undiminished once the current volatility level is already
known, meaning session/time-of-day structure carries genuinely independent
predictive content (consistent with Andersen-Bollerslev 1997's deterministic
intraday-seasonality mechanism, distinct from — not merely a stand-in for —
volatility-clustering itself).

## 9. Volatility-state analysis

The continuous `rv_rank` value shows a clean, monotonic dose-response
relationship with the target — NOT just the binary "is HIGH" fact:

| `rv_rank` bucket | P(target=1) | N |
|---|---|---|
| 0.66-0.75 | 0.389 | 50,845 |
| 0.75-0.85 | 0.433 | 59,194 |
| 0.85-0.95 | 0.513 | 59,471 |
| 0.95-1.00 | 0.646 | 33,891 |

Confirms directly that "how extremely HIGH" (not merely "is currently HIGH")
carries real information — the continuous volatility-state feature is doing
genuine work, distinct from the degenerate binary current-state flag (§7,
Model 1).

## 10. Neutralization methodology

**Time neutralization** (§8 Method A — within-hour centering): for each
(instrument, hour) pair, compute the TRAIN-only mean target rate; subtract
it from the actual target on the evaluation split to get a residual with
(by construction) zero conditional mean per (instrument, hour) cell on
TRAIN. Then test whether VOLATILITY-group features still explain any of
that residual's variance (3-fold CV linear regression R²).

**Volatility neutralization** (§9): symmetric — TRAIN-only mean target rate
per (instrument, FIXED volatility bucket — edges `[0.66, 0.75, 0.85, 0.95,
1.0]`, not data-derived), residual tested against TIME-group features.

Both baselines are computed exclusively on the fold's TRAIN split and
applied to the (disjoint) evaluation split — never fit on the split being
scored.

## 11. Conditional probability results

Overall `P(target=1)` in the event-conditioned population = 0.481. By
volatility bucket: see §9's table (0.389 → 0.646, monotonic). By hour and by
volatility-bucket-crossed-with-hour: computed and stored in the artifact
(`conditional_rates.by_hour`, `.by_session`,
`.by_volatility_bucket_and_hour`), gated by a predeclared minimum-N=200
threshold per cell — no cell below that count is reported, and no cell was
selectively excluded for looking unfavorable.

## 12. OOS methodology

Identical to Phase 80: calendar-YEAR purged walk-forward
(`phase80_ml_volatility_regime.make_folds`/`split_fold`, unchanged) — each
fold's TEST window is a distinct calendar half-year-or-later period
(2023H2/2024H2/2025H2+ for 15m; 2024H2/2025H2+ for 1h), so walk-forward and
cross-year analysis are the same experiment, not two.

## 13. Cross-asset results

Δ(M6 full − M4 volatility+time) AUC, headline fold, per instrument (pooled
model's own rows):

| Instrument | Δ AUC |
|---|---|
| AUDJPY | +0.0139 |
| USDJPY | +0.0138 |
| GBPJPY | +0.0120 |
| GBPUSD | +0.0053 |
| XAUUSD | +0.0055 |
| EURUSD | +0.0030 |

All 6 positive, all small (0.003–0.014) — no instrument shows a materially
larger residual gain than the others; the "full > vol+time" effect is
universally tiny, not concentrated in one asset.

## 14. Cross-year results

| Test period | M4 AUC | M6 AUC | Δ |
|---|---|---|---|
| 2023 H2 | 0.6952 | 0.7111 | +0.0159 |
| 2024 H2 | 0.7047 | 0.7166 | +0.0119 |
| 2025 H2+ | 0.6874 | 0.6966 | +0.0092 |

Consistently small and positive across all three years — not a one-year
artifact, but also never approaching a "material" magnitude in any year.

## 15. Leave-one-out results

Refit on 5 instruments, evaluate on the excluded one (headline fold):

| Held-out instrument | M4 AUC | M6 AUC | Δ |
|---|---|---|---|
| USDJPY | 0.6615 | 0.6769 | +0.0154 |
| AUDJPY | 0.6615 | 0.6762 | +0.0147 |
| GBPJPY | 0.6748 | 0.6817 | +0.0069 |
| GBPUSD | 0.7052 | 0.7088 | +0.0036 |
| XAUUSD | 0.6796 | 0.6829 | +0.0033 |
| EURUSD | 0.7053 | 0.7070 | +0.0017 |

Every single held-out instrument shows the SAME small, positive delta
pattern — the residual "full beats vol+time" effect, tiny as it is,
generalizes to genuinely unseen assets. It does not vanish, but it never
grows large either.

## 16. Horizon results

Full horizon matrix (HGB reference model), Δ(M6−M4) per fold:

| Horizon | Fold 1 (2023H2) | Fold 2 (2024H2) | Fold 3 (2025H2+) |
|---|---|---|---|
| h=1 | +0.0078 | +0.0097 | +0.0114 |
| h=2 | +0.0231 | +0.0200 | +0.0253 |
| h=4 | +0.0159 | +0.0119 | +0.0092 |
| h=8 | +0.0033 | +0.0084 | +0.0058 |

No horizon is selected as "best" — all four are reported. h=2 shows the
largest (still small, 0.02-0.025) delta; h=8 the smallest. No horizon shows
residual information anywhere near the 0.05 material threshold. Absolute
AUC itself is much higher at short horizons regardless of feature set (h=1:
~0.79-0.80; h=8: ~0.69-0.72) — consistent with a decaying persistence effect
that both M4 and M6 track similarly.

## 17. 15m vs 1h

| Timeframe | Fold | M4 AUC | M6 AUC | Δ |
|---|---|---|---|---|
| 1h | 2024 H2 | 0.7074 | 0.7175 | +0.0101 |
| 1h | 2025 H2+ | 0.6920 | 0.7052 | +0.0132 |
| 15m | (h=4, for comparison) | 0.687-0.705 | 0.697-0.717 | +0.009-0.016 |

The same small, consistently positive pattern holds at 1h as at 15m — the
finding is not an artifact of one timeframe's resolution.

## 18. Calibration

Headline M6 (full, HGB) expected calibration error = **0.0286** — low,
comfortably under the 0.15 threshold used in Phase 80. Probability outputs
are usable as approximately calibrated estimates.

## 19. Matched placebo

Phase 80's ORIGINAL placebo control drew random events from the WHOLE
series (`rv_rank` spanning ~0–1), a strictly EASIER population than the
real study's `rv_rank > 0.66` conditioning — confirmed confounded because
its own current-state-only AUC already exceeded the real data's before any
other feature was added. It was replaced with a population-MATCHED
placebo: identical feature rows (same instrument, same `event_idx`, hence
an identical `rv_rank` range), only the target relabelled using the
outcome `shift_bars` further into the future. That corrected methodology
is reused HERE VERBATIM (`phase80_ml_volatility_regime.
population_matched_placebo_targets`'s logic, reimplemented with a small
per-instrument cache for the temporal-shift sweep, §41) — it is not
re-litigated, and the population-decoupled version is not reinstated.

**Results** (headline fold, shift=200 bars, HGB):

| | Real | Matched placebo | Δ (real − placebo) |
|---|---|---|---|
| M4 (volatility+time) | 0.687 | 0.661 | +0.027 |
| M6 (full) | 0.697 | 0.665 | +0.031 |

Both deltas are positive but below the 0.05 material-margin used for Gate H
— **Gate H fails**. This is the central quantitative reason for the
`V2_EXPLAINED_BY_TIME_AND_VOLATILITY` verdict: even after decoupling the
true short-horizon timing, a population-matched placebo retains most of the
real result's AUC, confirming that most of the predictive power is NOT
specific to the true V2 persistence window.

## 20. Shuffled target

AUC = **0.474** (M6, HGB, headline fold) — at or slightly below chance,
confirming no leakage (a properly-behaved pipeline; had this stayed
substantially above 0.5, §18 says STOP).

## 21. Future-shock

PASS — features AND a fitted model's predictions are byte-identical for
events at/before a synthetic cutoff regardless of a 50× future shock
inserted after it (`check_feature_future_shock_invariance`, reused verbatim
from Phase 80).

## 22. Temporal shift

Sweeping the matched-placebo shift from 50 to 2,000 bars (M4, logistic
regression): AUC stays in a narrow 0.60–0.63 band across the ENTIRE sweep,
never decaying toward 0.5 even at a 2,000-bar (~500-hour, ~3-week) shift.
This is itself informative: it shows the matched-placebo's retained signal
is not a short-horizon artifact that would eventually vanish with a large
enough shift — it reflects genuinely slow-moving, persistent structure
(most plausibly instrument/session-level baseline volatility differences),
consistent with the hour-mechanism finding in §8. Treated as a diagnostic,
not a definitive null (§21 of the master prompt).

## 23. Bootstrap

Paired, block-bootstrap (block=4 bars, matching the horizon, reusing the
identical moving-block-resampling principle as
`phase76_event_study.block_bootstrap`) CI for Δ(M6−M4) AUC, headline fold:

```
point = +0.0092
95% CI = [+0.0075, +0.0113]
```

The CI excludes zero — the delta is statistically real, not noise — but its
magnitude (well under 1 AUC point) is explicitly NOT treated as "material"
per the predeclared interpretation rule (§34 of the master prompt): a
narrow, positive CI is not the same claim as an economically/scientifically
substantial effect (§44 "no false precision").

## 24. Feature importance

Reused Phase 80's permutation-importance machinery (labelled explicitly as a
predictive-attribution diagnostic, not causal evidence). Consistent with
Phase 80's own finding: `hour`-derived features and volatility-rank features
dominate; price/candle/regime features contribute comparatively little to
the full model's ranking power, consistent with §7's ablation table showing
D/E (candle-only, regime-only additions) moving AUC by only 0.001-0.005.

## 25. Interpretation

Three separate claims, kept explicitly distinct throughout (§35 of the
master prompt):

1. **"V2 is predictable."** TRUE — established by Phase 78, reconfirmed
   here (M4/M6 AUC 0.69-0.70, stable across years/assets/timeframes).
2. **"ML adds incremental predictive information."** NOT ESTABLISHED beyond
   volatility state + time/session — the residual delta is small, and does
   not clear the population-matched-placebo margin.
3. **"V2 is a useful trading signal."** NOT ADDRESSED and NOT IMPLIED by
   either of the above — no backtest, no PnL, no strategy logic exists
   anywhere in this phase or its predecessors.

Time is not a volatility proxy (§8); volatility carries real continuous
information beyond a binary flag (§9); the two together already explain the
overwhelming majority of what any tested model — linear or nonlinear — can
achieve on this target.

## 26. Gates

| Gate | Result |
|---|---|
| A — Dataset integrity | PASS |
| B — Leakage | PASS |
| C — Reproducibility | PASS (identical content_hash across 2 independent OS-process runs) |
| D — Time-neutralization methodology | PASS |
| E — Volatility-conditioning methodology | PASS |
| F — Cross-asset complete (all 6 evaluated) | PASS |
| G — Cross-year complete (all 3 periods evaluated) | PASS |
| **H — Matched placebo** | **FAIL** (real exceeds placebo by only +0.027 to +0.031, below the 0.05 margin) |
| I — Shuffled target collapses toward chance | PASS (0.474) |
| J — Holdout protected | PASS |

9/10 gates passed; Gate H is the deciding failure, directly driving the
verdict.

## 27. Limitations

- The linear-regression residual-information test (§10) is a simple,
  interpretable tool; it would not detect a purely nonlinear residual
  relationship between volatility/time and the neutralized target. The
  nested HGB comparisons (§7) partially cover this gap (HGB can capture
  nonlinearity directly), and they tell the same story (small residual
  delta), which is reassuring but not a substitute for a dedicated
  nonlinear residual test.
- The temporal-shift sweep (§22) is a diagnostic, not a rigorous null — its
  failure to decay at large shifts is suggestive of slow-moving structure,
  not proof of a specific mechanism.
- `regime_high_duration` was reclassified from Phase 80's "REGIME" group
  into this phase's "VOLATILITY" group — a deliberate, documented boundary
  choice (§6), not a data change.
- The three calendar-year OOS folds (2023/2024/2025) are the same
  boundaries Phase 80 used; no additional years exist in the 15m dataset to
  extend this further.

## 28. Final verdict

**`V2_EXPLAINED_BY_TIME_AND_VOLATILITY`**

V2 remains a genuine, reproducible, cross-asset/cross-year-stable,
well-calibrated phenomenon. It is explained almost entirely by current
volatility depth and deterministic session/time structure, each carrying
independent information; price, candle, and trend-regime context add only a
small, placebo-indistinguishable increment on top. This is a successful,
informative research outcome, not an inconclusive one.

## 29. V1 decision

**NO.** V2 has not produced evidence of scientifically meaningful residual
information beyond time and volatility state, so it does not justify
further ML development. Per the master prompt's explicit instruction, this
does NOT automatically decide V1's fate — V1 (15m compression-duration →
range persistence) was never made contingent on V2's outcome and remains an
independent, separate decision for a future phase, not addressed here.

## 30. Next research recommendation

Treat V2 as a documented, non-ML regime-context phenomenon: `rv_rank`
(continuous) combined with session/hour is already close to the ceiling of
what any tested model achieves, and could in principle serve as a cheap,
fully-understood, deterministic market-state feature or conditioning
variable in some future (non-ML, non-trading) context — but that is a
different kind of proposal than "train a predictive model," and is not
itself recommended as an action item here. No further predictive-modelling
phase is recommended for V2. No third target was opened. No trading
strategy was created or implied anywhere in this phase.
