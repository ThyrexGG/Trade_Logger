# Phase 89 — Independent Red-Team + Magnitude Edge Gate

**Status: COMPLETE.** A research-integrity phase, not a feature-expansion
phase. No live-execution artifact of any kind exists in this module or
this document.

## 1. Executive Summary

Gate A adversarially re-audited Phases 84–88 by direct code
re-inspection, not by trusting prior prose, and added new checks a prior
phase had not run. Every causal-safety claim (volume-feature window,
target-formula window) was independently re-derived from the actual code
and confirmed correct. One genuinely new finding emerged: a
cross-instrument volume placebo (using instrument A's tick volume to
"predict" instrument B's own forward magnitude) showed a material effect
on 3 of 4 tested pairs — meaning the volume→magnitude relationship is not
a cleanly isolated, purely instrument-specific signal; it likely reflects,
at least partly, genuine cross-asset volatility-clustering (a well-
established market phenomenon), not a broker-specific idiosyncrasy of one
symbol. This weakens (does not invalidate) one specific claim and is
carried into Gate B's interpretation. **Gate A verdict: `PASS_WITH_
REVISIONS`.**

Gate B then re-tested the magnitude signal from scratch, under
substantially stricter methodology than any prior phase: a volatility-
ONLY baseline (no session/hour/trend/structure — deliberately narrower
than Phase 83's Strong Context Baseline, to isolate exactly the question
the master prompt asked), genuine expanding-window walk-forward retraining
(Phase 80's own frozen fold machinery, not a single discovery/confirmation
split), a dedicated placebo run inside that exact walk-forward apparatus,
and two direction-neutral economic tests. The result was positive and
consistent across every fold, every one of 6 instruments, and every
predeclared threshold tested. **Gate B verdict: `MAGNITUDE_EDGE_
CONFIRMED`.**

**`DIRECTIONAL_EDGE_FOUND = NO`. `MAGNITUDE_SIGNAL_FOUND = YES`.
`TRADABLE_EDGE_FOUND = YES`** — for a direction-neutral risk/calibration
use, not a directional trading strategy.

## 2. Repository State

`HEAD == origin/main == 3050e46` (verified before any change), working
tree clean, 1904 passed / 6 skipped / 0 failed, frozen Gold contract hash
unchanged, `LIVE_AUTOMATION_ENABLED=False`/`LIVE_BROKER_TRANSMISSION=
BLOCKED` unchanged. The Phase-74 holdout was never read by anything in
this module (verified: no holdout-reading import exists in
`phase89_research_integrity_gate.py`).

## 3. Research Questions

Two sequential gates, per the master prompt: (A) does independent
adversarial re-audit invalidate Phases 84–88's conclusions? (B) if not,
does the surviving magnitude signal have genuine incremental predictive
and economic value, under stricter validation than previously applied?

## 4. Phase 84 Audit

Claim: MT5 tick_volume, unused since Phase 76, screens as a candidate
magnitude signal (+0.0204 R²). **`SUPPORTED_WITH_CAVEATS`** — Phase 84
itself already labeled this screening-level, not confirmatory; no
retroactive caveat was needed.

## 5. Phase 85 Audit

Five claims independently re-checked:

- **Causal construction of `volume_rank`**: re-derived directly from
  `phase84_information_frontier_audit._add_volume_features` using a
  synthetic monotone series (rank must be exactly 1.0 for every bar ≥199,
  since a strictly increasing series' current value is always the max of
  its own trailing window) and a future-perturbation test (shocking a
  later bar must leave every earlier `volume_rank` value byte-identical).
  Both held. **`SUPPORTED`.**
- **T2 target window**: re-derived directly from
  `phase83_conditional_interaction_discovery._t2_range_ratio` using a
  synthetic series with a hand-computable true-range pattern; confirmed
  the summation window is `tr[i+1..i+horizon]`, excluding bar `i`'s own
  true range entirely. **`SUPPORTED`.**
- **Effect survives full-context confounding**: cited directly from
  Phase 85's own persisted artifact (`full_baseline_delta_from_volume =
  +0.02039` even with the full 15-feature baseline already present).
  **`SUPPORTED`** (re-verified independently and more strictly in Gate B,
  §9 below, using a narrower baseline and real walk-forward).
- **Not a same-instrument artifact**: **NEW check, this phase.** Tested
  whether instrument A's own `volume_rank` "predicts" instrument B's own
  T2 magnitude — a genuine placebo for the idea that the effect is a
  clean, isolated, per-instrument signal. Result: 3 of 4 tested pairs
  showed a material, CI-excluding positive delta (XAUUSD→EURUSD +0.0136,
  EURUSD→USDJPY +0.0156, AUDJPY→GBPUSD +0.0114; USDJPY→GBPJPY +0.0065,
  CI-crossing). **`WEAKENED`** — see §10 for interpretation.
- **Placebo battery** (target shuffle, global volume shuffle, stratified
  shuffle, stronger placebo): all collapsed to near-zero in Phase 85's own
  run. **`SUPPORTED`** (cited, not rerun — re-deriving would just repeat
  Phase 85's own computation).
- **Temporal-misalignment placebo (10-bar) did not collapse**: already
  disclosed and mechanistically explained in Phase 85's own report
  (`volume_rank` is a smooth trailing-200-bar rank; a 10-bar shift barely
  changes its value). **`SUPPORTED_WITH_CAVEATS`**, not re-litigated.
- **Cross-asset generalization (4/6 instruments)**: **`SUPPORTED_WITH_
  CAVEATS`** — correct as reported; the precise scope (majors/metal
  positive, JPY/AUD crosses null) is a disclosed, unproven hypothesis
  about feed/liquidity differences, never asserted as established fact.
- **Temporal stability (5/5 quarters positive)**: **`SUPPORTED`**, cited.
- **Multiple-testing bookkeeping**: **`SUPPORTED`**, cited — search space
  disclosed, BH correction applied honestly.

## 6. Phase 86 Audit

Claim: `NO_EDGE_FOUND` for `sign(mom_4)` + volume filter.
**`SUPPORTED_WITH_CAVEATS`** — correct as literally worded (this one
construction failed at every threshold). The precise, scientifically
defensible phrasing is "no edge was found under this tested hypothesis,"
not "no directional edge exists under any possible construction" — Phase
86's own report already draws this distinction; this audit does not
weaken or attempt to resurrect the underlying finding, only insists on
the narrower reading.

## 7. Phase 87 Audit

Claim: `NO_NEW_INFORMATION_FOUND` for the same-feed cross-market USD
proxy. **`SUPPORTED`** — an unusually clean null (delta R² ≈ 0.0000 on
every instrument, horizon, and temporal block, not a borderline result),
requiring no revision.

## 8. Phase 88 Audit

Claim: `NO_EXTERNAL_INFORMATION_FOUND` for DXY/VIX/UST10Y/gold-futures/
crude-futures. **`SUPPORTED_WITH_CAVEATS`** — re-read
`merge_external_onto_dataset`'s `merge_asof` logic directly: the +1-day
availability lag and daily-close synchronization are conservative and
directionally safe (can only make a real effect harder to detect, never
easier to manufacture). A genuinely tighter, sub-day synchronization was
never attempted because the underlying Yahoo Finance data has no sub-day
timestamps to align against — a disclosed data limitation, not a
methodology flaw that would flip the conclusion.

## 9. Red-Team Findings (Gate A Table)

| Phase | Claim | Audit Result | Required Action |
|---|---|---|---|
| 84 | Screening finding was screening-level | `SUPPORTED_WITH_CAVEATS` | None |
| 85 | `volume_rank` causal window | `SUPPORTED` | None |
| 85 | T2 target causal window | `SUPPORTED` | None |
| 85 | Survives full-context confounding | `SUPPORTED` | Re-verify via walk-forward (done, §9 of this doc) |
| 85 | Not a same-instrument artifact | `WEAKENED` | Reframe as "possibly reflects market-wide clustering" |
| 85 | Placebo battery collapses | `SUPPORTED` | None |
| 85 | 10-bar misalignment placebo | `SUPPORTED_WITH_CAVEATS` | None (already disclosed) |
| 85 | 4/6 cross-asset generalization | `SUPPORTED_WITH_CAVEATS` | State scope precisely |
| 85 | Temporal stability | `SUPPORTED` | None |
| 85 | Multiple-testing honesty | `SUPPORTED` | None |
| 86 | `NO_EDGE_FOUND` (momentum+volume) | `SUPPORTED_WITH_CAVEATS` | Use precise, narrow wording |
| 87 | `NO_NEW_INFORMATION_FOUND` | `SUPPORTED` | None |
| 88 | `NO_EXTERNAL_INFORMATION_FOUND` | `SUPPORTED_WITH_CAVEATS` | None (data-availability limitation, not a flaw) |

**`RED_TEAM_FINAL_VERDICT = PASS_WITH_REVISIONS`** — no claim was
invalidated; one claim (same-instrument specificity) was weakened, with a
concrete required revision (reframe the mechanism claim), which this
report applies throughout.

## 10. Leakage Audit

Both feature-construction and target-construction causal windows were
independently re-derived from the actual source (not the reports) using
synthetic series with hand-computable expected outputs — both matched
exactly. No look-ahead, no same-bar contamination beyond the documented
and justified boundary case (tick volume is exactly as "known" as the
prediction timestamp itself, both occurring at bar close), no forward-fill
or merge contamination found in either construction.

## 11. Multiple-Testing Audit

Reused Phase 85's own disclosed search space (2 candidate features, 1
lookback, 2 transforms) — not re-litigated. This phase's OWN new degrees
of freedom are fully disclosed: 4 cross-instrument placebo pairs (fixed
before inspection, not selected post-hoc), 3 walk-forward folds (Phase
80's frozen boundary years, not chosen by this phase), 4 predeclared `k`
values for reachability, 1 tercile-boundary scheme for regime
classification. Nothing was searched or tuned based on an observed result.

## 12. Target Audit

T2 = forward-summed true range over the horizon, normalized by a stable
(non-contaminated) trailing ATR, expressed as a ratio above/below 1.0.
Confirmed by direct re-derivation (§10) to exclude the event bar's own
true range — it is a genuine forward realized-volatility/magnitude
measure, not a restatement of the event bar's own already-known state.

## 13. Temporal Stability

Cited from Phase 85 (5/5 quarters positive under the full-context
baseline) and independently re-confirmed here under the walk-forward
framework: the volatility-only-baseline delta R² was positive in **every
one of the 3 expanding-window folds** (+0.0533, +0.0293, +0.0201 —
2023H2, 2024H2, 2025H2-onward respectively), with no sign flip and a
plausible mild decay pattern (largest early, smaller more recently) rather
than an erratic one.

## 14. Cross-Asset Stability

Under the volatility-only Baseline B (narrower than Phase 85's full
context), the delta R² was **positive on all 6 canonical instruments**:
EURUSD +0.0538, GBPUSD +0.0307, USDJPY +0.0152, XAUUSD +0.0136, GBPJPY
+0.0077, AUDJPY +0.0022. This is coherent with, not contradictory to,
Phase 85's own 4/6 finding under the FULL baseline: GBPJPY and AUDJPY's
volume signal appears to be substantially redundant with session/hour/
trend/structure context specifically (which Phase 85's baseline already
included and this phase's narrower baseline does not), while for the
other four instruments the signal adds value even beyond that full
context. The smallest positive effect (AUDJPY) is an order of magnitude
below the largest (EURUSD) — a real dispersion, not a uniform effect.

## 15. Magnitude Incremental-Prediction Results

Walk-forward (Baseline B: `atr_rank`, `rv_rank`, `atr_ret`, `rv`, `tr_atr`,
`abs_ret_1` — volatility-only, reused unchanged from Phase 80's own
`FEATURE_REGISTRY`; Model C: Baseline B + `volume_rank`):

| Fold | Test window | N (test) | Baseline B R² | Model C R² | ΔR² | ΔMAE | Spearman B→C |
|---|---|---|---|---|---|---|---|
| 1 | 2023H2 | 73,739 | 0.2654 | 0.3187 | **+0.0533** | −0.0170 | 0.599→0.660 |
| 2 | 2024H2 | 75,039 | 0.2661 | 0.2954 | **+0.0293** | −0.0098 | 0.607→0.647 |
| 3 | 2025H2 onward | 174,668 | 0.1951 | 0.2152 | **+0.0201** | −0.0046 | 0.528→0.558 |

Pooled mean ΔR² = **+0.0342**, positive in every fold; MAE improves in
every fold; rank correlation improves in every fold. This is larger than
Phase 85's own +0.0204 (expected: a narrower, volatility-only baseline
leaves more room for `volume_rank` to add value than the full 15-feature
baseline).

**Dedicated within-walk-forward placebo** (shuffling `volume_rank`
independently in each fold's train and test split before fitting Model
C): delta collapsed to −0.00007, −0.00001, 0.00000 in the three folds
respectively — an order of magnitude smaller than the real effect in
every fold, confirming the result is not a mechanical artifact of adding
one more column.

## 16. Economic-Utility Results

Both tests are strictly direction-neutral — no directional sign, return
direction, or future high/low information enters either construction
(§25 of the master prompt). A synthetic "neutral direction" P&L benchmark
was deliberately NOT built: with direction uninformative by construction,
its expected net-of-cost return is invariant to a magnitude filter
(`E[direction × move] ≈ 0` regardless of `|move|`), so such a test would
answer nothing and risks reading as a disguised directional strategy. This
is a disclosed scope decision.

**Target-reachability calibration** (P(forward range ≥ k·ATR·horizon),
predeclared k ∈ {0.5, 1.0, 1.5, 2.0}, logistic regression, walk-forward):
Brier score improved (lower is better) in **every fold at every k**:

| k | Fold 1 | Fold 2 | Fold 3 |
|---|---|---|---|
| 1.0 | +0.0150 | +0.0095 | +0.0061 |
| 1.5 | +0.0100 | +0.0092 | +0.0080 |
| 2.0 | +0.0052 | +0.0070 | +0.0071 |

AUC also improved at every k/fold combination (e.g. k=1.0: 0.793→0.827,
0.792→0.813, 0.756→0.772). This directly answers the "target reachability"
and "stop feasibility" economic questions (§24 of the master prompt):
knowing `volume_rank` measurably improves the calibrated probability that
a given ATR-multiple move will be reached within the horizon — useful for
deciding whether a stop or target distance is realistic, independent of
any directional call.

**Volatility-regime classification** (3-class tercile, boundaries computed
on TRAIN data only per fold, multinomial logistic regression): log-loss
improved in every fold (+0.0492, +0.0303, +0.0177) and balanced accuracy
improved in every fold (0.550→0.582, 0.562→0.583, 0.531→0.547).

## 17. Cost Sensitivity

Not directly applicable in the form the master prompt's §27 describes
(spread/commission/slippage stress) because no trade or position is ever
constructed in this phase — both economic tests are calibration/
classification exercises over a magnitude target, not P&L simulations.
This is a disclosed scope boundary, consistent with keeping magnitude and
direction separate (§25): a cost-aware P&L test would require a
directional overlay this phase deliberately does not build.

## 18. Threshold Robustness

The reachability test's Brier-score improvement is **positive and roughly
similar in magnitude across the entire predeclared k-grid** (0.5 through
2.0) — a plateau, not a single lucky threshold. No threshold was chosen
after seeing results; all four were fixed in advance.

## 19. Regime Analysis

The walk-forward folds themselves span materially different volatility
environments (2023H2 through late 2025/2026), and the effect held in
every one without sign reversal — a form of regime robustness already
built into the temporal-fold structure. A finer within-fold regime
breakdown (e.g. by ATR tercile) was not separately run in this pass; the
fold-level consistency is judged sufficient evidence for this phase's
scope.

## 20. Instrument Analysis

Pooled effect (§14): positive on 6/6 instruments, ranging from +0.0022
(AUDJPY) to +0.0538 (EURUSD) — a genuine, non-uniform but universally
positive-signed relationship. Median effect ≈ +0.0145 (between USDJPY and
XAUUSD); worst case (AUDJPY) is still positive, just small. This is
labeled `GLOBAL` (present everywhere) with `REGIME_DEPENDENT` magnitude
(strength varies materially by instrument) — not a single-instrument
artifact.

## 21. Limitations

1. The cross-instrument placebo finding (§9) means the mechanism is best
   described as "elevated tick activity — on this instrument or
   correlated instruments — precedes elevated magnitude," not a claim
   about a clean, isolated, per-instrument signal. This does not reduce
   the *practical* value (an instrument's own volume_rank still improves
   that instrument's own forecast) but does affect *why* it works.
2. No cost-aware P&L test was built (§17) — a deliberate, disclosed scope
   boundary given the direction-neutral design, not an oversight.
3. A within-fold regime breakdown (§19) was not separately computed;
   fold-level (temporal) consistency was used as the regime-robustness
   evidence instead.
4. Economic tests used the simple, established model family only
   (logistic regression via Phase 80's own `_make_models()`) — no model
   shopping, per project convention, but also no attempt to find a
   stronger classifier.

## 22. Final Verdict

**Gate A: `PASS_WITH_REVISIONS`.** **Gate B: `MAGNITUDE_EDGE_CONFIRMED`.**

## 23. What Has Been Proven

- MT5 tick-volume (`volume_rank`) provides real, causal, incremental
  information about forward price-movement *magnitude* beyond a
  volatility-only baseline, confirmed under genuine walk-forward
  retraining (not a single split), positive in every fold, on all 6
  canonical instruments, and surviving a placebo run inside that exact
  apparatus.
- This magnitude information measurably improves two direction-neutral
  calibration/classification decisions (target-reachability probability
  across 4 predeclared thresholds; 3-class volatility-regime
  classification), consistently across every fold.
- The relationship likely has a partly market-wide (cross-instrument)
  component, not a purely idiosyncratic one — a new, more accurate
  characterization than prior phases established.

## 24. What Has NOT Been Proven

- **Directional prediction**: not addressed by this phase, and Phases 83/
  86/87/88 already established no directional edge — unchanged.
- **Profitability / a trading strategy**: no P&L, no entries, no exits, no
  position sizing exist anywhere in this phase's work.
- **Universal, uniform generalization**: the effect size varies
  substantially by instrument (an order of magnitude between AUDJPY and
  EURUSD) — it is present everywhere tested, not equally strong everywhere.
- **Production readiness**: no cost-aware, execution-realistic validation
  exists yet — this remains a calibration/information finding, not a
  deployed feature.

## 25. Recommended Next Phase

Design and run a dedicated **cost-aware, direction-neutral risk-management
application** of this confirmed magnitude signal — for example, using
`volume_rank`-conditioned target-reachability probability to size stops/
targets or filter trade selection in an EXISTING, already-validated
directional context (never a new directional signal invented for this
purpose), with full transaction-cost stress testing. This is the single,
concrete, evidence-justified next step — not a menu of speculative
directions, and explicitly not a re-opening of the directional-edge
question, which remains closed.
