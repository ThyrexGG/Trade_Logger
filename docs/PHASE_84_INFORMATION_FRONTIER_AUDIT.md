# Phase 84 — Information Frontier & Missing Signal Research Audit

**Status: COMPLETE.** This is an audit/roadmap phase, not a strategy phase
and not another ML pipeline. No `STRATEGY_CANDIDATE` is produced. The word
"edge" is deliberately not used to describe any result in this document.

**Final recommendation (see §23): proceed to Phase 85 with a single,
narrowly-scoped confirmatory study of MT5 tick-volume's incremental
information content for the forward-range MAGNITUDE target (T2), using the
exact Phase-83-grade validation battery.** This is not a vague call for
"more research" — it is one concretely specified next experiment, chosen
because this audit's own small bounded screening experiment found a
non-trivial, control-surviving effect (OOS R² +0.0204, 95% CI
[0.0176, 0.0229], excludes zero) from a feature that costs nothing to
acquire (already stored, already loaded by every phase since 76, never
once tested) and requires no new causal-alignment work. This is reported
as a **screening-level finding requiring confirmation**, not a validated
result — it has not been through cross-asset, leave-one-out, multiple
horizon, future-shock, or discovery/confirmation-locked testing yet.

---

## 1. Executive Summary

Phases 76–83 exhaustively tested TradeLogger's existing OHLC-derived
context feature space (volatility, time/session, trend/momentum,
location/structure) against three independent target families (V1
compression-expansion, V2 volatility-regime, and five unconditional
volatility/trend/session/momentum/structure interactions) and found, with
one exception, consistent negative-to-marginal results: real predictive
signal exists (OOS R² ≈ 0.20 for forward range magnitude, ROC-AUC ≈ 0.70
for a forward high-volatility bucket) but is explained by current
volatility state and deterministic session/time structure, not by any
newly-discovered relationship — and forward **direction** is essentially
unpredictable from this feature space (OOS R² ≈ 0.005). This phase's job
was not to re-slice that same information again, but to determine (a)
what information TradeLogger's repository *already has* but has not yet
used, (b) what information it plausibly *lacks* and could obtain, and (c)
which one candidate is the most scientifically defensible next thing to
test. §4–§14 build that picture; §19–§23 turn it into one recommendation.

The single most important finding of this phase is not external at all:
**MT5 tick volume has been loaded into the shared causal data frame by
every phase since Phase 76 (`phase76_event_study.load_bars`, column
`vol`) and never once placed in a feature registry or ablation set** —
not in Phase 78's `FEATURE_REGISTRY`, not in Phase 80's `ABLATION_SETS`,
not in Phase 81's `FEATURE_GROUPS_81`, not in Phase 82's
`FEATURE_GROUPS_82`, not in Phase 83's `BASELINE_D_COLUMNS`. This phase's
own small bounded ablation experiment (§9–§10) tested it for the first
time and found a real, control-surviving incremental effect on the
magnitude target. Every other candidate examined in this audit (order
flow, futures volume, positioning, macro, cross-market, higher-resolution
price) is either not causally clean, not currently available, or already
explored in a different guise — see the Information Frontier Matrix (§14).

## 2. Scope and Philosophy of This Phase

Per the master prompt, this phase deliberately does **not**: build a
strategy, acquire new external data, subscribe to any paid source, run an
unrestricted feature search, treat an LLM as a default answer, or optimize
for a positive result. It **does**: inventory what exists, classify what's
missing, run a small number of pre-scoped existing-data-only experiments
solely to answer feasibility questions (not to compete for the best
score), and produce one ranked, red-teamed recommendation — explicitly
permitted to be "stop, the evidence does not justify further complexity"
if that is what the evidence shows. It is not: the evidence instead
justifies one specific, cheap, already-partially-supported next step.

## 3. Repository & Prior-Phase Verification (independent)

Verified directly at the start of this phase, not assumed from memory or
documentation:

| Check | Result |
|---|---|
| `git rev-parse HEAD` == `origin/main` | `9a6a4d072d0b76ef51efcd8fd46174bd752be88e` (both) |
| Working tree | clean |
| Frozen Gold strategy contract hash | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` (read-only, unchanged) |
| `LIVE_AUTOMATION_ENABLED` / `LIVE_BROKER_TRANSMISSION` | `False` / `"BLOCKED"` (unchanged, docstring-verified across the repo) |
| Phase 83 final verdict (re-read from its own persisted artifact) | all 5 candidates `EXPLAINED_BY_CONTEXT`; `phase84_recommendation.recommended = False` |
| Phase 83 baseline confirmation R² (re-read live) | T2 (magnitude) = 0.19651, T1 (direction) = 0.00529 — the exact asymmetry the master prompt asked this phase to interpret |

No prior artifact was modified. The Phase-74 holdout was not read by
anything in this phase (`phase84_information_frontier_audit.py` imports
no holdout-reading module).

## 4. The Magnitude-vs-Direction Asymmetry, Interpreted as Information Content

Phase 83's R² ≈ 0.20 (magnitude) vs. R² ≈ 0.005 (direction) is interpreted
here strictly as a fact about *what the current feature space contains*,
not as "we found a strategy for magnitude." Volatility, time, and
structural context describe the *distribution* a market is currently in
(is it a wide-range or narrow-range regime, in which session) far better
than they describe which way price will move next. This is consistent
with a broad efficient-markets prior for a heavily arbitraged G10 FX/gold
15-minute-bar market: state (regime) has real, exploitable-feeling serial
structure; direction over a few bars does not. It is also consistent with
a narrower reading: the *feature space itself* is state-shaped (ATR
percentile rank, realized-vol rank, regime label, session dummy) and
essentially contains no order-flow or positioning information that could
plausibly carry directional content — see the competing-explanations
discussion in §16.

## 5. Information Taxonomy

| Category | Definition | TradeLogger status |
|---|---|---|
| A. Price / OHLC | Raw open/high/low/close | Present, foundation |
| B. Volatility | ATR, realized vol, and their ranks | Present, deeply explored (76–83) |
| C. Time | Hour/session/day-of-week | Present, deeply explored |
| D. Trend | Efficiency-ratio regime classification | Present, deeply explored |
| E. Momentum | ATR-normalized N-bar return | Present, explored (Phase 83) |
| F. Location | Position within recent range, distance to prior-day levels | Present, explored (Phase 83, `EXPLAINED_BY_CONTEXT`) |
| G. Structure | Swing/liquidity (SMC), MTF cascade | Present in `strategies/smc_utils.py` / `true_mtf_engine.py`, but architecturally separate from the 76-83 lineage and not cross-tested against it |
| H. Volume-derived | Tick-volume rank/return | Present in the raw data layer since Phase 76, **never in a feature registry until this phase** |

## 6. Existing Information Inventory (by repository module)

- **MT5 integration** (`mt5_provider.py`, Phase 74): OHLCV candles only
  (`copy_rates_range`), broker server-time-corrected to UTC. Tick volume is
  stored as `volume`, mislabeled generically — it is MT5's tick count, not
  centralized trade volume. `copy_ticks_range` (the API for genuine
  historical bid/ask/last tick data) is **never called anywhere in the
  repository** (verified by repo-wide grep). Live bid/ask is read via
  `symbol_info_tick()` in `market_data.py`, `order_execution.py`,
  `server.py`, `auto_sync.py` — current price only, never persisted
  historically. `historical_data_store`'s schema has exactly one
  volume-like column and no bid/ask/spread/depth column anywhere.
- **Capital.com integration** (`capital_sync.py`, `get_capital_id.py`):
  a secondary OHLCV sync path; same information class as MT5, no
  additional order-flow/depth data.
- **Macro / FRED** (Phase 65, referenced in `macro_intelligence_engine.py`):
  production FRED provider with an explicit lookahead rule
  (`release_timestamp > as_of` is inaccessible).
- **COT positioning** (Phase 66, `macro_intelligence_engine.py`): CFTC net
  positioning already ingested with a multi-provider conflict-handling
  layer; weekly resolution, ~3-day reporting lag, already as-of-gated.
- **News / economic calendar** (Phase 38, `xauusd_news_snapshot_store.py`,
  `xauusd_news_history_audit.py`, `xauusd_news_reliability.py`): an
  immutable `NewsSnapshotStore` with SHA-256 fingerprinting and a
  `CalendarMutationDetector` that already tracks post-release revisions —
  genuine revision-awareness infrastructure exists at the data layer,
  ahead of anything the 76-83 event-study lineage has used.
- **AI / Gemini** (`api/gemini_client.py`): a live conversational assistant
  (default model `gemini-1.5-flash`) for on-demand analysis commentary.
  Never used, and not currently suited for use, as a deterministic
  historical feature pipeline (no archival source text with verified
  publication timestamps has been identified).
- **VWAP / volume profile** (`phase75_orb_vwap.py`): already tested,
  `NO_EDGE_CONFIRMED`.
- **Structure / MTF** (`strategies/smc_utils.py`, `true_mtf_engine.py`,
  Phase 19): swing/liquidity-sweep structure and a 1D→4H→15M→5M→1M MTF
  cascade. This module *predates* and is architecturally independent of
  the Phase 76-83 lineage; its own docstring assumes 5M/1M data
  availability that §11 shows does not actually hold for most of the
  canonical universe today.
- **Backtester / Monte Carlo / walk-forward** (`backtester.py`):
  `run_monte_carlo()` and `run_walk_forward()` already exist, but operate
  on strategy trade sequences (execution-outcome resampling), a different
  use of resampling than the raw-target block-bootstrap used throughout
  76-83; not reused in this audit.

## 7. Current Feature-Space Redundancy Audit

Run on Phase 83's own Baseline D (15 features) via `redundancy_audit()`
(Pearson correlation, mutual information against T1/T2, and PCA on the
pooled discovery set — see `phase84_information_frontier_audit.py`; full
numeric output is in the persisted artifact, not reproduced number-by-
number here to avoid this becoming a second feature-selection exercise).
Structural findings:

- `dist_pdh_atr` and `dist_pdl_atr` are moderately correlated by
  construction (both scaled by the same `atr`), as expected — not a bug.
- `hour_sin`/`hour_cos` and the four session dummies are, by design,
  deterministic functions of the same underlying `hour` value — the
  feature space contains two *encodings* of the same time information,
  not two independent time signals. This matches Phase 81's own finding
  that `hour` alone nearly matches the full V2 model.
- PCA on the standardized 15-feature set needs noticeably fewer than 15
  components to explain 90% of variance, confirming the feature space is
  more redundant (fewer independent information axes) than its raw
  feature count suggests — consistent with, not contradicting, Phases
  80-83's own findings that "more features" did not add new information.

This is an understanding exercise, not a feature-selection competition:
no feature is recommended for removal here.

## 8. Empirical Predictability-Ceiling Table

Synthesized **live** from each phase's own persisted artifact via
`predictability_ceiling_table()` (never hand-copied, never re-run):

| Source | Target class | Metric | Value |
|---|---|---|---|
| Phase 83 Baseline D | MAGNITUDE (T2, forward range/ATR ratio) | OOS R² (confirmation) | 0.19651 |
| Phase 83 Baseline D | DIRECTION (T1, forward signed return) | OOS R² (confirmation) | 0.00529 |
| Phase 80 V2 pilot | STATE (forward high-vol bucket, binary) | ROC-AUC (mean, walk-forward, full/HGB) | 0.7076 |

This table is empirical, not invented: every figure is read directly out
of the cited phase's own artifact at report-generation time. It shows a
consistent pattern across three independently-designed target families:
**state and magnitude are moderately predictable from existing context;
direction is not.**

## 9. Feature-Group Ablation Experiment (existing-data-only)

A small, explicitly-permitted, cumulative ablation
(`run_feature_group_ablation`) reusing Phase 83's pooled dataset,
discovery/confirmation split, and `fit_and_eval_83` unchanged — purely to
understand which existing group contributes what, not a competition:

| Group | Features | T2 (magnitude) OOS R² | T1 (direction) OOS R² | T1 directional hit-rate |
|---|---|---|---|---|
| G0 intercept-only | 0 | 0.000 | 0.000 | 0.512 |
| G1 +volatility | 2 | 0.136 | −0.00004 | 0.512 |
| G2 +time/session | 9 | 0.190 | 0.0048 | 0.516 |
| G3 +trend/momentum | 12 | 0.196 | 0.0052 | 0.519 |
| G4 +location/structure (full Baseline D) | 15 | 0.1965 | 0.0053 | 0.520 |

Volatility alone captures the large majority of the magnitude signal
(0.136 of 0.1965); time/session adds most of the rest; trend/momentum and
location/structure each add a small increment. For direction, every group
adds only a few thousandths of R² and the directional hit rate never
clears 52% — a quantitative restatement, not a new finding, of Phases
80–83's conclusions. Determinism confirmed (two independent calls produce
identical per-group R² to 5 decimals).

## 10. The Tick-Volume Finding

`run_volume_ablation` adds exactly one new group — `volume_rank` (causal
trailing-200-bar percentile rank of MT5 tick volume, identical convention
to `atr_rank`/`rv_rank` since Phase 76/78) and `volume_ret_1`
(bar-over-bar log change) — on top of the full Baseline D:

| Target | Full Baseline D R² | +volume R² | Δ R² (point) | 95% CI |
|---|---|---|---|---|
| T2 (magnitude) | 0.19651 | 0.21691 | **+0.0204** | [0.0176, 0.0229], excludes zero |
| T1 (direction) | 0.00529 | 0.00519 | −0.0001 | [−0.0002, −0.00004], excludes zero but negligible |

**Controls** (`volume_ablation_controls`, T2):

- **Shuffled-target control**: permuting the training target collapses
  both the baseline (0.19651 → 0.0023) and the +volume model
  (0.21691 → 0.0024) — the delta collapses from +0.0204 to +0.00012. A
  mechanical or leakage artifact would not necessarily behave this way;
  a genuine forward-information effect must, and does.
- **Volume-shuffle placebo**: permuting `volume_rank`/`volume_ret_1`
  across rows (destroying true temporal volume dynamics while preserving
  their marginal distribution) collapses the delta from +0.0204 to
  +0.00001 — the effect depends on the *true temporal ordering* of
  volume, not merely its distribution.

**Honest scope**: this is a screening-level result from one bounded audit
experiment on the pooled discovery/confirmation split already defined by
Phase 83. It has **not** been through cross-asset breakdown, leave-one-
instrument-out, multiple horizons, future-shock invariance, regime/session
stability, or a freshly-locked discovery/confirmation cycle of its own —
all of which Phase 83's candidates went through before any of them (all
five) were rejected. It is reported here as the strongest evidence-backed
candidate this audit found, not as a validated finding. §19's Path 1
specifies exactly the confirmatory study required before any stronger
claim would be justified.

## 11. Native-Resolution / Tick-Data Feasibility Audit

Queried **live** from `historical_data_store.list_available()`
(`data_inventory_audit()` — never hard-coded, so this table cannot drift
out of date with the actual database):

| Timeframe | Instruments populated | Coverage |
|---|---|---|
| 15m / 1h / 4h / 1d | All 6 canonical instruments | 15m: 2022-06/08 → 2026-09; 1h/4h/1d: 2016-09 → 2026-09 |
| 5m | **XAUUSD only** | 2025-04-02 → 2026-09-03 (~1.5 years, 100,000-row cap) |
| 1m | **XAUUSD only** | 2026-05-25 → 2026-09-03 (~14 weeks, 100,000-row cap) |

Only XAUUSD has any sub-15m data, and only over recent, capped windows.
**Decision: the permitted M15-vs-M1 resolution experiment is explicitly
NOT run** (`m1_resolution_feasibility` → `NOT_ATTEMPTED_DATA_INSUFFICIENT`).
Reasoning: with M1 available for one instrument over a 14-week window, any
comparison against the multi-year, six-instrument M15 study population
used throughout Phases 76-83 would be built on a single, short, unusually
recent regime — a real risk of manufacturing either a spuriously clean or
spuriously null result driven by that window's own idiosyncrasies rather
than by resolution itself. This is a documented judgment call, not a
silent skip, consistent with the master prompt's "do not manufacture
success" principle.

On the MT5 capability side (`MT5_CAPABILITY_AUDIT`): `copy_ticks_range`
(true historical tick bid/ask/last data) has never been called anywhere
in the repository. This means genuine microstructure/order-flow history
does not exist yet even in principle — it would need to be captured
*going forward* from today, not backfilled.

## 12. Candidate Missing Information Dimensions

Each assessed against the orthogonality test ("what does this know that
OHLC does not know?") and revision/causal-alignment rules from the master
prompt:

- **Order flow / order-book imbalance**: potentially orthogonal, but no
  historical depth data exists or can be backfilled (`market_book_get` is
  live-only). `DATA_INFEASIBLE` today; only forward capture possible.
- **Centralized futures volume/OI (COMEX gold, CME FX)**: potentially
  orthogonal (spot MT5 activity vs. a centralized exchange's own volume
  are genuinely different populations), but requires external licensing,
  contract-roll/basis handling, and careful publication-timing alignment.
  `CAUSALLY_DIFFICULT`.
- **Options / implied volatility**: same class of difficulty, higher cost
  and higher construction complexity (surface fitting). `CAUSALLY_DIFFICULT`.
- **COT positioning**: already integrated and revision-safe
  (macro_intelligence_engine.py), but weekly resolution against a 15m/
  4-bar study is a severe resolution mismatch — unlikely to move a
  direction R²=0.005 result. `LOW_INFORMATION_VALUE` as a near-term ML
  feature (still legitimate as macro *context*, which is its current use).
- **Macro/rates (FRED)**: same resolution-mismatch caveat.
  `LOW_INFORMATION_VALUE` for this study's cadence.
- **Economic surprises**: genuinely event-conditioned (not a rolling-
  window feature) — a structurally different information type. Requires
  its own dedicated event-study design (out of this audit's small-
  experiment budget). `PROMISING_RESEARCH_FRONTIER`.
- **News (calendar event-state, not sentiment)**: the calendar layer is
  already revision-aware (Phase 38); headline-text/sentiment feeds have
  not been latency/survivorship-audited. `PROMISING_RESEARCH_FRONTIER`
  for calendar event-state specifically; explicitly not a sentiment-
  prediction recommendation.
- **Cross-market information**: potentially orthogonal, zero new
  acquisition cost (same MT5 connection, same store already holds
  correlated instruments), but requires a predefined-lag-family design
  (never a 1..500 lag search) and session-asynchrony handling.
  `PROMISING_RESEARCH_FRONTIER` — the cheapest genuinely-new-information
  candidate that requires no new provider.
- **Liquidity/spread, market depth**: cannot be backfilled; forward-
  capture only. `DATA_INFEASIBLE` today.
- **LLM/Gemini-derived text features**: no archival, timestamp-verified
  historical source text has been identified; the current Gemini
  integration is a live assistant, not a deterministic historical
  pipeline. `DATA_INFEASIBLE` (see §18).

## 13. Data-Quality Rubric and Direct/Proxy/Derived/Redundant/Orthogonal Classification

Applied per candidate in the Information Frontier Matrix (§14) using:
coverage, resolution, latency, revision behavior, survivorship,
availability, consistency, cost, licensing, replicability, and causal
alignment. Worked examples per the master prompt: ATR/EMA/RSI-style
indicators are **NOT orthogonal** (pure OHLC transforms — see the
"redundant OHLC-derived indicators" row in §14); MT5 tick volume is
**broker-specific, potentially additional** (not proven equivalent to
centralized trade volume); centralized futures volume, order-book
imbalance, macro surprises, and news event-state are **potentially
orthogonal but unproven**.

## 14. Information Frontier Matrix

Full 20-row matrix (source × already-present? × orthogonal? ×
historical-availability × resolution × causal-difficulty × cost ×
priority × verdict) is defined as data in
`phase84_information_frontier_audit.INFORMATION_FRONTIER_MATRIX` and
persisted in the run artifact. Summary by verdict:

| Verdict | Count | Examples |
|---|---|---|
| `HIGH_PRIORITY_RESEARCH_FRONTIER` | 1 | MT5 tick_volume (§10 finding) |
| `PROMISING_RESEARCH_FRONTIER` | 4 | Cross-market information, higher-resolution price, economic surprises, news event-state |
| `LOW_INFORMATION_VALUE` | 4 | COT positioning (as ML feature), macro/rates, MTF cascade, redundant volatility slicing |
| `CAUSALLY_DIFFICULT` | 4 | Centralized futures volume, open interest, options/IV, — |
| `DATA_INFEASIBLE` | 5 | Order flow, liquidity/spread, market depth, LLM text features, order-book depth |
| `REDUNDANT` | 3 | VWAP/volume-profile, market structure/SMC, redundant OHLC-derived indicators |
| `N/A_FOUNDATION` | 1 | OHLC itself |

## 15. Priority-Scoring Methodology and P0–P3 Assignment

Per the master prompt's explicit ban on "expected alpha" scoring, priority
was assigned holistically from: orthogonality plausibility, current-
feature-space gap, historical-data availability, expected data quality
(revisions/survivorship), causal-alignment feasibility, acquisition cost,
licensing clarity, engineering effort, replicability/determinism, sample
size over the studied period, cross-instrument generalizability, and
economic/microstructure theoretical rationale strength — applied
narratively per candidate (documented in each matrix row's `note`) rather
than mechanically summed into a false-precision numeric score for all 20
rows. P0 (tick volume) is reserved for the one candidate with actual
control-surviving empirical evidence, not merely plausibility; P1 is
reserved for zero-or-near-zero-cost, causally-clean candidates without yet
having empirical evidence (cross-market, higher-resolution price); P2/P3
scale down through resolution-mismatched, licensing-heavy, or currently
infeasible candidates.

## 16. Competing Explanations / Information-Bottleneck Hypotheses

For the central observed pattern (state/magnitude moderately predictable,
direction not), at least four competing explanations remain live and are
not resolved by this audit:

1. **Wrong information dimension**: the feature space measures state, not
   flow/positioning, which is disproportionately what would carry
   directional content (supported by: order flow / cross-market / COT are
   exactly the untested dimensions; not resolved without acquiring them).
2. **Market efficiency**: short-horizon direction in liquid G10 FX/gold at
   15m is close to a random walk regardless of feature richness (supported
   by: extensive literature precedent cited in Phase 76's own registry;
   not falsifiable by this audit alone).
3. **Wrong target formulation**: T1's ATR-normalized signed return may not
   be the right directional target (e.g. a longer horizon, a
   path-dependent target, or a regime-conditioned directional target might
   behave differently) — partially addressed by Phase 83's horizon
   analysis, not exhaustively.
4. **Genuine but small, currently swamped by noise**: the tick-volume
   finding (§10) is itself a data point against pure market efficiency at
   this resolution — a real, if narrow, targetable pocket of magnitude
   information does exist and had simply never been tested.

These are not mutually exclusive, and this audit does not adjudicate
between them — Phase 85 (§19, Path 1) is designed to add one more piece
of evidence, not to resolve the full question.

## 17. Research Tree (Branches 1–7)

| Branch | Status | This audit's disposition |
|---|---|---|
| 1. Existing OHLC/context | Exhausted (Phases 76-83) | Low priority — closed except tick-volume (§10) |
| 2. Higher-resolution price (M1/tick) | Feasibility studied (§11) | `DATA_INFEASIBLE` today; revisit if/when broader M1 history is captured |
| 3. Microstructure/order-flow | Feasibility studied (§12) | `DATA_INFEASIBLE`; no historical depth exists |
| 4. Cross-market | Feasibility studied (§12) | `PROMISING_RESEARCH_FRONTIER`; zero acquisition cost |
| 5. Macro/events/news | Feasibility studied (§12) | Mixed: COT/FRED `LOW_INFORMATION_VALUE`, economic surprises/news event-state `PROMISING` |
| 6. Positioning/options | Feasibility studied (§12) | `CAUSALLY_DIFFICULT` |
| 7. Alternative targets | Partially addressed by Phases 80-83's horizon/target work | Not a primary branch for Phase 85; folded into Path 1's design if needed |

## 18. LLM/Gemini-Derived Feature Caveats

Per the master prompt's explicit warning, an LLM must transform
historically-available, deterministically-timestamped information into a
reproducible representation — it must never "predict" anything directly,
and is never a default answer. No archival source of historical text with
verified publication timestamps, deterministic model/version pinning, and
guaranteed reproducibility has been identified in this repository. The
current Gemini integration (`api/gemini_client.py`) is a live
conversational assistant and is not repurposed here. **Classification:
`DATA_INFEASIBLE`** until such an archival source is separately
identified and audited — this is not proposed as a Phase 85 path.

## 19. Candidate Phase 85 Paths

**Path 1 — Confirmatory tick-volume magnitude study (RECOMMENDED).**
Hypothesis: MT5 tick volume carries incremental information about
forward range/ATR magnitude (T2) beyond Phase 83's full context baseline,
at the 15m/4-bar horizon, across the full 6-instrument canonical universe.
Required data: none new — `volume`/`vol` already in
`historical_data_store`. Expected information difference: a validated
Δ OOS R² materially above the 0.01 threshold used throughout 80-83,
confirmed to survive cross-asset, leave-one-out, multiple-horizon, and
future-shock testing. Research design: replicate Phase 83's full
methodology (fresh discovery/confirmation lock, block bootstrap,
shuffled-target + wrong-context-style volume placebo, cross-asset and
leave-one-instrument-out breakdown, regime/horizon stability, multiple-
testing correction if bundled with any secondary volume-derived
candidate). Risks: broker-specific tick-volume semantics may not
generalize across brokers/instruments; effect may be concentrated in one
instrument or regime (cross-asset/regime breakdown will show this).
Cost: none (existing data, existing infrastructure). Validation method:
identical gate structure to Phase 82/83 (`PREDICTABLE_BUT_EXPLAINED_BY_
CONTEXT`-style vs. genuine-incremental-value verdicts). Success criteria:
Δ R² ≥ 0.01 margin, survives BH correction, consistent sign/magnitude
across ≥ 4 of 6 instruments, survives both placebo controls at full
rigor. Failure criteria: any of the above fails, or the discovery-set
effect does not replicate in a freshly-locked confirmation window.

**Path 2 — Predefined cross-market lag-family study.** Hypothesis: a
small, pre-specified set of cross-instrument lag relationships (e.g. DXY-
proxy → XAUUSD, USDJPY → other JPY crosses) within the existing MT5 store
carries information the single-instrument context baseline lacks.
Required data: none new. Design: 2-3 pre-registered instrument pairs, a
small predefined lag family (e.g. {1, 4, 8} bars — never a 1..500 sweep),
multiple-testing corrected. Risks: session asynchrony/holiday mismatches
across instrument pairs; genuine risk of accidental lag-fishing if not
strictly pre-registered. Cost: none. Validation: same battery as Path 1.
Success/failure: same margin/BH/cross-asset-consistency criteria.

**Path 3 — Economic-surprise event-conditioned study.** Hypothesis: price
behavior in a narrow window around a pre-specified set of high-impact
release types (e.g. NFP, CPI, FOMC) differs systematically from the
unconditional baseline in a way current rolling-window features cannot
capture. Required data: existing macro/news infrastructure
(`macro_intelligence_engine.py`, `xauusd_news_snapshot_store.py`), with a
new consensus-at-release-time audit. Risks: small sample size (few
releases per year); consensus revision handling must be verified event-by
-event. Cost: none (data already integrated) but higher researcher/design
effort than Paths 1-2. Validation: event-study design (Phase 76-style),
not a rolling-window ML pilot.

**Path 4 — Continue existing OHLC/context research (NOT recommended).**
Explicitly retained as an option per the master prompt's decision
framework, but flagged low-priority: five independent target families
(V1, V2, five Phase-83 interactions) have already returned consistent
negative-to-marginal results from this exact feature space.

## 20. Ranking (by information-gain / research-risk / feasibility — NOT sophistication or cost)

1. **Path 1 (tick-volume confirmation)** — already has empirical,
   control-surviving screening evidence; zero cost; zero new causal-
   alignment risk; smallest, most tightly-scoped design of the three.
2. **Path 2 (cross-market)** — zero cost, causally clean, but purely
   plausibility-based (no screening evidence yet) and carries more
   design risk (lag-family pre-registration discipline).
3. **Path 3 (economic surprises)** — most interesting long-run
   information type (genuinely event-conditioned, not rolling-window) but
   highest design effort and smallest sample sizes; a reasonable Phase 86
   candidate after Path 1.
4. **Path 4 (continue OHLC/context)** — lowest priority; the evidence
   base (five independent negative/marginal results) argues against it.

## 21. Red-Team Review of the Top Recommendation (Path 1)

- **Strongest argument for**: real, controlled, reproducible effect
  (survives two independent falsification controls) on data that costs
  nothing to use; the single cheapest possible next step in the entire
  matrix.
- **Strongest argument against**: it is one screening result on one
  pooled dataset with one train/test split — Phase 83's own history shows
  candidates that looked promising at this stage (its own I2/I3 survived
  BH correction) still failed the *materiality* bar once fully evaluated.
  The same could happen here.
- **Biggest methodological risk**: the discovery/confirmation split used
  in this screening experiment is the SAME one Phase 83 already used and
  already "spent" scientifically for its own five candidates — a fresh
  Phase 85 study should be explicit about whether it is reusing that same
  confirmation window (in which case it is no longer a truly out-of-
  sample test for this new candidate) or defining a new one.
- **Biggest data risk**: MT5 tick-volume semantics (tick-count, not trade
  count) may differ across the six instruments' underlying feed sources
  in ways not yet characterized — cross-asset breakdown in Phase 85 is
  mandatory, not optional, for this reason.
- **Biggest false-positive risk**: with only one train/test split tested
  here, the +0.0204 point estimate could shrink substantially under
  walk-forward re-estimation, exactly as Phase 80's headline AUC did once
  compared against a corrected placebo.
- **What evidence would change the recommendation**: a fresh, properly
  time-separated discovery/confirmation cycle showing the effect
  concentrated in ≤ 2 of 6 instruments, or failing to survive a
  leave-one-instrument-out test, would downgrade this to
  `LOW_INFORMATION_VALUE` and the recommendation would revert to Path 2.

## 22. Research-Decision Framework and Stop Conditions

Of the master prompt's seven framework options, this audit selects
**"pursue one narrowly-scoped confirmatory study of an already-identified,
zero-cost candidate before considering any new data acquisition"** — not
"pause research entirely" (there is a genuine, evidence-backed candidate
left to test) and not "acquire new external data" (nothing external has
earned that yet). Concrete stop conditions for Path 1: if the confirmatory
study's Δ R² does not clear the 0.01 material margin, does not survive BH
correction, or is inconsistent in sign across instruments, the volume
candidate is closed (`EXPLAINED_BY_CONTEXT`/`NO_INCREMENTAL_VALUE`-style
verdict) and no further volume-feature research is pursued without new
justification — mirroring the discipline already established for V1/V2
and the five Phase 83 candidates.

## 23. Final Recommendation

**Proceed to Phase 85 with Path 1 only**: a confirmatory study of MT5
tick-volume's incremental information content for the T2 magnitude target,
run through the complete Phase-83-grade validation battery with a freshly
defined (or explicitly justified re-use of) discovery/confirmation split.
Do not pursue Paths 2–4 concurrently; re-rank after Path 1's result is
known. This is a concrete, evidence-anchored recommendation, not a call
for unspecified further research — and it remains fully falsifiable: if
Path 1 fails Phase 82/83-style validation, the honest and required next
step is to close the volume line and move to Path 2, not to search for a
different framing of the same data.

**Outstanding process step**: per the master prompt, this Claude-authored
audit is meant to be followed by an independent Gemini red-team review
whose explicit job is to try to disprove this recommendation (challenging
the information taxonomy, the orthogonality claims, the tick-volume
finding's controls, data-availability/provider assumptions, cost
assumptions, and whether Path 1 is itself a disguised form of feature
mining) before Phase 85 begins. That review has not yet been run and
cannot be performed by this session — it is an explicit follow-up
expectation from the master prompt, not something silently omitted here.
