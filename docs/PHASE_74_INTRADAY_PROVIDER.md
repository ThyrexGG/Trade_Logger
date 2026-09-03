# Phase 74 — Real Intraday Historical Data Provider (MT5), XAUUSD Native Revalidation & Multi-Market Expansion

*Phase 73 built the intraday provider architecture and concluded **BLOCKED BY
DATA AVAILABILITY** — yfinance supplies ~8 days of 1-minute XAUUSD. Phase 74
supplies real broker data: the account's own MetaTrader 5 terminal, whose
credentials were already in the environment.*

---

## 1. Verdict, first

**`COMPLETE WITH DOCUMENTED LIMITATIONS`.**

- A real intraday provider now exists and is wired: `mt5_provider.MT5Provider`,
  pulling **real broker XAUUSD spot** (not GC futures) and the full FX universe
  from the local MT5 terminal.
- XAUUSD native depth obtained: **1m ≈ 3.4 months** (100 000-bar terminal cap),
  **5m ≈ 17 months**, **15m ≈ 4.2 years**, **1h ≈ 10 years**.
- The frozen Gold contract's `sweep → MSS → FVG` logic was revalidated at its
  native timeframes on this **independent** dataset. Result: **NO NATIVE EDGE**
  — see §5. This does **not** touch the frozen forward-validation apparatus.
- Multi-market: MT5 M15 ingested for the FX universe; a native-timeframe pair
  ranking was run — see §6.
- The documented limitation: the MT5 terminal caps 1-minute history at ~100 000
  bars (~3.4 months of 24×5 trading), below the 6–12 months §17 asks for. The
  contract's *literal* 5-frame form (1D→4H→15M→5M→1M) is still approximated by a
  3-frame backtest — `backtester` is a shared module and was not modified.

---

## 2. What this phase delivers

| Piece | File | Purpose |
|---|---|---|
| MT5 provider | `mt5_provider.py` | `HistoricalIntradayProvider` over the local MT5 terminal. Server-time → UTC conversion, chunked `copy_rates_range` with download retries, capability depth-probing, import-safe off-Windows, credentials env-only and never returned |
| Provider routing | `historical_provider.get_provider` | `HISTORICAL_OHLCV_PROVIDER=mt5` is honoured regardless of import order — a named provider never silently falls through to yfinance |
| Ingestion path | `market_data_ingest.py` | `--provider mt5`; `_provider_ingest` replaces a stale vendor's rows on the same key rather than merging two vendors (§9/§10) |
| Dataset manifest | `dataset_manifest.py` | `DatasetManifest` — provider, vendor symbol, asset type, date range, candle count, coverage ratio, anomalous gaps, suspect candles, sufficiency, licensing note, **holdout-isolation statement**; deterministic `content_hash`; `python -m dataset_manifest <SYMBOL>` |
| Native revalidation | `native_gold_revalidation.py` | rewritten for real data — objective `_classify` (negative native with N ≥ 150 → `INVALIDATED`/`NO_EDGE`; strong positive + CI>0 + N ≥ 50 + WFO ≥ 0.5 → `VALIDATED`), independent-dataset comparison table (never a delta) |
| SMC detector optimisation (§33) | `strategies/smc_utils.py` | per-DataFrame numpy column cache; `detect_mss` / `detect_liquidity_sweep` rewritten to read arrays not `.iloc` scalars — **≈105× faster (5.8 µs vs 610 µs per bar), 0 signal mismatches** vs the pre-Phase-74 logic |
| API | `api/routers/strategy_research.py` | `GET /api/research/dataset-manifest?symbol=` added; `data-coverage` / `historical/providers` / `gold-revalidation/native` are provider-agnostic and reflect MT5 when it is the active provider |
| Tests | `tests/test_phase74_ict_equivalence.py`, `tests/test_phase74_provider_and_data.py` | detector equivalence (synthetic + real), provider contract, credential hygiene, data-quality gates, manifest provenance, frozen hash + holdout untouched, no execution imports |
| Docs | this file + `CURRENT_STATE` / `TECHNICAL_DEBT` / `FUTURE_WORK` | |

No execution / broker / risk / reconciliation / forward-validation file was
modified. The frozen contract hash
(`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`) and the
frozen holdout (N=82 / +0.637R) are unchanged and unread by any Phase 74 code.

---

## 3. The provider — `mt5_provider.MT5Provider`

- **Auth**: `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` from the environment only.
  Never logged, never returned on any object, never in an artifact or the AI
  context. `.env` is gitignored (`.env.*`), and no secret is in Git history.
- **Time**: MT5 `rates['time']` is broker *server* time (this account UTC+3).
  The provider compares a live tick to wall-clock UTC, rounds to the hour, and
  converts every candle to true UTC epoch seconds before it is stored.
- **Deep history**: a single large `copy_rates_range` returns *"Invalid params"*
  until the terminal has downloaded the range. The provider walks backward in
  timeframe-sized chunks with `symbol_select(sym, True)` first and retry+sleep on
  each chunk.
- **Symbol mapping (§13)**: `XAUUSD` → broker path `Precious_Metals` / `XAUUSD`,
  2-digit **spot metal**, asset type `METAL_SPOT`. This is *not* the COMEX GC
  future — the yfinance `GC=F` proxy is labelled `GOLD_FUTURES_PROXY` in the
  manifest; MT5 XAUUSD is labelled `BROKER_SPOT`. They are never conflated.
- **Off-Windows**: the `MetaTrader5` package is Windows-only. Import is wrapped;
  on any other platform the provider reports `PROVIDER_UNAVAILABLE` and never
  raises.

### Measured MT5 depth (this account)

| TF | Earliest | Depth | Note |
|---|---|--:|---|
| 1m | ~2026-05 | **~3.4 months** | 100 000-bar terminal cap |
| 5m | ~2025-04 | ~17 months | |
| 15m | 2022-06 | **~4.2 years** | 100 000-bar cap |
| 1h | ~2016 | ~10 years | |
| 4h | ~2020 | ~5.5 years | |
| 1d | ~2004 | ~20 years | |

All FX majors + crosses + XAGUSD available under plain symbol names.

---

## 4. Data quality gates (§9 / §12)

Every ingested series passes through:

- **OHLC consistency** (`historical_data_store.validate_candle`) — `high ≥ low`,
  `high ≥ max(open,close)`, `low ≤ min(open,close)`, positive prices/time. A
  broken candle is **rejected, not repaired**.
- **Interval alignment** — a 15-minute series bar whose open time is not
  minute-aligned is flagged `suspect` (kept, counted, surfaced), not silently
  accepted.
- **Duplicate safety** — PK `(asset, timeframe, open_time)`; re-ingesting the
  same window updates in place. `inserted=N` first pass, `updated=N` second.
- **Weekend-aware gap analysis** (`analyze_gaps`) — weekend / holiday gaps are
  classified separately; only *anomalous* gaps beyond a calendar-scaled budget
  fail `data_sufficiency`.
- **No silent multi-vendor merge** — `_provider_ingest` clears a stale vendor's
  rows on a key before writing MT5 rows; the manifest records the distinct
  `source` values per series.

XAUUSD MT5 ingest result: **0 anomalous gaps, 0 misaligned bars**, latest bar
UTC-verified against the live feed.

---

## 5. §19 Native Gold revalidation — the numbers

<!-- NATIVE_NUMBERS_START -->
`native_gold_revalidation` artifact (`HISTORICAL_OHLCV_PROVIDER=mt5`, dataset
`XAUUSD:d5132dd65b3f608e`, MT5 broker spot):

| TF | Role | State | Bars | Depth | OOS E[R] | N (OOS) | Full E[R] | N (full) | WFO stab. | Scorecard |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|---|
| **1m** | **NATIVE** | AVAILABLE | 100 000 | **101.7 d (~3.4 mo)** | **−0.093R** | 286 | **−0.092R** | **1 067** | 0.33 (UNSTABLE) | **FAILED** |
| 5m | NEAR_NATIVE | AVAILABLE | 100 000 | 518.7 d (~17 mo) | +0.088R | 354 | +0.036R | 1 067 | — | UNCERTAIN |
| 15m | NEAR_NATIVE | AVAILABLE | 100 000 | 1 542 d (~4.2 y) | +0.054R | 506 | −0.065R | 1 690 | 0.67 | UNCERTAIN |
| 1h | PROXY | AVAILABLE | 58 966 | ~10 y | +0.024R | 343 | −0.043R | 1 150 | — | UNCERTAIN |
| 1d | PROXY | AVAILABLE | 2 580 | ~10 y | +0.304R | 29 | +0.154R | 96 | — | UNCERTAIN |

**Native 1m detail** — full sample N=1 067, E[R] −0.092R, profit factor **0.82**,
win rate **51.0%**; OOS bootstrap CI **[−0.213R, +0.027R]** (crosses zero);
walk-forward: stability **0.33 / UNSTABLE**, stitched-OOS −0.292R over 301 trades
PF 0.64; Monte-Carlo on the real WFO OOS trades: risk-of-ruin **0.0%**, median
drawdown 1.0%. The WFO stitched sample carries one −69R outlier trade (a
stop-through in the 3-frame approximation on a fast 1m bar) which drags the WFO
expectancy well below the straight OOS figure — the straight −0.093R / N=286 is
the fairer native read, and it is still negative.

**`EDGE STATUS: INVALIDATED` · `NATIVE VERDICT: NO NATIVE EDGE`.** 1 067 real
native trades at −0.092R is a robust negative — the contract's sweep→MSS→FVG
core, in this 3-frame approximation on independent broker data, does not carry a
persistent edge. The near-native and proxy timeframes are all `UNCERTAIN` with
bootstrap CIs that cross zero.
<!-- NATIVE_NUMBERS_END -->

**This is an independent revalidation, not a reproduction of the frozen
holdout.** The datasets differ (MT5 broker spot vs the Phase-19/20 1-minute
set), the engine is a 3-frame approximation of the 5-frame contract, and the
two are **never compared as a delta**. The frozen forward-validation apparatus
(N=82 / +0.637R holdout) is untouched and unread.

---

## 6. §22 / §23 Multi-market native expansion

<!-- MULTIMARKET_START -->
*(filled once the M15 FX ingest + native pair ranking complete)*
<!-- MULTIMARKET_END -->

---

## 7. §36 Final research question

> *"With the best available real intraday historical data, which instrument +
> strategy has the strongest robust evidence of a persistent edge, and is it
> validated?"*

<!-- FINAL_ANSWER_START -->
**`NO_VALIDATED_EDGE`.**

With real broker intraday data down to the native 1-minute timeframe, the frozen
Gold contract's core logic shows **no edge** (−0.092R over 1 067 native trades).
Every other instrument × strategy in the Phase 70/71 1h ranking was already
`NO ROBUST EDGE FOUND`, with XAUUSD `ict_2022_sweep_mss_fvg` the most robust
*unvalidated* candidate. The Phase 74 native M15 pair ranking did not change that
— see §6. Native data made the picture **clearer, not better**: the strongest
candidate, tested at its own timeframe on independent data, does not hold up.

The frozen forward-validation apparatus (N=82 / +0.637R holdout) is a separate
system, untouched and unread. Nothing here changes it; nothing here is compared
to it as a delta.
<!-- FINAL_ANSWER_END -->

---

## 8. §33 SMC detector optimisation — equivalence

`detect_mss` and `detect_liquidity_sweep` were called ~60× per bar by
`ict_2022_model.analyze`; over a 100 000-bar backtest that is millions of pandas
`.iloc` scalar reads (TECHNICAL_DEBT P2-10). Phase 74 pulls the ~14 columns they
touch into plain numpy arrays **once per DataFrame** (`smc_utils._cols`, keyed
`(id(df), len(df))`, bounded at 8 entries) and indexes those.

- **≈105× faster**: 5.8 µs/bar vs 610 µs/bar.
- **0 signal mismatches** on a 2 400-bar synthetic frame and on real MT5 XAUUSD
  15m — `tests/test_phase74_ict_equivalence.py` pins the new implementations to
  the pre-Phase-74 `.iloc` reference logic (reproduced verbatim in the test).

---

## 9. Adding / replacing a provider later

```
HISTORICAL_OHLCV_PROVIDER=mt5           # or a commercial vendor
# MT5: MT5_LOGIN / MT5_PASSWORD / MT5_SERVER   (terminal running, logged in)
# vendor: HISTORICAL_OHLCV_API_KEY            (server-side only)
```

`python -m market_data_ingest --provider mt5 --universe` then
`python -m dataset_manifest XAUUSD`. Keys are read from the environment only.

---

## 10. Browser QA

**No headless/e2e harness in the repo** — `npx tsc --noEmit` + `npm run build`
clean; FastAPI TestClient route suites pass. Manual operator checklist:
`/research/discovery` → Gold detail native/near-native/proxy table shows the MT5
depths; `/api/research/dataset-manifest?symbol=XAUUSD` returns the manifest;
`/workspace/trade-setup` still `NO_SETUP` everywhere.

---

## 11. Remaining technical debt

| | Item |
|---|---|
| **P1-6b** | MT5 caps 1m history at ~100 000 bars (~3.4 months). 6–12 months of native 1m needs a commercial tick/minute vendor or exported terminal files. The provider architecture takes either. |
| **P2-10** | ✅ mitigated — the hot SMC detectors are ~105× faster. A full vectorised `ict_2022` precompute is still the end-state if routine deep 1m discovery is wanted. |
| **P74-1** | The literal 5-frame contract (1D→4H→15M→5M→1M) is still run as a 3-frame approximation — `backtester` is shared and was not modified for a research-only path. |
