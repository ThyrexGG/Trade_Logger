# TradeLogger — Future Work

*Maintained as the backlog. Nothing here is an active task — the next phase is
chosen separately from the stabilized current state.*

---

## CURRENTLY IMPLEMENTED

React SPA + FastAPI adapter covering: Command Center, Market Workspace, Risk
Gateway, Positions, Price Alerts, Analytics, AI Assistant, Market Intelligence,
Macro Intelligence (demo data), Strategy Lab, Backtesting, Edge Audit, Forward
Evidence & Governance, Journal / Audit / System Health. Read-only Gemini
assistant with an allowlisted context (incl. bounded macro snapshot).
1043 tests passing. Performance baseline measured (`docs/performance_baseline.json`).

---

## DONE

- **Intraday Data Foundation & Native Gold Revalidation (Phase 73)** —
  `historical_provider.py` (formal `HistoricalIntradayProvider` protocol +
  `ProviderCapability` deciding `INSUFFICIENT_HISTORICAL_DEPTH` *before* ingestion
  + `EnvKeyVendorProvider` env-only stub) + `data_coverage.py` (per instrument ×
  timeframe report: `SUFFICIENT` / `PARTIAL` / `INSUFFICIENT_DATA` /
  `PROVIDER_UNAVAILABLE` / `NO_DATA`) + `native_gold_revalidation.py` (runs the
  contract's entry logic at 1m/5m/15m/1h/1d, each labelled NATIVE / NEAR_NATIVE /
  PROXY). Ingested XAUUSD 1m (~8d) / 5m,15m (~70d). **Native 1m =
  INSUFFICIENT_HISTORICAL_DEPTH; native verdict = BLOCKED BY DATA AVAILABILITY;
  best real evidence (5m near-native, ~70d) = −0.032R / N=45, no edge.** Answer to
  the final research question: **NO_VALIDATED_EDGE**. P2-11 resolved (Monte Carlo
  on real WFO OOS trades). `GET /api/research/{data-coverage, historical/providers,
  gold-revalidation/native}`. `docs/PHASE_73_INTRADAY_DATA.md`. +17 tests.
- **Trade Setup Engine (Phase 72)** — `trade_setup.py`: `evaluate_setup()` →
  deterministic `SetupState` (NO_SETUP / WATCH / SETUP_FORMING / READY /
  INVALIDATED / STALE / INSUFFICIENT_EVIDENCE). READY only behind a VALIDATED
  strategy (evidence-gated: `pair_ranking` scorecard STRONG or `gold_revalidation`
  VALIDATED) with every mandatory condition passing and entry/SL/TP objectively
  derivable from the live candle window's ATR. Six mandatory conditions from the
  Phase-67 evidence layer (HTF bias / regime / MTF alignment / SMC trigger /
  session / freshness). `GET /api/trade-setup[/{asset}[/conditions]]`. AI context
  gets a bounded `trade_setups` section + a SYSTEM_INSTRUCTION rule that the model
  may explain but never change the state. Frontend `/workspace/trade-setup`.
  Current output: **NO_SETUP for every instrument** (no validated strategy) — the
  honest, correct state. `docs/PHASE_72_TRADE_SETUP_ENGINE.md`. +14 tests.
  **Phase 69-72 complete.**
- **Gold Revalidation Baseline (Phase 71)** — `gold_revalidation.py` runs the
  frozen contract's closest approximation (`ict_2022_sweep_mss_fvg` = sweep → MSS
  → FVG) through the Phase-70 pipeline on **1h + 1d** (the frozen contract's
  native **1m** is not testable on yfinance — stated up front, not buried),
  produces the old-vs-new comparison, and classifies `EdgeStatus` by objective
  rules. `gold_strategy_baseline.get_gold_baseline()` reflects a persisted
  `gold_revalidation` artifact (`revalidated_metrics` / `wfo_status` /
  `last_validated_at` / `edge_status`). `GET /api/research/gold-revalidation`;
  the Gold detail panel gets an old-vs-new table. `python -m gold_revalidation`.
  Verdict: **DEGRADED / UNVERIFIABLE** — the 1h proxy shows at best a weak
  positive; the native contract can't be tested here. Holdout untouched.
  `docs/PHASE_71_GOLD_REVALIDATION.md`. +10 tests. **Next: Phase 72 Trade Setup engine.**
- **Strategy Discovery & Pair Ranking (Phase 70)** — `strategy_discovery.py`
  (`StrategyDefinition` registry over the existing `strategies/`, store→backtester
  adapter, `discover()` with IS/OOS split + bootstrap CI + scorecard + session /
  regime / temporal breakdowns, `ResearchRankingScore` — decomposable, never a
  market score) + `pair_ranking.py` (universe × strategies, store-based
  walk-forward, Monte Carlo, parameter sensitivity, pair-stability classification,
  leaderboard artifact + `python -m pair_ranking` CLI). Compute is offline-only;
  `GET /api/research/{strategies,strategies/{id},pair-ranking}` read the persisted
  snapshot. Frontend `/research/discovery`. First 1h run verdict: **NO ROBUST EDGE
  FOUND** (honest — the SMC strategies need sub-1h structure the data source
  can't supply). `docs/PHASE_70_STRATEGY_DISCOVERY.md`. +32 tests.
  **Next: Phase 71 Gold revalidation baseline.**
- **Persistent Historical Data Foundation (Phase 69)** — `historical_candles`
  table (`database.init_db`) + `historical_data_store.py` (validated duplicate-safe
  upsert, as-of read, coverage / gap detection, `data_sufficiency` gate,
  `research_artifacts` persistence, Phase-68 `auto` provider adapter) +
  `market_data_ingest.py` (yfinance backfill / incremental, 4h←1h resample, CLI) +
  `research_universe.py` (11 instruments, pip sizes, sufficiency rules,
  intraday-depth honesty) + `gold_strategy_baseline.py` (recovered Phases 14–21
  Gold discovery = the frozen contract; `EdgeStatus` objective rules;
  `INSUFFICIENT_EVIDENCE` until Phase 71). Read-only `GET
  /api/research/{historical/coverage,universe,gold-baseline}`. Resolves P1-6 in
  software; real depth only for 1h/4h/1d (yfinance). Store ships empty.
  `docs/PHASE_69_HISTORICAL_DATA_FOUNDATION.md` + `docs/GOLD_STRATEGY_BASELINE.md`.
  +44 tests. **Next: Phase 70 strategy-discovery framework.**
- **Historical Market Evidence (Phase 68)** — `historical_market_data.py`
  (as-of candle window, `close <= as_of` truncation, provider registry) +
  `market_evidence_engine.py` (real EMA/RSI/MACD/ATR + MTF EMA bias; candle-
  derived SMC via the existing `market_data` functions; sample-sized seasonality;
  per-benchmark cross-asset regime with `MISSING_INPUT`). Wired into Phase-67
  `TECHNICAL/SMC/SEASONALITY/REGIME`; Phase-55 priors demoted to labelled
  `deterministic_prior` context (live-only, never historical, never scoring).
  `EvidenceItem` gained `timeframe`/`latest_input_timestamp`/`calculation_window`;
  `AssetIntelligenceSnapshot.from_dict` added for research storage / audit replay.
  **Data limitation:** repo ships no historical OHLCV — historical `as_of` needs
  `HISTORICAL_OHLCV_PROVIDER`. `docs/PHASE_68_HISTORICAL_MARKET_EVIDENCE.md`.
  +54 tests.
- **Unified Evidence Fusion (Phase 67)** — `api/evidence_model.py` +
  `api/evidence_fusion.py` + `GET /api/intelligence/asset/{asset}`. One canonical,
  timestamp-correct, evidence-backed asset context object orchestrating the
  existing Phase-55/56/57/64/66 engines (reimplements none). Categories
  `TECHNICAL/SMC/MACRO/COT/REGIME/SEASONALITY/SENTIMENT`; explicit states
  (`PROVIDER_UNAVAILABLE` ≠ `INSUFFICIENT_EVIDENCE` ≠ neutral); no blended
  composite; cross-category conflict represented not averaged; independent
  backend look-ahead guard; historical `as_of` mode (MACRO+COT reconstructable).
  Asset Deep Dive `EvidenceFusionPanel` + AI `asset_evidence` context.
  `docs/PHASE_67_EVIDENCE_FUSION.md`. +49 tests (1226 passing).
- **Performance phase (Phase 62)** — DB connection pooling, TTL caches on
  `/api/operations/{audit,system}` and command-centre sections, FastAPI startup
  warm-up, frontend route-level code splitting. All warm API p50 ≤ 40 ms; cold
  data path −85–99%. See `PERFORMANCE_REPORT.md` + `PHASE_62_REPORT.md`.
- **Performance verification (Phase 63)** — re-measured Phase 62 (stable, no
  regression), verified pool reuse + cache correctness, measured real browser
  navigation. No P1 bottleneck; next lever is P2-5 (load-test first) or the
  managed-DB RTT (infra). `PHASE_63_REPORT.md`. No code changed.

## NEXT (small, well-scoped, low risk)

- **Command-centre fan-out concurrency** (`TECHNICAL_DEBT.md` P2-5) — Phase 63
  found the 8-way `ThreadPoolExecutor` multiplies pool checkouts under
  concurrent cache-miss. Do a real `uvicorn` + `wrk`/`locust` load test first,
  then pick: sequential build / `max_workers` cap / per-request budget. Folds in
  P3-2 (per-section timeout).
- **Combine the `/api/operations/audit` cold queries** (`TECHNICAL_DEBT.md` P3-4).
- **Import / lint tidy** with `ruff` across `api/` (P2-2).

## LATER (bigger, needs its own design + regression)

- **Timestamp-correct market-structure factors** (`TECHNICAL_DEBT.md` P2-7/P2-8)
  — back the Phase-55 `TECHNICAL`/`SMC`/`SEASONALITY` factor engines and the
  cross-asset regime engine with real, as-of-aware inputs so Phase-67 historical
  mode can include them. Then a defensible cross-category weighting framework
  becomes possible (currently the layer deliberately exposes an evidence matrix,
  not a composite).
- **Register a retail-sentiment provider** under the Phase-66 registry
  (`Capability.RETAIL_SENTIMENT`) so the `SENTIMENT` category stops being
  `PROVIDER_UNAVAILABLE`.

- **`database.py` split** into `db/` submodules (the pool now lives at the top
  of it; a `db/connection.py` is the natural first slice).
- **Co-located Postgres / read replica** — the pool removed the connect
  handshake but not the ~125 ms/query RTT to the managed instance. This is an
  infra decision, and the only structural fix left for DB-bound endpoints.
- **Migrate the remaining Streamlit workflows:** notification-rules engine
  (`alerts.get_alert_rules` / `save_alert_rules`), daily-command-centre note /
  snapshot *writing*, AI Market Context (Ollama), USDJPY / True-MTF research
  labs, adversarial audits. Each is an independent unit; see
  `STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md §11`.
- **Retire `server.py`** once nothing launches it; then evaluate retiring
  `app.py`.
- **True MAE/MFE from bar data** in `research_analytics` (`TECHNICAL_DEBT.md` P3-1).

## PARKED — Macro "EdgeFinder-style" scorecard layer

Explicitly parked (Stage 18 §18I). **Do not implement in an unrelated task.**
All of the following are additive on top of the Stage 18 foundation and require
the user's reference screenshots to specify:

1. **Real macro data provider** — a live economic-calendar feed behind the
   `MacroDataProvider` protocol (`api/macro_provider.py`). Server-side
   credentials, `provider_is_live = True`, events `provenance = "live"`.
2. **Composite integer bias score + gauge UI** per instrument (the seed engine
   already produces a float −100..100 score; needs bucketing + a gauge component).
3. **Per-instrument 6-category scorecard** (Technical Signal / Institutional
   Activity (COT) / Sentiment Bias / Eco Growth / Jobs Market / Inflation), each
   Bullish/Bearish/Neutral with a sub-score and "X vs. forecast" comparison rows.
   Data mostly exists in `macro_intelligence_engine` factor groups + the
   surprise engine; needs a `/api/macro/scorecard/{instrument}` shape + React.
4. **"Score over time" sparkline** — start writing
   `macro_intelligence_engine.MacroIntelligenceSnapshotStore` on a schedule, add
   a `/api/macro/.../history` endpoint, render a sparkline.
5. **Per-country economic heatmaps** (US / EU / UK / JP / CA / AU / NZ / CH) —
   `economic_heatmap.EconomicHeatmapEngine` exists (US-centric, 5 categories);
   needs a per-country parameter + dashboard wiring.
6. **Dedicated COT / Crowd-Sentiment panels** — `SENTIMENT_POSITIONING` factor
   group + `COT_NET_POSITIONING` seed exist; surface them as first-class sections.

**Constraints for whoever picks this up:** keep `seed_demo` / `provenance` /
`INSUFFICIENT_EVIDENCE` / read-only behaviour; never fabricate macro data;
contextual intelligence must never become an execution trigger.

## PARKED — not planned

- Any form of live / paper / shadow / automated execution in the React SPA.
- Broker transmission, order routing, position mutation endpoints.
- Enabling `LIVE_AUTOMATION_ENABLED`.
- Turning macro / technical / sentiment / regime signals into trade actions.
