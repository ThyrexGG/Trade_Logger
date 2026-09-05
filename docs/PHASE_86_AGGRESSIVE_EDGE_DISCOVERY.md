# Phase 86 — Aggressive Trading Edge Discovery

**Status: COMPLETE.** No live-execution artifact of any kind exists in
this phase's code or this document — no entries, exits, stop losses,
targets, position sizing, or automation.

**Primary verdict: `NO_EDGE_FOUND`.** Neither research track produced a
candidate that cleared even the first, cheapest screening gate. This is
reported as a legitimate, well-instrumented negative result, not an
inconclusive one — it is directly consistent with, and mechanistically
explained by, every directional finding across Phases 76–85.

## 1. Phase Objective

Phase 85 established (Claim B, not C or D) that MT5 causal tick-volume
rank materially and stably improves forward **magnitude** prediction on 4
of 6 canonical instruments, on this one broker's feed, with **no**
directional benefit. This phase's mandate was different from every prior
phase: not "is there information?" but "can any surviving information be
converted into an actual, cost-aware, out-of-sample trading edge?" This
phase was explicitly authorized to search more aggressively than Phases
76–85 (a small, predeclared threshold grid, searched only on discovery
data) while remaining fully auditable — every hypothesis tested, promoted
or not, is recorded in the research ledger (§9).

## 2. Phase 85 Input Summary

Reused, unchanged, never repeated: Phase 83's frozen Strong Context
Baseline (15 features) and T1 (direction)/T2 (magnitude) target formulas;
Phase 84/85's frozen `volume_rank`/`volume_ret_1` construction; the
unchanged 6-instrument canonical universe; Phase 76's block-bootstrap
engine and its documented conservative cost proxy
(`_COST_ATR_PROXY = 0.05`); Phase 85's unified matched-population dataset
builder. No Phase 84/85 experiment (volume discovery, feed audit, placebo
battery, cross-asset confirmation, horizon/temporal-block analysis, LOAO)
was rerun — this phase reads their conclusions as fixed inputs.

## 3. Surviving Information Sources (inventory)

| Source | Role | Strength | Status |
|---|---|---|---|
| `volume_rank` | Magnitude (T2) | Material, +0.0204 ΔR², 4/6 instruments | `PROMISING` (Phase 85, Claim B) |
| `volume_ret_1` | Magnitude (T2), marginal | Small, +0.0017 | `DESCRIPTIVE` (redundant given `volume_rank`) |
| `mom_4` (existing baseline momentum) | Direction (T1) | Near-zero unconditionally (Phase 83); **no raw expectancy found in this phase either (§6)** | `REJECTED` as a standalone directional setup |
| `loc_in_range` × `regime` (Phase 83's own I4 interaction) | Direction (T1) | `EXPLAINED_BY_CONTEXT` (Phase 83) | `REJECTED` |
| Full Baseline D (volatility/session/trend/location/structure) | Magnitude (T2) | Real, R²≈0.20 (Phases 78-85) | `ROBUST` for magnitude, `REJECTED` for direction |

Only `volume_rank` (magnitude) is a genuinely `PROMISING` surviving
candidate for this phase to build on; every direction-oriented information
source tested across the entire 76–85 program remains rejected or
explained away.

## 4. New Hypotheses (this phase)

- **Track A/C**: an 8-cell pre-registered conditional-directional-asymmetry
  screen combining `loc_in_range` extremity × trend/range `regime` ×
  `volume_rank` state — a genuinely new three-way combination (Phase 83
  tested location × regime on direction alone; volume was never added).
- **Track B**: a concrete trading rule — trade in the direction of
  `sign(mom_4)`, filtered to bars where `volume_rank` is at or above a
  frozen threshold, exit at a fixed horizon.

## 5. Pre-Registration Rules

Frozen before any result was inspected: the three-way temporal split
(§7), the 8 asymmetry cells and their directional hypotheses (§8), the
7-point volume threshold grid `{0.50,0.60,0.70,0.75,0.80,0.85,0.90}`, the
materiality margin (`1.3 × 0.05 ATR = 0.065`, reusing Phase 76's own
materiality convention), the three cost scenarios, and the plateau-
selection rule for freezing a threshold (never argmax).

## 6. Conditional Information Methodology

Track A/C cells are evaluated with Phase 76's own block-bootstrap engine
(`block_bootstrap`, block=4) on discovery data, Benjamini-Hochberg
corrected (q=0.10) across the 8 pre-registered cells. A cell is promoted
to Level 1 **only if** it is material and BH-significant in discovery
**and** replicates with the same sign and materiality, unchanged, on
confirmation — a cell is never redefined after seeing confirmation.

## 7. Actionability Framework / Temporal Split

A three-way split, own to this phase (the frozen Phase-74 Gold holdout
contract is a completely separate invariant, never touched by anything
here):

| Split | Range | Role |
|---|---|---|
| Discovery | < 2025-01-01 | Screening, threshold search |
| Confirmation | 2025-07-01 – 2026-03-01 | Candidate promotion / freeze decision |
| Final holdout | ≥ 2026-03-01 | Evaluated exactly once, only for a candidate already promoted at confirmation |

These three dates were fixed in code before any candidate's result was
computed.

## 8. Economic-Materiality Framework

A trade-level effect is "material" if its block-bootstrap mean R-multiple
is ≥ `1.3 × 0.05 = 0.065` (reusing, not inventing, Phase 76's own
materiality convention) **and** its 95% CI excludes zero.

## 9. Cost Model

Reuses the project's own existing documented assumption
(`phase76_event_study._COST_ATR_PROXY = 0.05`, "conservative round-trip
cost proxy in ATR units" for spot FX/gold retail) as **BASE**. **ADVERSE**
= 0.10 ATR (2×). **SEVERE** = 0.20 ATR (4×, matching Phase 77's own upper
stress value). No cost scenario was invented without an existing project
anchor.

## 10. Trading Hypothesis Framework

R-multiple := `sign(mom_4) × T1 − cost_atr`, directly reusing Phase 83's
own frozen T1 formula (ATR-normalized signed forward return) as the raw
trade outcome — no new return-normalization convention was introduced.
This is the minimal possible operationalization of Track B: an existing
causal momentum "setup," filtered by the one confirmed information source.

## 11. Walk-Forward Methodology

The confirmation window's 5 predeclared calendar-quarter blocks (reusing
Phase 85's own `_quarter_blocks` helper) serve as the walk-forward
segments — performance is reported per block, never only in aggregate.

## 12. Robustness Methodology

Cross-asset breakdown (all 6 canonical instruments, never reduced),
parameter perturbation (±2 grid steps around the frozen threshold), cost
sensitivity (BASE/ADVERSE/SEVERE), and horizon robustness
(h∈{1,2,4,8}, in place of a new path-dependent stop/target simulator —
a disclosed scope choice, not a silent gap: no such simulator exists
anywhere in the Phase 76–85 lineage, and building one was judged
disproportionate to spend on a rule whose sign was not yet even confirmed
positive at BASE cost).

## 13. Placebo Methodology

Direction-sign shuffle (destroys the momentum-direction bet while keeping
the volume filter) and volume-rank shuffle (destroys the filter's temporal
association while keeping the direction bet) — both computed on
confirmation for the frozen threshold.

## 14. Multiple-Testing / Researcher-Degree-of-Freedom Accounting

Recorded in full in the persisted `research_ledger`: **24 hypotheses**
were tested in this phase — 8 pre-registered asymmetry cells (screened,
2 survived BH correction in discovery, 0 replicated on confirmation) and
8 volume-threshold grid points for Candidate 1 (all screened, 0 cleared
the materiality/CI bar), plus their downstream promotion/kill records.
**Zero hypotheses were promoted past Level 0.** No threshold, cell
definition, or cost scenario was chosen, adjusted, or re-run after seeing
a result it would have affected.

## 15. Results

**Track A/C (conditional directional asymmetry).** Of 8 pre-registered
cells, 2 survived Benjamini-Hochberg correction in discovery: `A2_high
loc_ranging_highvol` (mean T1 = −0.169, NEGATIVE, n=1,257 — a small-sample
"exhaustion reversal" cell) and `A7_low_loc_trending_lowvol` (mean T1 =
+0.062, POSITIVE, n=33,094). **Neither replicated on confirmation** with
matching sign and materiality — both were killed. This is exactly the
expected behavior of a disciplined multiple-testing procedure: with 8
cells tested, 1–2 "significant" results in discovery by chance is
unsurprising, and confirmation-stage replication is precisely the
safeguard that caught it.

**Track B (momentum + volume filter).** The discovery-stage screen found
the raw momentum rule **NEGATIVE at every one of the 7 grid thresholds**
(mean R-multiple from −0.051 at threshold 0.50 to −0.026 at threshold
0.90, all CI-excluding-negative, hit rate 47.7–48.7%, profit factor
0.91–0.96). No threshold ever produced a positive, material result — the
candidate was killed at the cheapest possible stage (Level 0), before any
confirmation, cross-asset, temporal, cost-sensitivity, or holdout
computation was spent on it (fail-fast, §23 of the master prompt).

## 16. Failed Hypotheses

All 8 asymmetry cells (2 killed at confirmation after passing discovery
screening; 6 killed at discovery screening itself) and all 7 Candidate-1
threshold points (killed at discovery screening) — see the full,
unmodified `research_ledger` in the persisted artifact for every entry.

## 17. Promoted Hypotheses

**None.** Zero candidates reached Level 1 in either track.

## 18. Final Verdict

**`NO_EDGE_FOUND`** — Candidate 1's base-cost expectancy never cleared
zero at any predeclared threshold, and no conditional-asymmetry cell
replicated on confirmation.

## 19. Limitations

1. Track B tested exactly one "directional setup" (raw ATR-normalized
   4-bar momentum, already in the existing feature library). This is a
   real methodological limitation, not a hidden one: **no directional
   setup anywhere in the entire Phase 76–85 research program has ever
   shown a raw, unconditional positive expectancy** to attach a volume
   filter to — Phase 76's large-bar-reversal candidate, Phase 78's
   momentum/breakout/session families, Phase 83's five interactions, and
   this phase's own raw-momentum test are all flat or negative before any
   filter is applied. A volume-based magnitude filter cannot manufacture
   positive expectancy out of a directional bet that has none to begin
   with — see §20's "what is missing" discussion.
2. A full path-dependent ATR stop/target exit simulator was not built
   (§12); horizon variation served as the exit-robustness proxy instead.
3. Given the Level-0 kill for Candidate 1, no cross-asset, temporal,
   cost-sensitivity, parameter-perturbation, placebo, or final-holdout
   computation was performed for it — by design (fail-fast), not omission.
4. Additional Track B sub-hypotheses (B3 expansion-participation without
   a directional overlay, B4 avoidance-only framing, B5 timing-only
   framing) were considered but not separately built as full trading rules
   in this pass, since B1/B2 already isolate the same root cause (no
   existing directional setup to condition) that would limit them equally.

## 20. Next-Step Recommendation

The evidence is now specific enough to name exactly what is missing,
answering this phase's closing question directly: TradeLogger's existing
causal feature library, across 76-85's exhaustive testing, contains **no
standalone source of raw directional expectancy** for any of the 6
canonical instruments at 15m. Phase 85's magnitude information
(`volume_rank`) is real but structurally cannot become a directional edge
by filtering a non-existent directional setup — it can, at most, ever
inform a magnitude-only decision (e.g., position sizing or volatility-
aware risk management, Track B6, explicitly the lowest-priority, "only if
strongly justified" track in the master prompt, and not pursued here for
that reason). **TradeLogger is not ready for a dedicated strategy-
engineering phase built on direction.** Any further work on an actual
trading edge would need either: (a) a genuinely new directional
information source (order flow, cross-market, or economic-surprise
information — all flagged `PROMISING_RESEARCH_FRONTIER` but untested in
Phase 84's own Information Frontier Matrix), or (b) an explicit pivot away
from directional trading toward a magnitude/volatility-conditioned
risk-management framing, which is a different, not-yet-scoped research
question from "find a directional edge."
