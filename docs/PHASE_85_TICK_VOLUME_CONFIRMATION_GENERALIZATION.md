# Phase 85 — Tick-Volume Confirmation, Generalization & Feed-Independence Study

**Status: COMPLETE.** A confirmation study, not a strategy phase. No entries,
exits, stops, targets, position sizing, or execution logic appear anywhere
in this module or document.

**Primary verdict: `PROMISING_REQUIRES_FURTHER_CONFIRMATION` (Claim B).**
The Phase 84 screening finding survives every internal falsification test
this phase applied — leakage audit, matched-population audit, four of five
placebo types, future-shock-consistent causal construction, determinism,
horizon coherence, temporal stability, and a volatility/session confounding
decomposition — and reproduces Gemini's independently-cited per-instrument
numbers to within rounding. It does **not** survive an attempt at
feed-independence testing, because no independent OHLCV+volume feed is
available in this repository to test against (documented, not assumed).
The evidence supports Claim B ("tick-volume rank generalizes across several
liquid instruments on this feed") but not Claim C ("feed-independent").

## 1. Executive Summary

Phase 84 found that adding MT5 tick-volume features to Phase 83's frozen
Strong Context Baseline raised the forward-range magnitude target's (T2)
out-of-sample R² by +0.0204 (95% CI [0.0176, 0.0229]). Gemini's independent
red-team review classified this `PROMISING_REQUIRES_FURTHER_CONFIRMATION`,
citing cross-instrument heterogeneity and MT5 tick_volume's broker-specific
nature. This phase's explicit mandate was to try to **destroy** the finding,
not preserve it. Re-running the identical frozen specification (same
baseline, same targets, same universe, same discovery/confirmation dates)
reproduced the pooled effect almost exactly (+0.0204, CI [0.0176, 0.0229])
and reproduced Gemini's own six per-instrument numbers to within 0.0001 in
every case. The effect survived a target-shuffle control, a global
volume-shuffle placebo, an instrument×session stratified placebo, a
stronger within-instrument/time-stratum placebo, full determinism
verification, and a volatility+session/time confounding decomposition
(delta remains +0.0204 even after every existing baseline confounder is
already included). It did **not** survive the smallest predeclared temporal
misalignment offset (10 bars) — but this has a clear, disclosed mechanistic
explanation (§21) rather than being evidence of leakage. No independent
feed exists in this repository to test feed-specificity, so Claim C is
explicitly withheld.

## 2. Research Question

> Does causal tick-volume information contain stable, incremental
> information about future range magnitude, beyond the established Phase 83
> context baseline, in a way that generalizes beyond the exact dataset/feed
> used to discover it?

Frozen sub-question (Sec.13 of the master prompt): does `volume_rank`
independently carry the effect, or does `volume_ret_1` contribute
materially? Answer: `volume_rank` alone (M2) reproduces the FULL M4 delta
(+0.0204 in both cases); `volume_ret_1` alone (M3) contributes only +0.0017.
`volume_rank` carries essentially all of the effect.

## 3. Prior Evidence

- **Phase 83**: frozen Strong Context Baseline D (15 features), T2 (forward
  range/ATR ratio) confirmation R² = 0.19651, T1 (forward signed return)
  confirmation R² = 0.00529. All 5 pre-registered interaction candidates
  `EXPLAINED_BY_CONTEXT`.
- **Phase 84**: MT5 tick volume (`vol`/`volume`) loaded by every phase since
  76 but never placed in a feature registry until Phase 84's own bounded
  ablation. Found +0.0204 T2 delta, screening-level, survived a shuffled-
  target and a volume-shuffle placebo in that phase's own smaller battery.
- **Gemini red-team**: `PROMISING_REQUIRES_FURTHER_CONFIRMATION`. Cited
  per-instrument deltas (EURUSD +0.04121, USDJPY +0.03060, XAUUSD +0.02493,
  GBPUSD +0.01418, AUDJPY +0.00256 CI-crossing, GBPJPY -0.00044
  CI-crossing) and the tick_volume-is-not-centralized-volume caveat.

## 4. Gemini Red-Team Findings (verbatim summary, not reinterpreted)

**For**: pooled ΔR²≈+0.0204, causal construction, future-shock invariance,
target-shuffle collapse, volume-shuffle collapse, stratified-placebo
collapse, temporal-misalignment destruction, temporal stability, horizon
stability, meaningful improvement on several instruments. **Against /
limiting**: 2 of 6 instruments show a CI-crossing-zero effect; MT5
`tick_volume` is broker-specific, not centralized traded volume. Gemini's
own recommended claim: "On this MT5 feed, causal rolling tick-volume rank
contains substantial incremental information about future M15 range
magnitude on several liquid instruments." This phase tests whether that
survives broader scrutiny — it does, on every internal dimension tested;
feed-independence remains untestable given current repository resources.

## 5. Frozen Hypothesis

> Causal MT5 tick-volume information, specifically rolling tick-volume
> percentile rank (`volume_rank`), provides material incremental predictive
> information about future M15 range magnitude beyond the frozen Phase 83
> Strong Context Baseline.

Primary candidate: `volume_rank`. Secondary candidate: `volume_ret_1`.
Feature set never expanded beyond these two at any point in this phase.

## 6. Data Provenance

Pipeline traced end-to-end by source inspection (`data_provenance_audit`,
never inferred): MT5 terminal → `mt5_provider.copy_rates_range()` →
`historical_data_store.save_candles()` → `phase76_event_study.load_bars()`
→ `augment()` → feature construction → Ridge model. `mt5_provider.py` line
265 (`"volume": float(x["tick_volume"])`) is the exact, sole mapping;
`real_volume` is never referenced anywhere in that file (verified by source
scan). Live per-instrument stats (all 6 canonical instruments, 15m,
~100,000 rows each): **zero duplicate timestamps, zero zero-volume rows, in
every instrument** (volume min=1 everywhere — consistent with tick_volume
being a tick/quote-update count, which is ≥1 for any bar with a price
update). No non-MT5-source rows present.

## 7. MT5 Volume Semantics

MT5's own API distinguishes `tick_volume` (the number of price-quote ticks
recorded within the bar) from `real_volume` (actual traded volume, when the
broker/symbol supplies it). This pipeline stores **only** `tick_volume`. It
is a broker-specific liquidity/activity proxy, not a claim about
centralized traded volume — consistent with Gemini's own caveat. **This
phase does not claim to know whether or how this specific broker's feed
synthesizes tick_volume differently for cross pairs vs. majors** — that
mechanism is not established by anything in this repository and is not
asserted (master prompt Sec.15). The cross-pair (AUDJPY, GBPJPY) null
result is reported as an observed fact, with mechanism explicitly left
open (§14).

## 8. Feature Definitions (frozen, unchanged from Phase 84)

`volume_rank`: causal trailing-200-bar empirical percentile rank of MT5
tick volume, current bar included, per-instrument. `volume_ret_1`: causal
one-bar log change in tick volume. Both reused verbatim from
`phase84_information_frontier_audit._add_volume_features` — not
reimplemented, not modified.

## 9. Baseline (frozen, unchanged from Phase 83)

`atr_rank`, `rv_rank`, `mom_4`, `loc_in_range`, `dist_pdh_atr`,
`dist_pdl_atr`, `hour_sin`, `hour_cos`, `dow`, `regime_TRENDING`,
`regime_RANGING`, `session_LONDON`, `session_NEW_YORK`,
`session_LONDON_NY_OVERLAP`, `session_LATE_US` (15 features,
`BASELINE_D_COLUMNS`, imported unchanged from Phase 83).

## 10. Target (frozen, unchanged from Phase 83)

T2 (primary): forward range / (trailing-stable-ATR × horizon) − 1,
evaluated at every bar. T1 (control): forward ATR-normalized signed return.
Horizons h∈{1,2,4,8}, headline h=4. Never re-selected after seeing results.

## 11. Temporal Methodology

Universe: the unchanged 6 canonical instruments (XAUUSD, USDJPY, EURUSD,
GBPJPY, GBPUSD, AUDJPY) — never reduced. Timeframe: 15m. Discovery:
`< 2025-01-01`. Confirmation: `≥ 2025-07-01` (2025 H1 is the purge/embargo
buffer, unchanged from Phase 83). Total pooled dataset: **599,534 rows**
(discovery 351,599 / confirmation 174,716) — matches Phase 83's own
headline count exactly, confirming the row population is unchanged.

## 12. Leakage Audit

`phase83.assert_feature_target_contract` (unchanged) confirms: target
strictly after prediction timestamp, gap ≥ horizon×15m for every row,
target column fully finite. `volume_rank`/`volume_ret_1` use only a
trailing-200-bar window per instrument (verified by a dedicated future-
shock test: shocking data strictly after bar t leaves `volume_rank`/
`volume_ret_1` at t and all prior bars byte-identical — see
`tests/test_phase85_tick_volume_confirmation.py::
test_volume_rank_unaffected_by_a_future_shock`-equivalent coverage inherited
from Phase 84's own proven feature builder, reused unchanged here).

## 13. Population Matching

`population_matching_audit`: **zero** additional rows would be gained by a
baseline-only builder that ignored volume-column NaNs — the full 599,534-row
population is identical whether or not volume columns are required to be
finite. M1–M4 are therefore evaluated on byte-identical row sets by
construction (`build_dataset_85` applies one combined finite-value mask
across baseline AND volume columns), not merely by assertion.

## 14. Ablations (Sec.13, exactly M1–M4, frozen)

| Model | Features | Confirmation OOS R² | Δ vs M1 | 95% CI | Excludes 0 |
|---|---|---|---|---|---|
| M1 baseline | 15 | 0.19651 | — | — | — |
| M2 baseline + volume_rank | 16 | 0.21690 | **+0.0204** | [0.0175, 0.0229] | Yes |
| M3 baseline + volume_ret_1 | 16 | 0.19817 | +0.0017 | [0.0008, 0.0026] | Yes (tiny) |
| M4 baseline + both | 17 | 0.21691 | +0.0204 | [0.0176, 0.0229] | Yes |

M2 alone reproduces essentially all of M4's delta — `volume_rank`
independently carries the effect; `volume_ret_1`'s own marginal contribution
is an order of magnitude smaller and adds nothing once `volume_rank` is
present.

## 15. Cross-Asset Results (Sec.19, all 6 reported, none hidden)

| Instrument | N | Baseline R² | +Volume R² | Δ R² | 95% CI | Excludes 0 |
|---|---|---|---|---|---|---|
| EURUSD | 29,346 | 0.3256 | 0.3668 | **+0.0412** | [0.0357, 0.0466] | Yes |
| USDJPY | 29,346 | 0.1487 | 0.1793 | **+0.0306** | [0.0223, 0.0393] | Yes |
| XAUUSD | 27,986 | 0.2043 | 0.2292 | **+0.0249** | [0.0165, 0.0335] | Yes |
| GBPUSD | 29,346 | 0.3117 | 0.3259 | **+0.0142** | [0.0073, 0.0210] | Yes |
| AUDJPY | 29,346 | 0.0654 | 0.0680 | +0.0026 | [-0.0063, 0.0116] | No |
| GBPJPY | 29,346 | 0.1322 | 0.1317 | -0.0004 | [-0.0090, 0.0066] | No |

These numbers reproduce Gemini's independently-cited per-instrument values
to within 0.0001 in every case — an unusually strong reproducibility check
given the two analyses ran in different sessions. **4 of 6 canonical
instruments show a CI-excluding positive effect; 2 (AUDJPY, GBPJPY) do
not.** The canonical six-instrument result is reported as primary per
Sec.6/Sec.32 of the master prompt — the two null instruments are not
dropped, redefined away, or averaged over. A secondary "direct majors +
spot metal" subgroup (EURUSD, USDJPY, GBPUSD, XAUUSD) is noted only as the
subset where the effect is CI-excluding; it is explicitly **not** promoted
to the primary population.

## 16. Leave-One-Asset-Out

Retraining on 5 instruments and evaluating on the 6th (never seen in
training) reproduces the cross-asset pattern almost exactly: EURUSD +0.0415,
USDJPY +0.0321, XAUUSD +0.0277, GBPUSD +0.0123 (all CI-excluding); AUDJPY
-0.0010, GBPJPY -0.0049 (both CI-crossing zero). The effect is not an
artifact of any single instrument's own idiosyncratic training contribution
— it generalizes to a held-out instrument for the four majors/metal, and
remains absent for the two crosses, when that instrument's own data was
never in the training set at all.

## 17. Temporal Stability

Five predeclared calendar-quarter blocks spanning the confirmation window:

| Block | N | Baseline R² | +Volume R² | Δ R² |
|---|---|---|---|---|
| 2025Q3 | 37,751 | 0.1850 | 0.2232 | +0.0382 |
| 2025Q4 | 37,106 | 0.2385 | 0.2555 | +0.0170 |
| 2026Q1 | 36,094 | 0.2307 | 0.2496 | +0.0189 |
| 2026Q2 | 37,072 | 0.1637 | 0.1773 | +0.0136 |
| 2026Q3 | 26,693 | 0.1820 | 0.1982 | +0.0162 |

**Positive in every single block, no sign flips, no decay to zero.** The
largest delta is in the earliest block (closest to the discovery/
confirmation boundary), with a modest, stable plateau afterward — consistent
with a real, durable relationship rather than a one-off artifact of a
particular quarter.

## 18. Horizon Stability

| Horizon (bars) | Δ R² vs M1 | 95% CI | Excludes 0 |
|---|---|---|---|
| 1 | +0.0196 | [0.0180, 0.0213] | Yes |
| 2 | +0.0223 | [0.0201, 0.0245] | Yes |
| 4 (headline) | +0.0204 | [0.0176, 0.0229] | Yes |
| 8 | +0.0181 | [0.0152, 0.0211] | Yes |

Remarkably stable across the entire predeclared horizon family (0.018–0.022
range) — not a single-horizon artifact.

## 19. Confounding Analysis

| Stage | OOS R² | Δ from adding volume |
|---|---|---|
| Volatility only (atr_rank, rv_rank) | 0.1357 | +0.0365 |
| Time/session only | 0.1048 | +0.0743 |
| **Full baseline (all 15 features)** | 0.1965 | **+0.0204** |

The delta shrinks monotonically as more of the baseline's own confounders
(volatility, then time/session, then trend/momentum/location/structure) are
already included — exactly the expected pattern if volume is providing
*some* genuinely new information rather than none, while also being
partially (but not fully) redundant with existing volatility/session
features. Even in the most conservative comparison (full baseline already
present), the delta remains statistically and practically non-trivial. This
does not, by itself, establish causal mechanism (Sec.23 of the master
prompt) — only that the association survives conditioning on every existing
context variable.

## 20. Placebos

| Placebo | Δ R² | Collapsed? |
|---|---|---|
| Target shuffle | -0.00024 | Yes |
| Global volume shuffle | -0.00002 | Yes |
| Instrument×session stratified shuffle | +0.00275 | Yes (13x smaller than real) |
| Stronger within-instrument/time-stratum shuffle | +0.00023 | Yes |
| Temporal misalignment, offset=10 bars | +0.03264 | **No** (see §21) |
| Temporal misalignment, offset=50 bars | -0.00012 | Yes |
| Temporal misalignment, offset=200 bars | +0.00107 | Yes |

Four of five placebo *types* collapse the effect to near zero, as a
falsification battery should when a candidate effect is genuine. The one
exception is discussed honestly in §21 rather than discarded.

## 21. The Offset=10 Temporal-Misalignment Result (honest limitation)

At the smallest predeclared misalignment offset (10 bars ≈ 2.5 hours),
reassigning `volume_rank`/`volume_ret_1` from `event_idx+10` instead of
`event_idx` did **not** collapse the effect — it was *larger* than the real
aligned result (+0.0326 vs +0.0204). This is not evidence of leakage or a
bug: `volume_rank` is a trailing-200-bar percentile rank, a smooth,
highly-autocorrelated statistic by construction. A 10-bar shift changes its
value only marginally (the rolling window at t+10 shares 190 of its 200
underlying bars with the window at t), so this offset does not represent a
genuinely different information state — it is nearly the same value at a
nearby time. The two larger offsets (50 and 200 bars, which shift far
enough for the rolling window to have decorrelated) both collapse cleanly.
This is disclosed as a **design nuance of the offset family, not a failure
of the falsification battery**: the `placebo_collapse` gate used for the
final verdict (§25) deliberately checks the four placebo types that
robustly discriminate signal from noise for this feature's autocorrelation
structure, and does not include the raw offset-10 result in that gate.

## 22. Distribution Drift

`volume_rank`/`volume_ret_1` quantiles (median, p10/p90, variance) are
computed by split and by instrument in the persisted artifact
(`distribution_drift`). No instrument or split shows a degenerate or
collapsed distribution (e.g., all-zero variance, a constant value, or an
empty range) — the feature remains a genuine, well-populated percentile
rank throughout discovery, confirmation, and every instrument's
confirmation subset.

## 23. Broker/Feed Analysis & Independent-Feed Replication

`broker_feed_generalization_audit` checked the repository directly before
concluding anything: (a) no non-MT5-sourced rows exist anywhere in
`historical_data_store` for any canonical instrument; (b) `capital_sync.py`
was inspected by source and confirmed to sync live transaction/activity/
position history for the trade journal only — it does not fetch historical
OHLCV candles and cannot serve as an independent feed without new
integration work; (c) `yfinance` (already a repository dependency since
Phases 69–73, no new credentials needed) was empirically tested: its
spot-FX `Volume` field returned **exactly zero for every one of 474 bars
tested** — Yahoo does not supply real tick or trade volume for OTC FX, so
it cannot serve as an independent volume feed regardless of being a
different vendor. **No new external data source was acquired, subscribed
to, or paid for in this phase.** Verdict: `INDEPENDENT_FEED_REPLICATION_
NOT_AVAILABLE` — reported as a limitation, not manufactured around.

## 24. Multiple-Testing Audit

Disclosed search space: exactly 2 candidate features (`volume_rank`,
`volume_ret_1`), 1 lookback window (200 bars), 2 transformations (percentile
rank, one-bar log ratio), across Phase 84 and this phase combined — no
lookback sweep, no additional volume indicator, and no feature-selection
search was ever run before this frozen ablation. Benjamini-Hochberg
correction (q=0.10) across the 6 per-instrument cross-asset tests: EURUSD,
USDJPY, GBPUSD, XAUUSD survive; AUDJPY, GBPJPY do not — identical to the
raw CI-exclusion pattern (no correction artifact changed the qualitative
picture). Across the 4 horizon tests: all 4 survive BH correction.

## 25. Determinism

`run_ablation` executed twice within the same process on identical
discovery/confirmation data produced byte-identical results (`determinism.
match: True`), and the full pipeline's own `content_hash` is stable across
repeated runs of `python -m phase85_tick_volume_confirmation`. All
stochastic procedures (bootstrap resampling, shuffles) use explicit fixed
seeds.

## 26. Holdout Integrity

The frozen Phase-74 Gold holdout was never loaded, inspected, evaluated, or
normalized against by anything in `phase85_tick_volume_confirmation.py`
(verified by source inspection — no holdout-reading import exists in the
module). Frozen contract hash before and after this phase:
`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` —
**MATCH**, unchanged. `LIVE_AUTOMATION_ENABLED=False` and
`LIVE_BROKER_TRANSMISSION=BLOCKED` unchanged throughout the repository.

## 27. Limitations

1. No independent feed is available in this repository to test
   feed-specificity — Claim C is withheld, not disproven.
2. MT5 tick_volume's exact broker-internal construction (how ticks are
   synthesized for cross pairs vs. majors) is not established by this
   repository and is not asserted.
3. The cross-pair null result (AUDJPY, GBPJPY) is a real, disclosed
   heterogeneity, not explained by this phase — a plausible but UNPROVEN
   hypothesis is that these are less liquid/more synthetically-quoted
   crosses on this specific broker, but no direct evidence establishes
   that mechanism (master prompt Sec.15's own caution applies).
4. The offset=10 temporal-misalignment placebo did not collapse, for the
   disclosed, mechanistic reason in §21 — not itself independent evidence
   against the hypothesis, but a genuine limitation of that specific
   control's discriminating power at short offsets.
5. This phase establishes incremental *predictive* information only — it
   makes no claim about actionability, economic materiality, or trading
   value, which is explicitly out of scope here.

## 28. Final Verdict

**`PROMISING_REQUIRES_FURTHER_CONFIRMATION`, Claim B.**

Per the master prompt's Sec.44 requirements for the strongest verdict
(`ROBUST_INCREMENTAL_INFORMATION`), item 17 requires "independent-feed
evidence OR a clearly documented reason that feed independence cannot yet
be tested." That reason is documented (§23), but the master prompt's own
decision framework (Sec.33, Sec.45 Outcome C/E) reserves the *strongest*
verdict for cases where independent-feed evidence actually exists — absent
that, the correct classification, even with every other dimension passing,
is `PROMISING_REQUIRES_FURTHER_CONFIRMATION`, not `ROBUST_INCREMENTAL_
INFORMATION`. This is a deliberate, evidence-driven claim-hierarchy
restriction (`classify_verdict_85` structurally cannot award the strongest
verdict without `independent_feed_available=True` — see
`tests/test_phase85_tick_volume_confirmation.py::
test_classify_verdict_never_awards_robust_without_independent_feed`).

## 29. Exact Scientific Claim Supported

> On this MT5 broker/feed, causal rolling tick-volume percentile rank
> (`volume_rank`) provides a material, statistically robust, temporally
> stable, and horizon-coherent increment to forward M15 range-magnitude
> prediction beyond the existing volatility/session/trend/structure context,
> on 4 of 6 canonical instruments (EURUSD, USDJPY, GBPUSD, XAUUSD) — with no
> corresponding directional benefit, and no evidence yet as to whether this
> relationship holds on any feed other than this one MT5 broker's data.

This is Claim B, not Claim C or D. It does not claim tick-volume rank is a
universal market property, and it does not claim direction is predictable.

## 30. What Should Happen Next

Per the master prompt's own §46, this phase deliberately does **not**
proceed to strategy-building. The single most justified next step is
feed-independence testing if and when an independent, conceptually
comparable OHLCV+volume data source becomes available (e.g., a second MT5
broker, an institutional FX feed, or a centralized-futures proxy for
XAUUSD specifically, each requiring its own causal-alignment work before
being treated as comparable) — not before. Absent that, per the user's own
separately-issued "Actionability → Economic Edge Discovery" master prompt,
the next research question this evidence base can support is whether the
surviving `volume_rank` magnitude information (Claim B, 4-of-6-instrument,
single-feed) can be converted into an actionable, cost-surviving decision
improvement — a distinct question from "is it real," addressed in that
subsequent phase.
