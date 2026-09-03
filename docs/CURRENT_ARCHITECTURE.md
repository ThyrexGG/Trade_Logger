# TradeLogger — Current Architecture

*Plain-English map of the codebase as of the stabilization pass (commit after `534f574`).
Written so a new AI agent or developer can orient without reading the whole repo.*

TradeLogger is a **trading terminal + research lab + market/macro intelligence +
forward-evidence governance** app. It has one modern stack (React SPA + FastAPI
adapter) and two legacy surfaces kept for reference.

---

## 1. The three application surfaces

| Surface | Entry point | Port | Status |
| :-- | :-- | :-- | :-- |
| **React SPA + FastAPI adapter** (the current product) | frontend: `frontend/` (Vite) · backend: `api/main.py` (`api.main:app`) | dev: 5173 (Vite) → proxy → 8010/8000 (uvicorn) | **ACTIVE** — all new work goes here |
| **Streamlit app** (`app.py`) | `streamlit run app.py` | 8501 | **LEGACY / golden reference** — kept, untouched. Power-user workflows not yet migrated (manual paper entry, AI Market Context/Ollama, notification-rules engine, daily-command-center writes, some research labs). See `STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md`. |
| **`server.py`** ("Trade Logger Pro Engine API") | `python -m uvicorn server:app` | 8000 | **LEGACY** — Flutter-era engine that also serves the old Flutter web build. Not part of the React SPA. `start_flutter.bat` / `start_silent.vbs` launch it. Do not extend. |

> The React SPA talks **only** to `api.main:app`. `api.main:app` is a *thin
> adapter* — it never re-implements trading/research/analytics logic; it calls
> the authoritative Python engines and serializes their output.

---

## 2. Frontend (`frontend/`)

Vite 6 + React 19 + TypeScript ~5.7 + Tailwind v4 + `react-router-dom` v7. **No
state-management library, no charting library** (small inline SVG + CSS bars).

```
frontend/src/
  main.tsx / App.tsx        router; App.tsx maps nav-item id -> page component
  lib/navigation.ts         SINGLE SOURCE OF TRUTH for sidebar + breadcrumbs + command palette
  lib/health.tsx            HealthProvider — slow poll of /api/health, never blocks nav
  lib/use*.ts               one data hook per feature; the recurring pattern is:
                              - one request per resource (or one batched allSettled)
                              - [nonce]-only useEffect deps (never object deps -> no request storm)
                              - AbortController + request-id / disposed race guards
                              - slow interval refresh, paused when document.hidden
                              - last-good data kept on error
  api/client.ts             apiGet / apiPost / apiPatch / apiDelete (native fetch, typed)
  api/<feature>.ts          typed endpoint wrappers
  types/<feature>.ts        response contracts
  pages/<Feature>Page.tsx   one page per route (24 pages); all but the landing +
                            zone/overview pages are React.lazy() -> own JS chunk,
                            loaded on first navigation behind one <Suspense>
  components/
    shell/                  AppShell, Sidebar, TopBar, Breadcrumbs, CommandPalette,
                            PageContainer, RouteFallback (Suspense fallback)
    <feature>/              feature components; operations/primitives.tsx + intelligence/primitives.tsx
                            + research/primitives.tsx hold the shared cards / metrics / tags / Sparkline
  styles/tokens.css         design tokens (derived from ui_components.py TOKENS)
```

Design tokens live as CSS vars in `index.css`, mapped via Tailwind `@theme inline`.

### Routes / navigation zones

| Zone | Routes |
| :-- | :-- |
| **Trading Workspace** (`/workspace`) | `/workspace/command-center`, `/workspace/market`, `/workspace/risk`, `/workspace/positions`, `/workspace/alerts`, `/workspace/analytics`, `/workspace/assistant` |
| **Research & Strategy Lab** (`/research`) | `/research/intelligence` (+ `/asset/:symbol`), `/research/strategy`, `/research/backtest`, `/research/audit`, `/research/macro` |
| **Forward Evidence & Governance** (`/evidence`) | `/evidence/forward`, `/evidence/statistics`, `/evidence/governance` |
| **Operations, Journal & Audit** (`/operations`) | `/operations/journal`, `/operations/audit`, `/operations/system` |

`ZoneOverviewPage` renders a zone landing page; `PlaceholderPage` is the fallback
for any nav item without a real page (currently none — all 12+ items are live).

---

## 3. Backend adapter (`api/`)

FastAPI, one router per feature. **Every router is read-shaped**; the only
non-GET verbs are: `POST /api/risk/preview` (calc only), `POST /api/research/backtest`
+ `/api/research/audit` (run a backtest, calc only), `PATCH /api/operations/journal/{id}`
(annotation edit), `POST/DELETE /api/alerts` (price-alert CRUD), `POST /api/ai/chat`
(generate text), `PUT /api/preferences` (UI layout). **No order / execute / broker / automation endpoint exists.**

```
api/
  main.py               FastAPI app; registers 15 routers; CORS allows GET/POST/PUT/PATCH/DELETE
  schemas.py            all Pydantic request/response models (numbered sections 1..15)
  routers/
    health, watchlist, market, preferences, intelligence, risk, positions,
    evidence, research, operations, alerts, analytics, command_center, ai, macro
  ai_context.py         Stage 15C — allowlisted read-only snapshot handed to Gemini
  gemini_client.py      Stage 15C — server-side Gemini wrapper (key from env, never returned)
  macro_provider.py     Stage 18A — MacroDataProvider abstraction + normalizer
  macro_service.py      Stage 18 — orchestrates the macro engines, tags provenance
  surprise_engine.py    Stage 18B — deterministic per-indicator economic-surprise config
```

### Router -> engine map (what each area actually calls)

| Area | Router | Authoritative engine(s) |
| :-- | :-- | :-- |
| Watchlist / market snapshot | `watchlist`, `market` | `trading_workspace_cockpit.TradingWorkspaceCockpit` |
| Market intelligence | `intelligence` | `market_intelligence_command_center.UnifiedMarketIntelligenceAggregator`, `market_intelligence_scanner`, `economic_heatmap`; **Phase 67** `…/asset/{asset}` → `api.evidence_fusion.get_asset_intelligence` (orchestrates Macro-scorecard / registry / **Phase 68 `market_evidence_engine`** — reimplements none) |
| Risk preview / sizing | `risk` | `risk_gateway.calculate_pre_trade_risk_preview` (currency-aware FX fix in `9.1`) |
| Positions | `positions` | `database.get_open_positions` |
| Analytics | `analytics` | `analytics.calculate_performance_metrics` (byte-parity verified) |
| Backtest / edge audit | `research` | `backtester`, `research_engine`, `research_analytics` |
| Forward evidence | `evidence` | `xauusd_forward_statistical_monitoring.Phase49MonitoringFacade` (cached snapshot) |
| Journal / audit / system | `operations` | `database.get_closed_trades`, `execution_orders` table, `system_health.evaluate_system_health` |
| Command centre | `command_center` | concurrent fan-out to analytics + positions + alerts + intelligence + evidence + `DailyResearchJournal` |
| Price alerts | `alerts` | `database.*_price_alert` + `symbol_mapping` |
| AI assistant | `ai` | `api.ai_context` (allowlisted) + `api.gemini_client` |
| Macro | `macro` | `macro_intelligence_engine.*` (Phase 56) + `api.macro_provider` + `api.surprise_engine` |

---

## 4. Data sources

| Data | Where it comes from |
| :-- | :-- |
| Live prices / OHLC | `market_data.py` (broker feeds / yfinance for backtests) |
| Trades / positions / accounts | SQLite/Postgres tables, populated by the standalone sync daemons `mt5_sync.py`, `auto_sync.py`, `capital_sync.py` + the reconciliation worker — **not** by any UI |
| Macro / economic events | `api/macro_provider.py` → default `SeedDemoProvider` wraps `macro_intelligence_engine.EconomicDataRegistry` (**synthetic / seeded**, USD/EUR/GBP/JPY only) + `xauusd_daily_preflight.StandardMacroCalendarProvider`. Every macro response is tagged `provenance: "seed_demo"`. |
| Research backtests | `backtester.run_backtest` over yfinance history |
| Forward evidence | `closed_trades` filtered by `source` (`PAPER` / `SHADOW`), never pooled with the locked historical holdout |

---

## 5. Persistence

`database.py` — dual backend: **PostgreSQL** (cloud, when `DATABASE_URL` is set)
with **SQLite fallback** (`trades.db`, used automatically under pytest via
`PYTEST_CURRENT_TEST`). Schema is created idempotently by `init_db()` and
per-feature `_ensure_*_tables()` helpers. `_DB_CACHE` is a process-level dict
used by the short-TTL read caches.

**Connection pool (Phase 62).** For the Postgres backend `get_connection()`
hands out a connection from a process-wide `psycopg2.pool.ThreadedConnectionPool`
(lazy, fork-safe) wrapped in a `_PooledConnection` proxy — callers use it
exactly as before, and `.close()` returns it to the pool. Idle connections are
re-validated (`SELECT 1`) past `DB_POOL_IDLE_PING` s; pool exhaustion falls back
to a direct connect. Config: `DB_POOL_{ENABLED,MIN,MAX,IDLE_PING}`. The SQLite
path is unpooled (connect is free). The FastAPI `lifespan` primes the pool +
hot routes at startup and calls `close_all_pools()` on shutdown.
`database.pool_stats()` exposes reuse / ping / fallback counters.

Key tables: `raw_deals`, `closed_trades`, `open_positions`, `account_metadata`,
`price_alerts`, `app_settings`, `execution_orders`, `execution_audit_log`,
`received_signals`, `xauusd_context_snapshots`, `xauusd_research_notes`,
`macro_intelligence_snapshots`.

---

## 6. Caching

| Layer | Mechanism | TTL |
| :-- | :-- | :-- |
| DB read helpers | `database._DB_CACHE` dict, `get_*(ttl_sec=)` | `closed_trades` 5s, `open_positions` 2s, `price_alerts` 8s (added this pass), `account_balances` short |
| React data hooks | in-hook `useState` + module-level `Map` cache (`useOperations.ts`) | mount-reuse 12s, interval refresh 20–120s (paused when hidden) |
| Forward-evidence read | `Phase49MonitoringFacade.get_cached_forward_state_snapshot` (Stage 3.5D bounded snapshot cache) | thread-safe internal |
| Strategy-lab config | module-scope cache in `useStrategyLab.ts` (static for a session) | session |
| Operations audit response | module TTL cache in `api/routers/operations.py`, keyed by `limit` (Phase 62) | 12s, `invalidate_audit_cache()` |
| PAPER system-health gate | `api/system_health_cache.py`, shared by `get_system` + command-centre `_safety` (Phase 62) | 8s, `invalidate()` |
| Command-centre research notes | module TTL cache in `api/routers/command_center.py` (Phase 62) | 30s |
| Evidence-fusion snapshot | module TTL cache in `api/evidence_fusion.py` (Phase 67), same idiom as the regime cache; `live::` keys 4s, `hist::…::{as_of}` keys immutable for the process; `invalidate()` | 4s / ∞ |
| Candle windows | `market_data._CANDLE_CACHE` (existing, TTL 4s per `sym_tf_count`) reused by Phase-68 `historical_market_data`; a 120s "live feed down" short-circuit avoids repeated socket timeouts when offline | 4s |
| Startup warm-up | FastAPI `lifespan` primes pool + heavy routes before traffic, incl. `…/intelligence/asset/XAUUSD` (`TL_SKIP_WARMUP=1` to skip) | once at boot |

**Freshness rules that caching must never break:** `release_timestamp <= as_of`
(macro / evidence lookahead protection), research reproducibility (fixed seeds),
`as_of` semantics in the evidence pipeline.

---

## 7. State

| Kind | Where |
| :-- | :-- |
| Server state | SQLite/Postgres + the engines' own in-process state |
| Client session state | React component state + the data-hook module caches; `?symbol=` query param carries the selected asset across `/workspace/*` and `/research/intelligence` |
| Persistent user prefs | `app_settings` table via `PUT /api/preferences` (workspace layout) — predates the React migration |
| No global store | deliberately — hooks + URL params only |

---

## 8. Trading safety (where it is enforced)

**Not in the UI, not in the adapter.** Fail-closed logic lives in the engines:

- `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"` — enforced in `execution_pipeline.py`, `broker_adapter.py`, `system_health.py`, `xauusd_forward_end_to_end_proof.Phase50SafetyBarrier`, `xauusd_research_governance.LiveTradingSafetyBarrier`.
- `/api/health` and `/api/operations/system` surface `automation_enabled=false`, `live_broker_transmission=BLOCKED`.
- Strategy contract SHA-256 (`xauusd_market_conditions.FROZEN_CONTRACT_HASH`) is verified byte-exact by `test_phase56_safety` etc.
- The React SPA and every macro / AI / research / analytics module have **no import path** to `execution_pipeline` / `broker_adapter` / `risk_gateway` — asserted by binding + import-graph tests in `test_stage15c`, `test_stage18_macro`.

---

## 9. AI / contextual intelligence

`React chat (/workspace/assistant) → POST /api/ai/chat → api/ai_context.build_context()
(allowlisted read-only snapshot, bounded ~16k chars) → api/gemini_client.generate()
(server-side GEMINI_API_KEY) → Gemini`. Read-only by construction; a fixed
server-side system instruction the user cannot override. Unset key → graceful
`ok:false, error_kind:"not_configured"`. The snapshot now includes a bounded
`macro_intelligence` section (Stage 18H) and a bounded `asset_evidence` section
(Phase 67) — the canonical evidence-fusion snapshot for the current watchlist
highlights, timestamp-correct by construction (no future information reaches the
model through it).

### 9b. Historical Market Evidence (Phase 68)

`historical_market_data.py` — canonical **as-of candle window** interface:
`get_candle_window(asset, timeframe, as_of, lookback)` returns candles truncated
to `candle_close <= as_of` (drops the still-forming candle). Live path wraps
`market_data.get_candles_with_source` (new; also reports which upstream served);
the **synthetic offline fallback is never treated as real data** and trips a
120 s "feed down" short-circuit. Historical path dispatches to
`HISTORICAL_OHLCV_PROVIDER` (Phase-66-style registry) — the repo ships **no**
historical OHLCV store, so the default resolves to `None`; tests install a
deterministic in-process provider via `set_test_provider`.

`market_evidence_engine.py` — real, timestamp-safe evidence from a candle
window: EMA20/50/200 + RSI(14) + MACD + ATR(14) + MTF EMA bias (technical);
reuses `market_data.detect_fvgs / detect_order_blocks / calculate_market_structure
/ calculate_liquidity_zones` (SMC); day-of-week / month return tendency with an
explicit `sample_size` (seasonality); per-benchmark as-of windows with
`MISSING_INPUT` for absent series (regime). Emits canonical
`api.evidence_model.EvidenceItem` (Phase-67 model, reused — no parallel class),
each with `timeframe` / `latest_input_timestamp` / `calculation_window`.

`api/evidence_fusion.py` — `TECHNICAL / SMC / SEASONALITY / REGIME` now prefer
`market_evidence_engine`. A Phase-55 deterministic prior is used **only** in live
mode when no candle window resolves, and only as a `NOT_APPLICABLE` context item
tagged `provenance="deterministic_prior"`, `source="model_prior"` — never
`historical_ohlcv`, never driving direction/score/cross-category. Full reference:
`docs/PHASE_68_HISTORICAL_MARKET_EVIDENCE.md`.

### 9a. Unified Evidence Fusion (Phase 67)

`api/evidence_model.py` (canonical `EvidenceItem` / `CategoryEvidence` /
`AssetIntelligenceSnapshot` + `EvidenceState` enum) + `api/evidence_fusion.py`
(`get_asset_intelligence(asset, as_of, timeframe)`). One orchestration layer that
normalises the existing Phase-55/56/57/64/66 engine output into a single
timestamp-correct evidence object. Computes nothing new — no new score, no new
data source, **no blended composite**. Categories:
`TECHNICAL · SMC · MACRO · COT · REGIME · SEASONALITY · SENTIMENT` (only those
with a real source are populated; the rest are `INSUFFICIENT_EVIDENCE` /
`PROVIDER_UNAVAILABLE`, kept distinct from neutral). Cross-category disagreement
is represented, never averaged away. Historical `as_of` mode reconstructs
`MACRO` + `COT` only (registry-backed); live-only categories are honestly marked.
Exposed read-only via `GET /api/intelligence/asset/{asset}`; consumed by the
Asset Deep Dive (`EvidenceFusionPanel`) and the AI context. Full reference:
`docs/PHASE_67_EVIDENCE_FUSION.md`.

---

## 10. Research (backtesting / WFO / Monte Carlo / ML)

`backtester.py` (`run_backtest` / `run_walk_forward` / `run_monte_carlo`),
`research_engine.py` (`ThreeLayerDataSplitter`, `BootstrapEstimator`,
`MultipleTestingTracker`, `ScorecardClassifier`, `ResearchExperiment`),
`research_analytics.py` (R-multiples, liquidity/session/confluence attribution,
execution-stress, expectancy drift), `ml_trainer.py`, `strategies/` (registry +
SMC / MTF utilities), `true_mtf_engine.py`, `usdjpy_*.py` labs. Exposed via
`/api/research/{strategy,backtest,audit}`.

---

## 11. Evidence (forward validation / governance)

`xauusd_forward_statistical_monitoring.py` (Phase 49 facade), `xauusd_forward_validator.py`
(forward journal), `xauusd_forward_integrity.py` (contract guard),
`xauusd_research_decision_audit.py` (decision ledger), `xauusd_alert_engine.py`
(surveillance events). Exposed via `/api/forward-evidence/state`. The **locked
historical holdout** (N=82, E[R]=+0.637R) is never pooled with forward data.

---

## 12. Testing

`tests/` — run with `pytest tests/ -p no:randomly`.
Baseline: **1281 passed, 6 skipped, 0 failed (~169s)** (Phase 68; was 1226/6 at Phase 67).

Naming: `test_phaseNN_*` = the Streamlit-era feature phases (still the bulk of
coverage); `test_stageNN_*` = the React-migration stages; `test_*_safety.py` /
`test_*_isolation` / `test_*_lookahead` = invariant guards. Two gitignored
root-level scratch files (`test_backtester.py::test_lot_rounding`, `test_ws.py`)
fail outside the tracked suite — pre-existing, unrelated, not counted.

`performance_benchmark.py` (added this pass) = an in-process latency baseline
diagnostic, not a test.
