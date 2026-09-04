# Phase 75 — Systematic Strategy Research: ORB + VWAP Mean Reversion

*A deliberate move away from discretionary ICT/SMC pattern interpretation toward
two highly objective, deterministic, programmatically testable strategy families.
Each is run at **one frozen baseline specification** — no parameter search. The
research question: can either demonstrate a reproducible, statistically credible
OOS edge on a small predefined set of liquid instruments? A negative result is a
successful scientific outcome.*

---

## S. Final verdict (stated first)

**`NO_EDGE_CONFIRMED`.**

- **ORB v1** — no post-cost edge. Per-instrument OOS samples are too small
  (N = 14–21) to promote anything (all `INSUFFICIENT_SAMPLE`); the full sample
  (N = 534) and aggregate OOS (N = 101, mean **−0.44R**, 95% CI **[−0.67R,
  −0.20R]**, "NEGATIVE EXPECTANCY") are decisively negative. Pre-cost the OOS
  aggregate is still slightly negative (−0.08R) — the in-sample marginal
  positivity did not carry to OOS even before transaction costs.
- **VWAP v1** — `FAILED` on all 6 instruments. Aggregate OOS N = 1 024, mean
  **−0.88R**, PF 0.17, win rate 30%, max drawdown 909R. The "poke beyond ±2.5σ
  then close back inside" confirmation catches continuation, not reversal
  (~30% target-hit); on FX majors the 1.5σ stop is frequently smaller than
  round-trip costs.
- **0 / 12** primary hypotheses produced a positive OOS cell; **0** survive a
  Bonferroni-widened CI; **0** candidates.

No candidate advances to Phase 76. Neither strategy is "validated" — the term is
not used in Phase 75.

---

## A. Objective

Research two deterministic strategy families — Opening Range Breakout (directional
expansion after the opening auction) and session-VWAP σ mean reversion
(statistically stretched price returning to fair value) — each at a single frozen
baseline spec, and determine whether either shows a reproducible OOS edge.

## B. Phase-74 baseline (not reopened)

| | |
|---|---|
| Start commit | `4288f16` (clean; Phase 74 was `78f0cf9`) |
| Phase 74 regression | 1 417 passed, 6 skipped, 0 failed |
| Phase 74 verdict | `NO_VALIDATED_EDGE` · native M15 ranking `NO ROBUST EDGE FOUND` · native gold 1m `EDGE INVALIDATED` |
| Frozen contract hash | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` |
| Safety | `LIVE_AUTOMATION_ENABLED=False` · `LIVE_BROKER_TRANSMISSION=BLOCKED` |

Phase 75 does not alter any of it. ICT/SMC strategies remain in the repository as
historical baselines (§12).

## C. Research universe (fixed before evaluation — §1)

Exactly six instruments: **XAUUSD, USDJPY, EURUSD, GBPUSD, GBPJPY, AUDJPY**. No
instrument was added or removed based on its results.

## D. Data provenance (§2)

Native **MT5 broker spot**, 15-minute, from the persisted dataset manifests
(`providers=['mt5']`). No yfinance / futures substitution.

| Instrument | Bars | First session | Last session | Manifest | Data quality |
|---|--:|---|---|---|---|
| XAUUSD | 100 004 | 2022-06-14 | 2026-09-03 | `XAUUSD:bda02b736685ea98` | AVAILABLE, 0 anomalous gaps, 0 suspect |
| USDJPY | 100 075 | 2022-08-29 | 2026-09-03 | `USDJPY:6306168424369bbe` | AVAILABLE, 0 / 0 |
| EURUSD | 100 065 | 2022-08-29 | 2026-09-03 | `EURUSD:2b7cf2a1a1f2c05e` | AVAILABLE, 0 / 0 |
| GBPUSD | 100 067 | 2022-08-29 | 2026-09-03 | `GBPUSD:387c857d2a801dbc` | AVAILABLE, 0 / 0 |
| GBPJPY | 100 000 | 2022-08-29 | 2026-09-03 | `GBPJPY:1734f67583c21622` | AVAILABLE, 0 / 0 |
| AUDJPY | 100 547 | 2022-08-22 | 2026-09-03 | `AUDJPY:7741acc8a6683f91` | AVAILABLE, 0 / 0 |

~4.1 years each; ~1 000–1 100 NY cash sessions per instrument.
`volume` = MT5 `tick_volume` (non-zero throughout) — used for VWAP weighting.

## E. ORB v1 specification (frozen — §4)

| Element | Rule |
|---|---|
| Session | 09:30–16:00 **America/New_York** (US equity cash session). DST handled by `zoneinfo` — never a hardcoded UTC offset. |
| Timeframe | 15m (native MT5) |
| Opening range | the single 15m bar opening at 09:30 NY; `OR_high` / `OR_low` = its high / low |
| Compression filter | **NR7** — the OR bar's range is strictly the smallest of the last 7 completed 15m bars (OR bar + 6 prior). Fails NR7 → no trade. |
| Entry | first session bar (≥ 09:45 NY, < 16:00) that **closes** beyond the OR (> `OR_high` → long, < `OR_low` → short); fill at the **next bar's open** (no look-ahead) |
| Trade limit | max **1 trade per instrument per session**; no re-entry after a failed breakout |
| Stop | opposite OR extreme (long: `OR_low`, short: `OR_high`) — range-derived, no multiplier |
| Target | entry ± **2.0 R** (single deterministic R multiple) |
| Time exit | flat at the last session bar's close if neither stop nor target hit |
| Intrabar | if a bar spans both stop and target, **stop assumed first** (conservative) |
| Costs | spread 1.5 pips + slippage 0.5 pips/side + commission 0.005% notional (`strategy_discovery` conventions) |

## F. VWAP v1 specification (frozen — §5)

| Element | Rule |
|---|---|
| Session | same as ORB v1 (09:30–16:00 NY, DST-aware) |
| Timeframe | 15m (native MT5) |
| VWAP | cumulative session VWAP from 09:30; typical price (H+L+C)/3, weight = tick_volume |
| σ | volume-weighted std of typical price around the running VWAP: `sqrt(Σ(v·TP²)/Σv − VWAP²)`, cumulative |
| Warmup | no entries before the 5th session bar (≥ ~1h15m in) so σ is meaningful |
| Bands | VWAP ± **2.5 σ** (baseline threshold, not optimised) |
| Entry | long: bar `low ≤ lower band` **and** bar `close > lower band` (poke + close back inside); short symmetric; fill at the **next bar's open** |
| Trend filter | skip long when `(VWAP − session_open) < −1.0σ`; skip short when `> +1.0σ` (one frozen filter) |
| Target | the **session VWAP at each subsequent bar** (dynamic) |
| Stop | entry ∓ **1.5 · σ_at_entry** (deviation-based); risk = 1.5 σ_entry |
| Trade limit | max **2 trades per session**; must be flat to enter |
| Time exit | flat at the last session bar's close |
| News | **no authoritative historical high-impact-event calendar exists in the repo** for backtest black-outs (the calendar layer is live/upcoming-oriented; FRED supplies data series, not timed releases). **Not applied.** Documented limitation. |
| Costs | same as ORB v1 |

## G. Validation methodology (§8)

- One deterministic backtest per (instrument, strategy) at the frozen spec —
  `phase75_orb_vwap.run_instrument` iterates NY sessions, simulates fills with
  the cost model, records every trade's pre-cost and post-cost R.
- **Chronological 60 / 20 / 20** train / validation / OOS, split on the **session
  date** (a session is never split across the boundary). No shuffling, no
  look-ahead, no future information. `research_engine.ThreeLayerDataSplitter`
  ratios.
- Bootstrap CIs: `research_engine.BootstrapEstimator`, deterministic seed 42.
- The frozen Phase-74 holdout is entirely separate and never read (§O).

## H. Full results matrix (§13)

`r_net` = post-cost R. `all` = full sample; `oos` = the 20% chronological
out-of-sample slice.

| Strategy | Instrument | N (all) | E[R] all | PF all | WR% all | N (oos) | E[R] oos | PF oos | WR% oos | OOS CI low | OOS MaxDD | Status |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| orb_v1 | XAUUSD | 81 | −0.038 | 0.94 | 40.7 | 17 | −0.067 | 0.90 | 35.3 | −0.666 | 5.7 | INSUFFICIENT_SAMPLE |
| orb_v1 | USDJPY | 104 | −0.279 | 0.61 | 39.4 | 21 | −0.629 | 0.37 | 33.3 | −1.168 | 13.5 | INSUFFICIENT_SAMPLE |
| orb_v1 | EURUSD | 96 | −0.358 | 0.54 | 37.5 | 20 | −0.470 | 0.44 | 35.0 | −0.977 | 12.0 | INSUFFICIENT_SAMPLE |
| orb_v1 | GBPUSD | 86 | −0.259 | 0.62 | 37.2 | 18 | −0.602 | 0.36 | 22.2 | −1.101 | 12.1 | INSUFFICIENT_SAMPLE |
| orb_v1 | GBPJPY | 99 | −0.189 | 0.73 | 38.4 | 20 | −0.199 | 0.67 | 35.0 | −0.668 | 5.4 | INSUFFICIENT_SAMPLE |
| orb_v1 | AUDJPY | 68 | −0.079 | 0.88 | 42.6 | 14 | −0.272 | 0.68 | 42.9 | −0.990 | 5.9 | INSUFFICIENT_SAMPLE |
| vwap_v1 | XAUUSD | 797 | −0.385 | 0.43 | 38.8 | 167 | −0.280 | 0.53 | 40.7 | −0.426 | 47.2 | FAILED |
| vwap_v1 | USDJPY | 732 | −0.854 | 0.18 | 31.4 | 149 | −1.100 | 0.12 | 25.5 | −1.317 | 164.9 | FAILED |
| vwap_v1 | EURUSD | 746 | −0.974 | 0.13 | 27.1 | 151 | −0.972 | 0.12 | 29.8 | −1.154 | 147.3 | FAILED |
| vwap_v1 | GBPUSD | 751 | −0.827 | 0.17 | 30.6 | 147 | −0.932 | 0.15 | 27.9 | −1.119 | 136.9 | FAILED |
| vwap_v1 | GBPJPY | 821 | −0.720 | 0.23 | 35.2 | 166 | −0.908 | 0.17 | 28.3 | −1.088 | 152.2 | FAILED |
| vwap_v1 | AUDJPY | 786 | −0.935 | 0.14 | 28.2 | 159 | −0.997 | 0.12 | 28.3 | −1.187 | 158.5 | FAILED |

Artifact: `phase75_orb_vwap`, `content_hash 0028a92d0560…`. `GET
/api/research/orb-vwap` serves it.

## I. Statistical analysis

- **ORB v1 aggregate OOS** (N = 101): mean −0.438R, median −1.09R, WR 32.7%,
  PF 0.47, max DD 46R, 95% bootstrap CI **[−0.672R, −0.198R]** → "NEGATIVE
  EXPECTANCY (FAILED)". Bonferroni-widened (α = 0.05/12) CI: still entirely < 0.
- **VWAP v1 aggregate OOS** (N = 1 024): mean −0.885R, WR 30.0%, PF 0.165, max DD
  909R. Every per-instrument OOS CI upper bound is < 0 except XAUUSD ([−0.43R, …])
  which is still decisively negative.
- **Pre-cost vs post-cost** (§7): ORB v1 per-instrument full-sample pre-cost
  means are +0.006R … +0.27R (roughly breakeven-to-slightly-positive), but the
  ORB v1 **OOS** aggregate is −0.079R pre-cost — the marginal in-sample positivity
  did not survive into OOS, and costs then push every cell clearly negative. VWAP
  v1 is deeply negative pre-cost as well (the entry logic, not the cost model,
  is the primary failure).

## J. Instrument comparison (both strategies combined, full sample)

| Instrument | N | E[R] | PF | WR% | Max DD (R) |
|---|--:|--:|--:|--:|--:|
| XAUUSD | 878 | −0.353 | 0.47 | 39.0 | 317 |
| GBPJPY | 920 | −0.663 | 0.27 | 35.5 | 621 |
| GBPUSD | 837 | −0.769 | 0.21 | 31.3 | 643 |
| USDJPY | 836 | −0.783 | 0.22 | 32.4 | 656 |
| AUDJPY | 854 | −0.867 | 0.18 | 29.4 | 749 |
| EURUSD | 842 | −0.903 | 0.16 | 28.3 | 762 |

XAUUSD is consistently the least-bad instrument for both strategies (widest ranges
→ costs a smaller fraction of risk), but nowhere near an edge. No instrument was
individually optimised (§6).

## K. Strategy comparison

| | ORB v1 | VWAP v1 |
|---|---|---|
| Full-sample N | 534 | 4 633 |
| Full-sample E[R] (post-cost) | −0.211R | −0.778R |
| Full-sample PF | 0.70 | 0.20 |
| Full-sample WR | 39.1% | 32.0% |
| OOS E[R] | −0.438R | −0.885R |
| Trade frequency | ~1 per 2 sessions (NR7 gates most) | ~0.75 per session |
| Failure mode | edge (if any) is marginal and does not survive OOS or costs; NR7 makes per-instrument OOS under-powered | confirmation catches continuation not reversal; stop < costs on FX majors |

## L. OOS results

Every OOS cell is negative. ORB v1: 6/6 `INSUFFICIENT_SAMPLE` (N 14–21). VWAP v1:
6/6 `FAILED` with CI upper < 0 (or ≈ 0 for XAUUSD). Aggregate OOS equity for both
strategies is monotonically declining — no sustained profitable regime in the OOS
window (2026 data).

## M. Multiple-comparison treatment (§9)

- **12 primary hypotheses** = 2 strategies × 6 instruments, each evaluated once on
  its OOS split. **No parameter grid was run** — these 12 are the only tests.
- Bonferroni α = 0.05 / 12 = **0.004167**. Expected false positives at α = 0.05:
  0.6.
- **Raw positive OOS cells: 0.** **Cells surviving a Bonferroni-widened bootstrap
  CI lower bound > 0: 0.**
- No exploratory sub-tests were needed or run.

## N. Candidate promotion gate (§10)

Classification set: `INSUFFICIENT_SAMPLE` / `FAILED` / `EXPLORATORY` /
`UNCERTAIN` / `CANDIDATE`. `VALIDATED_EDGE` is **not** used in Phase 75.

Gate criteria (all must hold, evaluated on OOS): N ≥ 30 · mean R > 0 · nominal CI
lower > 0 · Bonferroni CI lower > 0 · post-cost mean R > 0 · pre- **and**
post-cost positive · both chronological halves positive · drawdown reasonable.

**No cell satisfies any of the positive-expectancy criteria.** VWAP v1 cells fail
every gate check; ORB v1 cells do not reach a testable OOS sample.

**Candidates promoted: NONE.**

## O. Frozen-holdout governance (§16)

- The Phase-74 frozen holdout (N=82 / +0.637R) was **not loaded, queried,
  inspected, or compared** at any point. `phase75_orb_vwap.py` contains no
  reference to `LOCKED_HISTORICAL_BASELINE`, `forward_accumulation`,
  `forward_validator`, or `HistoricalVsForwardComparator` (asserted by
  `test_frozen_holdout_is_never_read`).
- Frozen contract hash verified **`7f135a12…76`** at the start and end of the
  phase (`test_frozen_hash_and_safety_flags_intact`). Unchanged.
- The result artifact records `holdout_untouched: true` and the hash it saw.

## P. Safety audit (§15)

- `LIVE_AUTOMATION_ENABLED = False` · `LIVE_BROKER_TRANSMISSION = "BLOCKED"` — unchanged.
- No execution / broker / risk / reconciliation / forward file modified.
- `phase75_orb_vwap.py` imports none of those modules (asserted).
- No credentials added; `.env` untracked.
- No new execution or order pathway. The API endpoint is GET-only.

## Q. Regression / build results

- `pytest tests/test_phase75_orb_vwap.py` — **21 passed**.
- `pytest tests/ -p no:randomly` — **1 454 passed, 6 skipped, 0 failed** (~128 s).
  Phase-74 baseline was 1 417; +37 = 21 (Phase 75) + 16 (research-diagnostics
  tooling committed in `4288f16`).
- `npx tsc --noEmit` — clean; `npm run build` — clean (1.99 s). No frontend
  changes in this phase; the endpoint is backend-only.

## R. Limitations

- **ORB v1 sample power.** NR7 on a single 15m bar is restrictive: the 09:30 bar
  is usually an *active* opening bar and rarely the narrowest of the last 7, so
  only ~7–10% of sessions trade. Per-instrument OOS N is 14–21 — enough to reject
  a large positive edge, not enough to promote a marginal one. This is a property
  of the frozen spec, documented rather than optimised away. A future controlled
  optimisation phase could test alternative compression definitions (NR4,
  inside-bar, pre-open range) — **not** done here (§3).
- **VWAP news black-outs not applied** — no historical high-impact-event calendar
  exists in the repo (§F). Results include periods around scheduled releases.
- **σ scale on FX majors** — cumulative-VWAP σ on 15m EUR/GBP/JPY pairs is small
  in price terms, so the 1.5σ stop is often only 5–10 pips and the 2.5-pip
  round-trip cost is a large fraction of risk. This is a real instrument-
  appropriateness finding (§6), not a bug.
- **Single timeframe** — 15m only (the common native denominator for all six).
  XAUUSD also has 1m/5m; a finer ORB opening range was not explored (§3).
- **One spec each** — by design. Phase 75 is a specification test, not an
  optimisation.

## Reproduction

```
HISTORICAL_OHLCV_PROVIDER=mt5 python -m phase75_orb_vwap
```

Deterministic: `zoneinfo` session anchoring, fixed 60/20/20 split on session
date, bootstrap seed 42, one frozen spec each. Same store state ⇒ identical
`content_hash` (`test_result_is_reproducible`). Tests:
`tests/test_phase75_orb_vwap.py` (21).

---

## Decision tree outcome (§17)

Neither strategy produced a credible candidate → **`NO_EDGE_CONFIRMED`**. No
further optimisation cycle is forced. Nothing proceeds to Phase 76.
