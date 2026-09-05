# Phase 87 — Directional Information Frontier

**Status: COMPLETE.** No live-execution artifact of any kind exists in
this phase's code or this document.

**Final verdict: `NO_NEW_INFORMATION_FOUND`.** Lane A's cross-market
USD-strength proxy — a genuinely new signal, never tested in Phases
76–86 — added essentially zero incremental directional information (ΔR²
≈ 0.0000, CI-crossing zero on every one of the 6 canonical instruments,
every one of 4 predeclared horizons, and every one of 5 temporal blocks).
Lane B (magnitude tradeability) is structurally blocked: it requires a
genuine directional setup to condition on, and none survives anywhere in
Phases 76–87. Priority 2 (economic surprise) and Priority 3 (order flow)
are `DATA_SOURCE_UNAVAILABLE`, verified by direct inspection, not assumed.

## 1. Purpose

Phase 86 tested one directional construction (`sign(mom_4)` filtered by
`volume_rank`) and found `NO_EDGE_FOUND` — a useful but narrow negative
result. This phase's mandate was explicitly not to re-slice the existing
OHLC/context feature space (no new EMA/RSI/MACD combinations) but to hunt
for genuinely **new** information that could plausibly create directional
asymmetry, following the master prompt's own priority order: cross-market
(Priority 1), economic surprise (Priority 2), order-flow (Priority 3), and
magnitude-as-a-tradeability-filter (Priority 4, conditional).

## 2. Repository State (verified, not assumed)

`HEAD == origin/main == 8a9e3a2` (Phase 86), working tree clean, 1839
passed / 6 skipped / 0 failed, frozen Gold contract hash unchanged —
confirmed at the start of this phase exactly as the master prompt itself
asserted.

## 3. Information Inventory

Reused Phase 84's own 20-row Information Frontier Matrix directly (never
rebuilt) for the currently-available inventory: OHLC, volatility,
momentum, trend regime, session/time, location/structure, MT5 tick
volume, VWAP (Phase 75, no edge), SMC/MTF (Phase 19, separate
architecture), macro actuals (FRED, Phase 65), and news calendar (Phase
38, revision-aware). This phase's only genuinely new element: a
cross-market USD-strength proxy built from the already-owned 11-instrument
MT5 basket.

## 4. Lane A — Cross-Market Information (Priority 1)

**Construction.** TradeLogger's MT5 store already holds 11 instruments on
the same broker/feed: the 6 canonical instruments plus AUDUSD, EURJPY,
NZDUSD, USDCAD, USDCHF — all with matching 15m coverage (2022-06/08 →
2026-09). No true centralized USD index (DXY) exists in this repository,
and **none was acquired for this phase**. Instead, a trade-weighted
USD-strength proxy was built causally, entirely from data already owned:

```
usd_strength(t) = mean(mom_4 over {USDJPY, USDCHF, USDCAD} at t)
                 - mean(mom_4 over {EURUSD, GBPUSD, AUDUSD, NZDUSD} at t)
```

using Phase 83's existing, unchanged `mom_4` feature on each contributing
instrument (never the target's own price). When the target itself is a
basket member, it is excluded from its own group average (leave-one-out)
to avoid any self-referential contamination. **Data-source class:
explicitly logged as Class A — the same MT5 feed, not an independent
source.** A causal trailing-200-bar percentile rank of this proxy
(`usd_strength_rank`, identical convention to Phase 84/85's `volume_rank`)
was also tested.

**Ablation** (frozen, M0–M2, on the T1 direction target, pooled across all
6 canonical instruments, 599,534-row-scale dataset, Phase 83's unchanged
discovery/confirmation split):

| Model | Confirmation OOS R² | Δ vs M0 | 95% CI | Excludes 0 |
|---|---|---|---|---|
| M0 baseline (Phase 83 unchanged) | 0.00534 | — | — | — |
| M1 +usd_strength (raw) | 0.00532 | −0.00002 | [−0.0000, 0.0000] | No |
| M2 +usd_strength_rank | 0.00532 | −0.00002 | [−0.0000, 0.0000] | No |

M0's own R² (0.00534) reproduces Phase 83's own T1 headline (0.00529)
almost exactly — a useful continuity check confirming this phase's dataset
construction is consistent with the established baseline.

**Cross-asset breakdown** (all 6 canonical instruments, none dropped): a
CI-excluding, non-zero delta on **zero of six** instruments (deltas of
0.0000 to −0.0001 everywhere, every CI straddling zero).

**Horizon robustness** (h∈{1,2,4,8}): delta ≈ 0.0000 at every horizon,
none CI-excluding.

**Temporal stability** (5 predeclared calendar-quarter blocks): signal R²
tracks baseline R² almost exactly in every single block (largest gap
0.0009), no meaningful separation in any period.

**Placebo** (shuffled `usd_strength_rank`): delta ≈ −0.00001 — as expected
for a signal that already carried no real information to begin with.

**Verdict: `NO_NEW_INFORMATION_FOUND`.** The cross-market USD-strength
divergence hypothesis, despite being economically well-motivated (a
standard concept in FX trading — currency strength composites are
routinely used as a discretionary tool), adds no measurable incremental
directional information over the existing context baseline, at any
horizon, in any period, on any instrument, in this dataset.

## 5. Priority 2 — Economic Surprise (data-availability audit)

`api/providers/fred_provider.py` (Phase 65) is confirmed, by this
repository's own Phase 65 documentation, to supply real historical
**actual** values only — no consensus/forecast field
(`macro_intelligence_engine.EconomicSurpriseEngine` has a dedicated
incomplete-data code path specifically for this reason). The only records
in this repository that DO carry a forecast field are a small (27-entry)
illustrative seed dataset spanning a few weeks, automatically disabled
once a real provider is registered — not a multi-year archive suitable for
an event study. **Verdict: `DATA_SOURCE_UNAVAILABLE`.** Per the master
prompt's explicit rule, no proxy substitution (e.g., actual-minus-previous
standing in for actual-minus-consensus) was fabricated to manufacture a
"surprise" study — that would misrepresent an established concept.

## 6. Priority 3 — Order Flow / Microstructure (data-availability audit)

Reused Phase 84's own `MT5_CAPABILITY_AUDIT` directly, independently
consistent with Phase 85's own provenance findings: `copy_ticks_range` is
never called anywhere in this repository; the persisted schema has no
bid/ask/spread/depth column; MT5 `tick_volume` is never treated as, nor
equivalent to, order-flow direction or traded volume. **Verdict:
`DATA_SOURCE_UNAVAILABLE`.**

## 7. Lane B — Magnitude Tradeability (Priority 4, conditional)

Per the master prompt's explicit warning, `sign(mom_4)` is **not** an
acceptable "genuine directional setup" for this lane — Phase 86 already
tested and rejected it. Lane A's cross-market signal was the only
candidate this phase could have used as a fresh, non-repeated directional
setup to condition a volume/magnitude filter on; it did not clear the
promotion bar (§4). **No other validated directional setup exists
anywhere in Phases 76–87.** Lane B is therefore reported as **structurally
blocked**, not weakly tested against a known-invalid substitute — running
it anyway on `sign(mom_4)` again would simply repeat Phase 86 in a new
wrapper, exactly what the master prompt's §17 explicitly forbids.

## 8. Researcher-Degree-of-Freedom Ledger

Recorded in full in the persisted artifact: 2 feasibility audits (economic
surprise, order flow), 3 frozen ablation models (M0/M1/M2) evaluated once
each on the frozen discovery/confirmation split, 1 cross-asset breakdown
(6 instruments), 1 placebo, 4 horizon-robustness runs, 5 temporal-block
evaluations, and 1 Lane B gate check. No threshold, lag, or basket
composition was searched, tuned, or adjusted after seeing any result — the
USD-strength basket composition (which instruments belong to the base vs.
quote group) was fixed by standard FX convention before any code ran.

## 9. Final Decision (Case 3 of the master prompt's decision tree)

> Both Lane A and Lane B fail → stop mining the current information space;
> identify the specific missing data required for the next frontier.

Applied honestly: the specific missing data this phase identifies is
either (a) a genuine forecast/consensus-bearing economic-release archive
with sufficient historical depth (not available today, and not
fabricable from FRED's actuals-only feed), or (b) genuine historical
order-flow/tick-level data (not available today — MT5's tick data has
never been ingested, and no historical bid/ask/depth exists in any form).
Absent either, **TradeLogger's currently-accessible information — OHLC,
derived context, tick volume, and now cross-market divergence among its
own 11 already-owned instruments — does not contain a directional edge**,
a conclusion now independently corroborated across two full phases (86,
87) using two structurally different directional constructions.

## 10. Limitations

1. The cross-market proxy tested only one construction (a trade-weighted
   USD-strength composite via `mom_4` divergence). Other cross-market
   framings (e.g., realized-correlation regime shifts, lead/lag at
   non-headline lags) were not separately tested, consistent with the
   master prompt's own explicit instruction not to search "thousands of
   arbitrary lags" — the predeclared horizon family {1,2,4,8} was used
   instead.
2. XAUUSD was included as a Lane A target but not as a basket member (gold
   is not a pure interest-rate-parity USD pair in the same sense as the
   FX majors) — this is a disclosed modeling choice, not an oversight.
3. This phase establishes an absence of *linear, Ridge-detectable*
   incremental information; it cannot rule out a genuinely nonlinear
   cross-market relationship the existing model family (deliberately
   restricted to Ridge, no model shopping) would not detect.

## 11. Recommendation

Per the master prompt's own final decision framework, this is Case 3:
**stop mining the current information space for a directional edge.**
Any further directional-edge research needs either a genuinely new,
verifiably available data source (a real economic-surprise archive or
genuine historical order-flow data — both currently absent) or an
explicit, separately-scoped pivot away from direction entirely, toward
Phase 85's confirmed magnitude information used for something other than
directional trading (e.g., volatility-aware risk framing) — a different
research question from the one this and Phase 86 were asked to answer.
