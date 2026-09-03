# Phase 71 — Gold Revalidation Baseline

*Third checkpoint of the Phase 69–72 master build. Runs the frozen Gold contract's
closest available approximation through the Phase-70 pipeline and produces the
old-vs-new comparison — honestly, with the timeframe substitution stated up front.*

---

## 1. The caveat, first

The frozen Strategy Contract (`PHASE_21_XAUUSD_STRATEGY_CONTRACT.md`, hash
`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`) executes on
**1-minute** structure with tight structural stops. The N=82 / +0.637R / 58.6% /
2.52 holdout was produced from a 1-minute XAUUSD dataset that is **not in the
repository** (P1-6). yfinance supplies ~7 days of 1m data.

**A like-for-like revalidation of the frozen holdout is not possible.**

Phase 71 runs the contract's *entry logic* (liquidity sweep → MSS → displacement
FVG retrace, `strategies/ict_2022_model.py` = `ict_2022_sweep_mss_fvg`) on the
timeframes the Phase-69 store can supply — **1h** (struct 4h, bias 1d) and **1d** —
as the nearest defensible proxy. It never claims equivalence to the frozen
holdout, and it never reads or mutates the holdout.

---

## 2. What this phase delivers

| Piece | File |
|---|---|
| Revalidation engine | `gold_revalidation.py` — `revalidate()` (1h + 1d discovery + walk-forward), old-vs-new `comparison`, objective `_classify()` → `EdgeStatus`, `persist_revalidation()` |
| Baseline merge | `gold_strategy_baseline._with_revalidation()` — `get_gold_baseline()` now reflects a persisted `gold_revalidation` artifact (`revalidated_metrics`, `wfo_status`, `last_validated_at`, `edge_status`) |
| API | `GET /api/research/gold-revalidation` (full artifact); `/api/research/gold-baseline` carries the merged fields |
| Frontend | `StrategyDiscoveryPage` "current revalidation" panel — old-vs-new table + substitution warning |
| Tests | `tests/test_phase71_gold_revalidation.py` — 10 tests |
| CLI | `python -m gold_revalidation` |

No execution / broker / risk / forward-validation file touched. Frozen hash and
holdout unchanged.

---

## 3. Edge-status rules (objective — §31)

`_classify(per_timeframe, walk_forward)`:

| Result | Condition |
|---|---|
| `INSUFFICIENT_EVIDENCE` | 1h OOS `< 20` trades, or 1h discovery not `AVAILABLE` |
| `INVALIDATED` | 1h OOS E[R] `≤ 0` **and** bootstrap CI upper `< 0` |
| `VALIDATED` | 1h OOS CI lower `> 0` **and** N `≥ 50` **and** WFO stability `≥ 0.5` — *tagged "timeframe-substituted, not the frozen 1m holdout"* |
| `DEGRADED` | anything else with a positive-but-uncertain 1h edge |

`GoldStrategyBaseline.edge_status` reflects this once a revalidation artifact
exists; otherwise it stays `INSUFFICIENT_EVIDENCE`.

---

## 4. Result (actual run — `gold_revalidation` artifact `83fb524d542a`)

**Old (frozen 1m holdout) vs new (1h proxy OOS):**

| Metric | Old | New | Δ | Interpretation |
|---|--:|--:|--:|---|
| expectancy_r | +0.637 | +0.106 | −0.531 | **materially lower** |
| win_rate_pct | 58.6 | 67.4 | +8.8 | higher |
| profit_factor | 2.52 | 1.32 | −1.20 | **materially lower** |
| max_drawdown_r | 4.0 | 4.37 | +0.37 | slightly worse |
| sample_n | 82 (1m) | 222 (1h all) | — | different regime |

**Per timeframe (proxy):**

| TF | state | OOS E[R] | PF | N | bootstrap CI | scorecard |
|---|---|--:|--:|--:|---|---|
| 1h | AVAILABLE | +0.106 | 1.32 | 46 | [−0.137R, +0.351R] | UNCERTAIN |
| 1d | AVAILABLE | +0.280 | 1.94 | 27 | [−0.077R, +0.651R] | UNCERTAIN |

Walk-forward (coarse, 3 windows): stability **1.0 (ROBUST)** — all three OOS
windows positive, but on small samples.

**EDGE STATUS: `DEGRADED`** · **VERDICT: DEGRADED / UNVERIFIABLE**

Both timeframes keep a positive tendency and the WFO is stable, but the 1h proxy
expectancy is ~1/6 of the frozen holdout, both bootstrap CIs cross zero, and
N is below the 50-trade / positive-lower-CB bar for `VALIDATED`. It is a
timeframe substitution, not the frozen 1-minute contract.

---

## 5. What this does *not* say

- It does **not** say the frozen contract is invalid — the forward-validation
  apparatus (`xauusd_forward_*`) remains its live evidence source and is
  untouched.
- It does **not** say Gold has no edge — it says the *1h timeframe substitution*
  of the entry logic does not, on its own, clear the bar, and the real thing
  isn't testable here.
- It does **not** replace or weaken the locked holdout.

---

## 6. Next (Phase 72)

Trade Setup Engine — does the *current* market satisfy a validated strategy right
now? Given Phase 70/71 found no validated edge on available data, the Trade Setup
engine's honest default state will frequently be `NO_SETUP` /
`INSUFFICIENT_EVIDENCE` with the failing condition named — which is correct
behaviour (§65/§72).
