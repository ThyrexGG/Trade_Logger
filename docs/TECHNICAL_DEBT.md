# TradeLogger — Technical Debt

*Recorded during the stabilization pass. Priorities: P0 critical · P1 important ·
P2 improvement · P3 nice-to-have. Nothing here is a safety-invariant risk.*

---

## Phase 70 — Strategy Discovery

### P2-10 · `ict_2022_sweep_mss_fvg` backtest is O(n·window) — ~30 s per 17 k-bar run
- `strategies/ict_2022_model.analyze` runs nested `for` loops (`detect_mss` /
  `detect_liquidity_sweep`) inside the per-bar backtest loop. The full universe
  quick ranking is ~8–12 min because of it.
- **Mitigation in place:** in-process `strategy_discovery._PREP_CACHE` (candle
  pull + DataFrame build once per `(asset, timeframe)` per ranking run);
  discovery is offline-only and never on an API path.
- **Recommended fix:** precompute swing/FVG/MSS arrays once per df (vectorised)
  and have `analyze` index into them, instead of re-scanning windows each bar.

### P2-11 · Deep-mode Monte Carlo ran on a *synthesised* trade list — ✅ RESOLVED (Phase 73)
- **Fix:** `pair_ranking.walk_forward()` now returns `stitched_oos_r` (the real
  per-trade R sequence from the stitched OOS windows); `compute_pair_ranking`
  runs Monte Carlo on `[{"pnl": r} for r in stitched_oos_r]` and tags it
  `basis: "real_wfo_oos_trades"`. `_synth_trades` kept only for its shape test,
  marked deprecated.

### P3-8 · Discovery is 1h/4h/1d only
- Same root cause as P1-6b (no intraday OHLCV). The SMC strategy family is
  designed for sub-1h structure, so the 1h discovery verdict is "NO ROBUST EDGE
  FOUND" — honest, but the interesting timeframes are unreachable until an
  intraday provider exists.

---

## P2 — Macro test suite assumes no live provider *(surfaced + fixed Phase 69)*

### P2-9 · 4 macro tests hard-asserted `seed_demo` / `provider_is_live is False` — ✅ RESOLVED (Phase 69)
- **Was:** `test_stage18_macro.py::{test_macro_responses_carry_provenance,
  test_ai_context_includes_bounded_macro_section}` and
  `test_phase64_macro_scorecard.py::{test_scorecard_response_shape,
  test_every_response_carries_provenance}` failed once `.env` configured a live
  FRED provider (`MACRO_DATA_PROVIDER=fred`) — the responses correctly reported
  `provenance="live"` but the tests asserted `seed_demo` unconditionally.
  Reproduced on clean `HEAD` (`04d43c9`); not a Phase-69 code regression.
- **Fix:** module-level `_LIVE_MACRO` flag (evaluated after `api.main` import so
  `.env` is loaded); the `seed_demo` / `provider_is_live is False` assertions are
  now gated on `not _LIVE_MACRO`, while shape + `provenance in {...}` is asserted
  unconditionally.

### P3-7 · `test_phase68_invariants.py::test_invariant_no_evidence_after_as_of` is order-dependent
- Run **alone** it fails 8/19 with `ValueError: Invalid isoformat string: '2025-01'`
  when the live yfinance feed is reachable — a seasonality/window timestamp is a
  `YYYY-MM` label rather than ISO in some live-data path. In the **full suite** it
  passes (earlier tests warm `market_data` caches / trip the feed-down
  short-circuit first). Pre-existing — reproduces on clean `HEAD` (`04d43c9`),
  unrelated to Phase 69.
- **Recommended fix:** make the test parse defensively (skip non-ISO) or, better,
  fix `market_evidence_engine` to only ever emit ISO timestamps on evidence
  items; add `historical_market_data.set_test_provider` isolation to the file's
  autouse fixture so it no longer depends on live reachability.

---

## P1 — Important

> **All P1 items below were RESOLVED in Phase 62** (`perf: database pooling,
> API latency, cold-load & bundle`). Kept here for history; see
> `PERFORMANCE_REPORT.md` for the full write-up and measurements.

### P1-1 · No database connection pooling — ✅ RESOLVED (Phase 62)
- **Was:** `database.get_connection()` opened a fresh `psycopg2.connect()` every
  call — **~280 ms handshake** measured — on ~150 call sites. Dominant cause of
  navigation slowness.
- **Fix:** `psycopg2.pool.ThreadedConnectionPool` in `database.py`, lazy +
  fork-safe, handed out via a transparent `_PooledConnection` proxy whose
  `.close()` returns the socket to the pool. Idle connections re-validated
  (`SELECT 1`) past `DB_POOL_IDLE_PING` s; pool exhaustion falls back to a
  direct connection. SQLite path unchanged. No new dependency. Config:
  `DB_POOL_{ENABLED,MIN,MAX,IDLE_PING}`.
- Covered by `tests/test_db_pool.py` (10 tests: reuse, return-not-close,
  double-close, delegation, idle revalidation, dead-connection discard,
  exhaustion fallback, shutdown).

### P1-2 · `/api/operations/audit` uncached (~1.3 s) — ✅ RESOLVED (Phase 62)
- **Fix:** 12 s snapshot cache keyed by `limit` in
  `api/routers/operations.py` (`invalidate_audit_cache()` for any writer).
  `execution_orders` is append-only and broker transmission is BLOCKED, so it
  barely changes. Warm p50 1420 → 2.8 ms.

### P1-3 · `/api/operations/system` uncached (~0.7 s) — ✅ RESOLVED (Phase 62)
- **Fix:** 8 s cache on the PAPER system-health gate in the new
  `api/system_health_cache.py`, shared by `get_system` and the command-centre
  `_safety` section. **Not** placed inside `system_health.py` — real
  execution-gating still calls the authoritative evaluator directly. Warm p50
  760 → 2.0 ms; also removes ~250 ms from the command-centre fan-out.

### P1-4 · Cold-load cache miss + connection cost stacks — ✅ RESOLVED (Phase 62)
- **Fix:** pooling (P1-1) plus a best-effort startup warm-up in the FastAPI
  `lifespan` (`api/main.py`) that primes the heavy routes before uvicorn
  accepts traffic (`TL_SKIP_WARMUP=1` to disable). Cold `/api/watchlist`
  1056 → ~1 ms in the deployed process.

---

## P2 — Improvement

### P2-1 · Frontend bundle is one 510 kB chunk — ✅ RESOLVED (Phase 62)
- **Fix:** route-level `React.lazy` for all ~20 non-landing pages + a
  `react-vendor` `manualChunks` split (`frontend/src/App.tsx`,
  `frontend/vite.config.ts`). Initial JS 510 kB → 264 kB `index` + 51 kB
  `react-vendor` (~97 kB gzip vs ~137 kB); route chunks 0.4–22 kB each, loaded
  on first visit. Chunk-size warning gone. `index.js` at 264 kB is the
  remaining shared core — split further only if it grows.

### P2-2 · Inconsistent `typing` imports / minor unused imports across routers
- **Location:** `api/routers/intelligence.py` (`Dict, Any, Optional, List` unused),
  `api/routers/market.py` (`HTTPException`), `api/routers/preferences.py`
  (`DEFAULT_PREFERENCES`), `api/routers/research.py` (`pd` — only in a string
  annotation).
- **Impact:** cosmetic; slightly noisy for a new reader.
- **Recommended solution:** a one-pass import tidy with `ruff`.
- **Why deferred:** "do not refactor working code purely for style" — these are
  pre-existing and harmless. The two imports *introduced* during recent stages
  were removed this pass.

### P2-5 · Command-centre overview fans out to ~8 concurrent pool checkouts
- **Location:** `api/routers/command_center.py :: get_overview`
- **Impact:** the 8 section builders run in a `ThreadPoolExecutor`, so one
  *cold* overview request can check out up to ~8 pooled connections at once.
  Phase 63 pool-stress (unreliable TestClient harness) showed
  `/api/command-center/overview` degrading non-linearly past ~pool size while
  `/api/positions` scaled cleanly. `overflow_direct` fires under concurrent
  cache-miss → slow ~400 ms direct connects (no errors, no leaks). Warm cost is
  ~15 ms and single-user is unaffected; this is a **concurrency** soft spot.
- **Recommended solution:** measure first with a real `uvicorn` + `wrk`/`locust`
  load test. Then one of: build the (now mostly cached) sections sequentially;
  cap `max_workers`; or give each request a small connection budget. Phase 63
  tried "sequential" — marginal single-user gain (~4 ms), inconsistent
  concurrent result under TestClient — and reverted it pending a real test.
- **Why deferred:** does not affect the current single-instance deployment;
  needs a trustworthy load generator to size the fix.

### P2-3 · `database.py` is a 900-line grab-bag
- **Location:** `database.py`
- **Impact:** schema init, per-feature CRUD, caching and the dual-backend
  placeholder logic all live in one file. Hard to navigate.
- **Recommended solution:** split into `db/connection.py`, `db/schema.py`,
  `db/<feature>.py` — but only alongside P1-1 (they touch the same code).
- **Why deferred:** high-churn file used everywhere; not worth the regression
  risk outside a dedicated persistence change.

### P2-4 · Two legacy surfaces (`app.py`, `server.py`) still in the tree
- **Impact:** a new reader can't immediately tell which backend is "the" backend.
- **Recommended solution:** `CURRENT_ARCHITECTURE.md` now states it explicitly;
  a future call can retire `server.py` once nothing launches it, and retire
  `app.py` after the remaining workflow migration.
- **Why deferred:** retirement is a separate owner decision
  (`STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md`).

---

## P3 — Nice to have

### P3-1 · `research_analytics` MAE/MFE approximation
- **Location:** `research_analytics.calculate_trade_r_multiples`
- **Impact:** when a trade record lacks `mae`/`mfe`, the function substitutes a
  fixed heuristic (0.8R / 0.2R). Fine for the demo dataset, misleading if real
  excursion data becomes available.
- **Recommended solution:** compute true MAE/MFE from bar data when the
  backtester provides it.

### P3-2 · Command-centre concurrent fan-out has no per-section timeout
- **Location:** `api/routers/command_center.py :: get_overview`
- **Impact:** a hung engine call would hold the request for the client's whole
  timeout (sections are `ThreadPoolExecutor` futures with no `timeout=`).
- **Recommended solution:** `fut.result(timeout=5)` per section → degrade that
  section.
- **Note (Phase 62):** still open, but much lower risk now — the two sections
  that made real DB round-trips (`_safety`, `_research_notes`) are cached, so
  the common path no longer blocks on I/O.

### P3-4 · Cold `/api/operations/audit` first hit ≈ 570 ms
- **Location:** `api/routers/operations.py :: get_audit` +
  `xauusd_research_decision_audit.ResearchDecisionAuditEngine.get_audit_history`
- **Impact:** the very first request (before the 12 s cache fills / outside the
  startup warm-up) does a `LIMIT 1000` ledger read + 4 sequential
  `execution_orders` queries. Warm is 3 ms.
- **Recommended solution:** one combined query for the counts + rows; smaller
  ledger limit or a dedicated count query.

### P3-3 · `PlaceholderPage` / `ZoneOverviewPage` are dead-ish
- **Location:** `frontend/src/pages/`
- **Impact:** `PlaceholderPage` is referenced as a fallback but every nav item
  is now live, so it never renders. Harmless.
- **Recommended solution:** keep as the fallback contract; no action.

---

## Phase 68 — Historical Market Evidence

### P1-6 · Persisted historical OHLCV store — ✅ SOFTWARE RESOLVED (Phase 69) / ⚠️ DATA DEPTH REMAINS
- **Phase 69:** `historical_candles` table (in `database.init_db`, dialect-safe) +
  `historical_data_store.py` (validated duplicate-safe upsert, as-of read,
  coverage, gap detection, sufficiency gate) + `market_data_ingest.py`
  (`python -m market_data_ingest --universe`). The store is registered as the
  Phase-68 `auto` historical provider, so `get_candle_window(as_of=<past>)` and
  Phase-67 historical `TECHNICAL` / `SMC` / `REGIME` light up **wherever the store
  has coverage**. An empty store still returns `None` — the honest gap, now
  closeable by ingestion rather than by a vendor.
- **Data depth remains (P1-6b/c):** the only wired source is yfinance —
  probed 2026-09 (GC=F): **1h/4h/1d** real multi-year; **5m/15m ~70 d** (`PARTIAL`);
  **1m ~8 d** (`INSUFFICIENT_HISTORICAL_DEPTH` — the frozen Gold contract's native
  TF). FX comes only as Yahoo `=X` synthetic spot (no real volume). Native Gold
  revalidation and real intraday discovery are **BLOCKED BY DATA AVAILABILITY**.
- **Phase 73 built the provider architecture for either fix:**
  `historical_provider.HistoricalIntradayProvider` protocol + `ProviderCapability`
  (decides `INSUFFICIENT_HISTORICAL_DEPTH` before ingestion) + `EnvKeyVendorProvider`
  (`HISTORICAL_OHLCV_PROVIDER` / `HISTORICAL_OHLCV_API_KEY`, env-only, ships
  disabled). Add a vendor adapter + `historical_provider.register(...)`. See
  `docs/PHASE_73_INTRADAY_DATA.md`.

### P2-7 · Phase-55 `evaluate_asset_edge` still returns symbol-keyed priors — ⚠️ PARTLY RESOLVED (Phase 68)
- **Was:** `TechnicalStructureFactorEngine` / `SmartMoneyStructureFactorEngine` /
  `SeasonalityFactorEngine` / `MarketRegimeFactorEngine` return fixed
  deterministic scores.
- **Phase 68:** the Phase-67 fusion `TECHNICAL` / `SMC` / `SEASONALITY` / `REGIME`
  categories now come from `market_evidence_engine` (real EMA/RSI/MACD/ATR,
  candle-derived SMC, sample-sized seasonality, per-benchmark regime). The
  Phase-55 prior is used **only** in live mode when no candle window resolves,
  and only as a `NOT_APPLICABLE` context item tagged
  `provenance="deterministic_prior"`, `source="model_prior"` — never as observed
  evidence, never in historical mode.
- **Remaining:** `asset_edge_intelligence.evaluate_asset_edge` itself is
  unchanged (still serves `/api/intelligence/asset-profile` for back-compat).
  Delete the prior code once P1-6 lands.

### P2-8 · Cross-asset regime historical reconstruction — ⚠️ PARTLY RESOLVED (Phase 68)
- **Phase 68:** `market_evidence_engine.regime_evidence(as_of)` pulls a
  per-benchmark as-of candle window and classifies with the same signals /
  thresholds as `CrossAssetRegimeEngine`; a missing benchmark is `MISSING_INPUT`,
  never zero. Works whenever candle windows resolve (see P1-6).
- **Remaining:** `CrossAssetRegimeEngine` live path (`/api/intelligence/summary`)
  is unchanged — still live 24h-change only.

### P3-4 · Seasonality needs multi-year daily history *(data limitation)*
- `market_evidence_engine.seasonality_evidence` computes a real day-of-week /
  month tendency with an explicit `sample_size`, but the live feed only supplies
  ~30 daily bars → almost always `INSUFFICIENT_EVIDENCE`. Honest, not fabricated.
- **Recommended solution:** a multi-year daily OHLCV provider.

### P3-6 · `GET /api/intelligence/asset/{asset}` cold ≈ 1–2.5 s (first process hit)
- **Impact:** one-off per-process cost — first-time init of the Edge / Macro
  engines **plus** (Phase 68) the live candle fetch for the asset + 7 regime
  benchmarks. Warm is ~6–8 ms; historical-with-provider cold ≈ 46 ms.
- **Mitigation in place:** `api/main.py` `_warm_up()` primes `…/asset/XAUUSD` at
  startup; `historical_market_data` trips a 120 s "live feed down" short-circuit
  when offline so it does not repeat socket timeouts.
- **Recommended solution:** none needed unless a benchmark shows a real user
  hitting it cold; would otherwise chase the shared Phase-56 macro-scorecard
  ~446 ms path, which the phase brief explicitly says not to rewrite.

---

## Phase 63 verification (no code changes)

Phase 62's pooling / caching / code-splitting were re-measured and confirmed
stable and reproducible (`docs/PHASE_63_REPORT.md`). Steady-state DB checkout is
0.036 ms (was ~406 ms); warm navigation endpoints make **zero** DB round-trips;
initial load is ~500 ms / 309 kB JS. No application-level P1 bottleneck found.
The remaining limit is the managed-Postgres ~85–125 ms query RTT
(infrastructure). New item logged: **P2-5** (command-centre fan-out concurrency).

## Resolved in Phase 62 (performance engineering)

| Was | Fix | Result |
| :-- | :-- | :-- |
| P1-1 no DB connection pooling (~280 ms/connect × ~150 sites) | `psycopg2` `ThreadedConnectionPool` + transparent proxy in `database.py` | connect handshake eliminated; full reuse, no leaks |
| P1-2 `/api/operations/audit` uncached (~1.4 s) | 12 s snapshot cache keyed by `limit` | warm p50 → 2.8 ms |
| P1-3 `/api/operations/system` uncached (~0.8 s) | 8 s PAPER system-health cache (`api/system_health_cache.py`) | warm p50 → 2.0 ms |
| P1-4 cold-load stacking | pooling + FastAPI `lifespan` startup warm-up | cold `/api/watchlist` 1056 → ~1 ms |
| P2-1 one 510 kB JS chunk | route-level `React.lazy` + `react-vendor` split | initial JS −28% gzip; 20 route chunks |
| command-centre overview warm p50 804 ms (p99 3.5 s) | pooling + the two caches above | warm p50 26 ms (p99 137 ms) |

## Resolved during the earlier stabilization pass

| Was | Fix |
| :-- | :-- |
| `api/routers/positions.py:34` — `float(pos.get("tp", 0.0))` crashed on a NULL `tp` (only surfaced under randomized test ordering) | null-safe `_f()` helper for all position numeric fields |
| `/api/alerts` warm p50 ≈ 372 ms (fresh Postgres connection every call) | `get_all_price_alerts(ttl_sec=8.0)` + cache invalidation on create/delete/trigger → warm p50 ≈ 3 ms |
| 2 unused imports introduced in Stages 15/18 (`ai_context.List`, `macro_service._CCY_BY_COUNTRY`) | removed |
