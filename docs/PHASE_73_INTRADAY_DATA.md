# Phase 73 — Institutional Intraday Data Foundation & Native Gold Revalidation

*Solves the Phase 69-72 limitation: the native Gold contract could not be tested
at its execution timeframe. Phase 73 builds the intraday provider architecture,
ingests what the wired provider can supply, and answers the native question
honestly.*

---

## 1. Verdict, first

**The frozen Gold contract's native 1-minute timeframe cannot be revalidated on
the currently wired provider (yfinance).** yfinance supplies ~8 days of 1m and
~70 days of 5m/15m for XAUUSD — none of which is a statistically valid sample.

The native question is **BLOCKED BY DATA AVAILABILITY**. The infrastructure to
answer it the moment real intraday data exists is COMPLETE.

---

## 2. What this phase delivers

| Piece | File | Purpose |
|---|---|---|
| Provider abstraction | `historical_provider.py` | `HistoricalIntradayProvider` protocol; `ProviderCapability` (decides deliverability *before* ingestion → `OK` / `INSUFFICIENT_HISTORICAL_DEPTH` / `PROVIDER_UNAVAILABLE` / …); `FetchResult` with the §4 metadata; `YFinanceProvider`; `EnvKeyVendorProvider` (env-only, ships disabled); registry |
| Coverage report | `data_coverage.py` | `coverage_report()` / `human_report()` — per instrument×timeframe: earliest/latest/count/span/gaps/provider/state (`SUFFICIENT` / `PARTIAL` / `INSUFFICIENT_DATA` / `PROVIDER_UNAVAILABLE` / `NO_DATA`) |
| PARTIAL tier | `strategy_discovery.py` | `prepare_data(..., allow_partial=True)` + `DiscoveryResult.data_tier` — runs on real-but-below-bar intraday data, labelled `PARTIAL`, **never** entering the ranking pipeline |
| Native Gold | `native_gold_revalidation.py` | runs `ict_2022_sweep_mss_fvg` at 1m/5m/15m/1h/1d, each labelled `NATIVE` / `NEAR_NATIVE` / `PROXY`; `python -m native_gold_revalidation` |
| P2-11 fix | `pair_ranking.py` | `walk_forward()` returns `stitched_oos_r` (real per-trade OOS R); Monte Carlo runs on it (`basis: "real_wfo_oos_trades"`), not a synthesised list |
| API | `api/routers/strategy_research.py` | `GET /api/research/{data-coverage, historical/providers, gold-revalidation/native}`; `gold-baseline` carries `native_revalidation` |
| Frontend | `StrategyDiscoveryPage` | native/near-native/proxy table in the Gold detail panel |
| AI | `api/ai_context.py` | SYSTEM_INSTRUCTION: NATIVE/NEAR_NATIVE/PROXY labels; never present a proxy/PARTIAL result as the strategy result or as settling the native question |
| Docs | this file | |
| Tests | `tests/test_phase73_intraday.py` | 17 tests |

No execution/broker/risk/reconciliation/forward-validation file modified. Frozen
hash + holdout untouched and unread by the research path.

---

## 3. §3 Audit — where the limitation was

- Store held **1d/1h/4h only** (Phase 69). `market_data_ingest._YF_PLAN` already
  listed 1m/5m/15m but `research_universe.timeframe_is_data_capable` gated them out.
- `true_mtf_engine.py` (Phase 19) has the 5-level state machine but is a
  **parametric heuristic** (`tf_delta = +0.120` constants) — not a candle-driven
  backtest. `gold_strategy_baseline` already flags all Phase 19/20 numbers
  `reconstructable=false`.
- `backtester.run_backtest` supports a 3-frame stack (base + struct + bias) via
  `preloaded_data`. The frozen contract is 5 frames. Rather than risk a shared
  module, Phase 73 runs the **15m setup timeframe** (`TF_STACK["15m"] = (1h, 4h)`)
  as the closest testable near-native chain and labels it as such.

---

## 4. §7-§8 Coverage (yfinance, XAUUSD intraday ingested)

```
INSTRUMENT TF   CANDLES  SPAN(d) STATE
XAUUSD     1m      7562      7.5  PARTIAL   (yfinance ~8d; ~58d needed)
XAUUSD     5m     13709     70.5  PARTIAL   (yfinance ~70d; ~73d needed)
XAUUSD     15m     4579     70.5  PARTIAL   (yfinance ~70d; ~88d needed)
XAUUSD     1h/4h/1d  ...          SUFFICIENT
… all other instruments: 1h/4h/1d SUFFICIENT, intraday INSUFFICIENT_DATA (not ingested; provider can't reach bar)

summary: SUFFICIENT=33, PARTIAL=3, INSUFFICIENT_DATA=30
```

`PARTIAL` = real data present, below the sufficiency bar — usable for an
explicitly-labelled exploratory read only. `INSUFFICIENT_DATA` = the wired
provider itself cannot reach the bar (a data-availability limit, **not** a
provider outage).

---

## 5. §11-§12 Native / near-native Gold revalidation

`native_gold_revalidation` artifact:

| TF | Role | State | Span | OOS E[R] | N |
|---|---|---|--:|--:|--:|
| **1m** | **NATIVE** | **INSUFFICIENT_HISTORICAL_DEPTH** | 7.5 d | — | — |
| 5m | NEAR_NATIVE | PARTIAL | 70.5 d | **−0.032R** | 45 |
| 15m | NEAR_NATIVE | PARTIAL | 70.5 d | +0.227R | **17** |
| 1h | PROXY | AVAILABLE | 874 d | +0.106R | 46 |
| 1d | PROXY | AVAILABLE | 3649 d | +0.28R | 27 |

- **Native 1m: not testable** (7.5 days).
- **Best available real evidence: 5m near-native** — OOS **−0.032R over 45 trades
  on ~70 days**. Essentially no edge on that sample.
- 15m shows +0.227R but **N=17** — meaningless.
- The 1h/1d proxies are unchanged from Phase 71.

**EDGE STATUS: `DEGRADED`** · **NATIVE VERDICT: BLOCKED BY DATA AVAILABILITY.**

Every result is labelled NATIVE / NEAR_NATIVE / PROXY and PARTIAL where
applicable. None is comparable to the frozen N=82 / +0.637R holdout, and the
module says so in its docstring, artifact `caveat`, `native_verdict`, the API,
the UI and the AI SYSTEM_INSTRUCTION.

---

## 6. §36 Final research question

> *"With the best available real intraday historical data, which instrument +
> strategy has the strongest robust evidence of a persistent edge, and is it
> validated?"*

**`NO_VALIDATED_EDGE`.** The finest usable real test (XAUUSD 5m near-native,
~70 days) shows no edge (−0.032R / N=45). The 1h ranking (Phases 70/71) already
said NO ROBUST EDGE FOUND, with XAUUSD `ict_2022_sweep_mss_fvg` the most robust
*unvalidated* candidate. Intraday data did not change that — it reinforced it.
The native contract remains untested for lack of data.

---

## 7. §29 P2-11 — resolved

`pair_ranking.walk_forward()` now returns `stitched_oos_r`, the real per-trade R
sequence from the stitched OOS windows. `compute_pair_ranking` runs Monte Carlo
on `[{"pnl": r} for r in stitched_oos_r]` and tags the result
`basis: "real_wfo_oos_trades"`. `_synth_trades` is retained only for its shape
test and is marked deprecated — a synthesised list is never labelled native
trade-level evidence.

---

## 8. Adding a real intraday provider later

```
HISTORICAL_OHLCV_PROVIDER=<vendor>      # e.g. polygon / databento / tiingo
HISTORICAL_OHLCV_API_KEY=<key>          # server-side only
```

Write an adapter implementing `HistoricalIntradayProvider` and
`historical_provider.register("<vendor>", adapter)`. The key is read from the
environment only — never returned to the frontend, never in an artifact, never
in the AI context. `.gitignore` already covers all `.env.*`.

---

## 9. Tests / build

`tests/test_phase73_intraday.py` (17): provider capability + `INSUFFICIENT_HISTORICAL_DEPTH`,
FX synthetic-spot flag, env-vendor-disabled, coverage-report states, PARTIAL tier
gating, intraday as-of boundary (exact / −1s), sub-minute suspect flag, native
revalidation roles + verdict + no-holdout-equivalence, frozen hash + holdout,
P2-11 real-trade MC, GET-only endpoints, no credentials in the providers
response, no execution imports, safety barrier.

**Full suite: 1391 passed, 5 skipped, 0 failed.** `tsc` + `build` clean.

---

## 10. Browser QA

**Browser QA unavailable in this environment** — no headless/e2e harness in the
repo. `tsc` + `build` clean; TestClient route/UI suites pass.

Manual QA checklist (operator): `/research/discovery` → Gold detail shows the
native/near-native/proxy table with 1m = INSUFFICIENT_HISTORICAL_DEPTH;
`/workspace/trade-setup` still NO_SETUP everywhere; `/api/research/data-coverage`
returns the SUFFICIENT/PARTIAL/INSUFFICIENT_DATA summary; at 1280×720 / 1600×900
/ 1920×1080 the new table does not overflow the page body.

---

## 11. Remaining technical debt

| | Item |
|---|---|
| **P1-6b** | Still the core limit — no deep intraday OHLCV. yfinance: 1m ~8d, 5m/15m ~70d. Native Gold revalidation and real intraday discovery need a commercial vendor key or bundled files. The provider architecture is ready for either. |
| **P2-10** | `ict_2022` O(n·window) — unchanged. Intraday data is *fewer* bars (~70 d) so not worse; a vectorised precompute is still the fix if deep intraday runs ever become routine. |
| **P2-11** | ✅ resolved (real-trade Monte Carlo). |
| **P3-4 / P3-8** | Seasonality + full discovery remain 1h/1d-bound. |
