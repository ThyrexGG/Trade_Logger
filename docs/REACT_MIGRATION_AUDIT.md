# MASTER ARCHITECTURAL AUDIT & MIGRATION BLUEPRINT: TRADELOGGER FAST TERMINAL

**Document Version:** 1.2.0 (Pre-Stage-2 Architectural Guardrails & Lightweight Health Correction)  
**Date:** 2026-09-02  
**Target Architecture:** React 19 + TypeScript + Vite + Tailwind CSS Frontend / FastAPI Adapter + Python 3.14 Authoritative Core Backend  
**Pre-Migration Test Baseline:** All pre-migration tests passing, plus all newly introduced migration tests must pass (100% passing, coverage strictly increases).  
**Strategy Contract SHA-256:** `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` (Frozen & Byte-Exact Immutable)

---

## 0. Fundamental Migration Rules & Invariants

> [!IMPORTANT]
> **PERMANENT RULE: NO MASS REWRITE — INCREMENTAL MIGRATION ONLY**  
> TradeLogger will **NOT** be rewritten. It will be migrated incrementally.
> - **PRESERVE (Authoritative Python Core)**: All Python calculation engines, research methodology, mathematical formulas, risk rules, database schema, scientific tests, safety barriers, evidence systems, and the existing Streamlit implementation.
> - **REPLACE GRADUALLY**: Presentation layer, client-side navigation, frontend state management, terminal interaction, and browser rendering.

### Absolutely Frozen Project Safety Invariants
1. **Strategy Contract SHA-256**: `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` (Strictly immutable; never modified, regenerated, or reordered).
2. **Historical Holdout Baseline**: $N=82$, $E[R]=+0.637\text{R}$, $\text{WR}=58.6\%$, $\text{PF}=2.52$ (Locked and unpooled; never merged or altered).
3. **Live Safety Barrier**: `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"` (Permanently fail-closed; no API path may bypass this).
4. **Dataset Isolation**: $IDs_{\text{hist}} \cap IDs_{\text{paper}} = \emptyset$, $IDs_{\text{hist}} \cap IDs_{\text{shadow}} = \emptyset$ (No serialization or caching may merge these datasets).
5. **Streamlit Coexistence**: `app.py` remains 100% operational on port `8501` throughout migration as the fallback, golden reference, and parity benchmark.

---

## 1. Strict API Architectural Rule: FastAPI Is an Adapter Layer, NOT a Second Trading Engine

FastAPI must **NOT** reproduce, duplicate, or independently implement business logic that already exists in the authoritative Python core.

```text
React (Port 5173)
  ↓ HTTP / JSON
FastAPI Adapter (Port 8000)
  ↓ Direct Python Invocation
Existing Authoritative Python Engine (mtf_engine, asset_edge, macro, risk_gateway, etc.)
  ↓ Local Data Access
Existing Data / Calculation Layer & SQLite
  ↓
Normalized Response
```

### FastAPI Role:
- Request parameter validation (Pydantic schemas)
- Serialization and typed response schemas
- HTTP routing and endpoint error handling
- Controlled invocation of existing Python engines
- API-level performance telemetry
- Safe, lookahead-protected caching where applicable

### Forbidden in FastAPI:
- Re-implementing scoring formulas or calculations
- Creating divergent research or trading logic
- Altering thresholds, risk parameters, or evidence rules
- Creating write/execution endpoints during initial read-only stages

---

## 2. Current Architecture Inventory ("WHAT WE HAVE")

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CURRENT TRADELOGGER                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Presentation (Streamlit):                                                   │
│  - app.py (4,428 lines): Monolithic routing, 4 operational zones           │
│  - trading_workspace_cockpit.py: Watchlist, MTF bias bar, Risk Gateway      │
│  - market_intelligence_command_center.py: 6-tab intelligence suite          │
│  - forward_evidence_cockpit.py: 7-tab governance & milestone tracking       │
│  - ui_components.py: Design tokens, 15-state badge language, metric cards   │
│  - command_palette.py & keyboard_shortcuts.py: Terminal hotkeys (Ctrl+K)    │
│  - workspace_layout_manager.py & user_preferences.py: Layouts & state       │
│                                                                             │
│ Authoritative Calculation Engines (Pure Python):                            │
│  - strategies/mtf_engine.py & smc_utils.py: 6-TF liquidity & FVG structure  │
│  - asset_edge_intelligence.py: 11-factor [-100, +100] directional scoring  │
│  - macro_intelligence_engine.py: Canonical registry, z-score surprises      │
│  - cross_asset_regime_engine.py: Macro regime classification & breadth      │
│  - market_intelligence_scanner.py: 23-asset normalized scanning & ranking   │
│  - risk_gateway.py: Pre-trade risk calculator, lot sizing, correlation gate │
│  - execution_pipeline.py: Canonical order submission state machine          │
│  - xauusd_forward_statistical_monitoring.py: Wilson score CIs & milestones  │
│                                                                             │
│ Storage & Infrastructure:                                                   │
│  - SQLite (trading_app.db / trades.db): 10+ indexed snapshot tables         │
│  - In-memory memoization caches: _PRICE_CACHE, _SCAN_CACHE, _REGIME_CACHE   │
│  - application_performance_profiler.py: Server-side timing & P50/P95/P99    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. What We Should Keep, Move, and Remove

### A. WHAT WE MUST KEEP (Authoritative Python Core)
1. **All Python Calculation Engines**: Every mathematical formula, scoring weighting, surprise z-score, and SMC rule remains in Python.
2. **Strategy Contract & Baseline Constants**: Exact SHA-256 and unpooled historical statistics.
3. **Database Schema & SQLite Tables**: `trades`, `open_positions`, `app_settings`, `user_terminal_preferences`, snapshot tables.
4. **Streamlit App (`app.py`)**: Operational on port `8501` as golden reference until migration parity is fully verified.

### B. WHAT SHOULD MOVE (Python Presentation &rarr; React SPA)
1. **Terminal Shell & Navigation**: 4 operational zones, layout manager, persistent telemetry ribbon.
2. **Command Palette & Hotkeys**: `Ctrl + K` search modal and single-key navigation (`1`-`4`, `W`, `C`, `E`, `M`, `J`, `R`) with client-side state.
3. **Watchlist**: Real-time virtualized table with search, class filter pills, and 10 quantitative telemetry fields.
4. **Market Snapshot & Context Panel**: Near-instant cached MTF bias hierarchy, SMC key levels, and market session indicators.
5. **Execution Panel & Active Positions Strip**: Pre-trade risk sizing, worst-case risk ($ / %), target rewards, and MAE/MFE excursion meters.
6. **Market Intelligence Command Center**: 6-tab progressive disclosure dashboard (Opportunity Map, Deep Dive, Heatmap, Correlations, Regime Ledger, Data Health).
7. **Forward Evidence Cockpit**: 4-tier cognitive hierarchy, milestone progression, Wilson score intervals, and forensic chain audit.

### C. WHAT SHOULD BE REMOVED / MADE OPTIONAL (Cost Elimination)
1. **Default Heavy TradingView Iframe**:
   - **Cost**: Adds 800–1,200 ms latency, ~150MB RAM per instance, external network dependency, and browser reflow overhead.
   - **Action**: Removed from default view; replaced with a **Near-instant cached Market Snapshot & Context Panel**. TradingView chart is retained as an optional, on-demand view that never blocks terminal boot.
2. **Monolithic Script Rerun Cascades**: Eliminated completely by React's component-level state updates.
3. **Unnecessary Infrastructure Prohibited**: No Redis, Celery, Kafka, RabbitMQ, Kubernetes, microservices, or separate message queues.

---

## 4. Performance Language & Measurement Framework

### A. Performance Terminology Standard
- **Forbidden**: Literal claims of "Instant 0ms" without empirical proof.
- **Standard**: **Near-instant cached Market Snapshot with measured P50/P95 latency.**
- **Latency Disaggregation**: The migration profiler must measure and report distinct latency segments:
  1. *Python Execution Latency* (Core engine computation)
  2. *API / Server Latency* (FastAPI serialization & routing)
  3. *Network Latency* (Client-server transport)
  4. *Browser Rendering Latency* (DOM reflow & paint)
  5. *React State-Update Latency* (Component lifecycle & re-render)
  6. *Initial Page-Load Latency* (First Contentful Paint / Time to Interactive)
  7. *External Chart Latency* (Iframe loading overhead if enabled)
  8. *Cached vs. Cold Request Latency*

### B. Engineering Targets (To Benchmark, Not Fabricate)
- **Simple UI Interactions**: Target P50 < 100 ms, P95 < 250 ms
- **Navigation (Zone/Tab Switch)**: Target P50 < 150 ms, P95 < 300 ms
- **Asset Selection**: Target P50 < 200 ms, P95 < 400 ms
- **Watchlist Filtering**: Target P50 < 100 ms, P95 < 200 ms
- **Cached API Responses**: Target P50 < 150 ms, P95 < 300 ms

---

## 5. Golden-Reference Parity Verification Architecture

Every migrated API endpoint and React feature must pass golden-reference parity tests comparing FastAPI outputs against the existing Python engine returns.

```text
Existing Authoritative Python Engine Result
                  ↓
          Golden Reference
                  ↓
        FastAPI Endpoint Output
                  ↓
    Normalize Transport Representation (JSON, datetimes, ordering)
                  ↓
    Compare Authoritative Underlying Semantic Values
```

### Parity Principles:
- **Semantic Value Equality**: Compare underlying numbers, scores, states, and text rather than blindly asserting raw JSON string equality.
- **Allowed Transport Differences**:
  - JSON formatting, field key ordering where semantically irrelevant.
  - ISO-8601 UTC timestamp string representation.
  - Strict Pydantic type coercions (e.g. `float` precision formatting).
- **Strictly Forbidden Differences**:
  - Altered numerical values, calculations, edge scores, or z-scores.
  - Modified bias states, regime classifications, or setup states.
  - Altered risk amounts, lot sizes, or stop loss calculations.
  - Modified historical benchmark constants or dataset IDs.
  - Missing evidence fields or fabricated analytical data.

---

## 6. Revised 10-Stage Migration Roadmap & Phased Gates

```text
STAGE 1: Master Architecture Audit & Baseline
[COMPLETE]
    ↓
STAGE 2: Minimal FastAPI Foundation & Strictly Read-Only Vertical Slice
  - /api/health (Extremely lightweight: verifies process status & safety config constants without importing heavy broker infrastructure)
  - /api/watchlist (10-field quantitative data from trading_workspace_cockpit)
  - /api/market/snapshot/{symbol} (MTF hierarchy, SMC levels, session data)
  - Golden-Reference Tests (Semantic parity verification against Python engines)
  - [NO WRITE ENDPOINTS, NO BROKER TRANSMISSION, NO MUTATIONS]
    ↓
[MIGRATION GATE 2: All pre-migration tests + all newly introduced Stage 2 tests = 100% passing]
    ↓
STAGE 3: Expand FastAPI Read-Only Service Layer
  - /api/preferences (GET/PUT user layout & settings)
  - /api/intelligence/* (Summary, Opportunity Map, Asset Profile, Heatmap)
  - /api/risk/preview (POST read-only risk calculation, sizing preview)
  - /api/positions (GET open positions & MAE/MFE metrics)
  - /api/forward-evidence/state (GET 4-tier hierarchy & Wilson CIs)
  - Golden-Reference Parity Tests for expanded endpoints
    ↓
[MIGRATION GATE 3]
    ↓
STAGE 4: React 19 + TypeScript + Vite + Tailwind CSS Project Foundation
  - Initialize `frontend/` project shell with strict TypeScript configs
  - Centralized design tokens (colors, typography, spacing, 15-state badge language)
  - Client-side API service layer with request deduplication
    ↓
[MIGRATION GATE 4]
    ↓
STAGE 5: React Terminal Shell, Navigation & Command Palette (Ctrl+K)
  - 4-zone routing, persistent telemetry ribbon, layout switcher
  - Native React keyboard listeners (`Ctrl + K`, single-key hotkeys `1`-`4`, `W`, `C`, `E`, `M`, `J`, `R`)
  - Form input exclusion (no hotkey collision during typing)
    ↓
[MIGRATION GATE 5]
    ↓
STAGE 6: React Watchlist & Near-Instant Market Snapshot Component
  - 10-field virtualized watchlist table with instant client-side search/filter
  - Near-instant cached Market Snapshot & Context Panel (replacing heavy TradingView iframe)
  - Optional on-demand TradingView chart toggle
    ↓
[MIGRATION GATE 6]
    ↓
STAGE 7: React Pre-Trade Risk Gateway & Active Positions Excursion Strip
  - Order direction toggle, lot size preview, worst-case risk, reward targets
  - Permanent fail-closed LIVE BLOCKED safety banner
  - Open positions table with floating PnL and MAE/MFE progress meters
    ↓
[MIGRATION GATE 7]
    ↓
STAGE 8: React Market Intelligence Command Center & Economic Heatmap
  - 3-second Hero Summary Bar
  - 6-tab progressive disclosure suite (Opportunity Map, Deep Dive, Heatmap, Correlations, Regime Ledger, Data Health)
    ↓
[MIGRATION GATE 8]
    ↓
STAGE 9: React Forward Evidence & Governance Cockpit
  - 4-tier cognitive hierarchy, 14-stage milestone progression ladder
  - Wilson score confidence intervals and immutable forensic evidence chain
    ↓
[MIGRATION GATE 9]
    ↓
STAGE 10: End-to-End Performance Benchmark, Browser QA & Full Regression
  - Real-world P50/P95/P99 latency benchmarks across Workflows A–D
  - Cross-browser QA (Chrome, 1280x720, 1440x900, 1920x1080)
  - Full regression: All pre-migration tests + all newly introduced migration tests = 100% passing
  - Final parity audit vs. Streamlit golden reference
    ↓
[ONLY THEN: Streamlit Legacy UI Retirement Evaluation]
```

---

## 7. Migration Gate Criteria & Rollback Protocol

Every migration stage must satisfy the following checklist before proceeding to the subsequent stage:

```text
[ ] All pre-migration tests + all newly introduced migration tests = 100% passing
[ ] Golden-reference semantic parity verified (FastAPI normalized output == Python engine values)
[ ] Strategy Contract SHA-256 unchanged: 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76
[ ] Historical holdout baseline intact: N = 82, E[R] = +0.637R, WR = 58.6%, PF = 2.52
[ ] Dataset isolation strictly preserved: IDs_hist ∩ IDs_paper = ∅, IDs_hist ∩ IDs_shadow = ∅
[ ] Live execution permanently blocked: LIVE_AUTOMATION_ENABLED = False, LIVE_BROKER_TRANSMISSION = 'BLOCKED'
[ ] Lookahead protection strictly enforced: release_timestamp <= as_of
[ ] No secrets, broker credentials, or environment keys exposed via API
[ ] Real performance measured and documented (no fabricated claims)
[ ] Streamlit fallback operational on port 8501
[ ] Small, atomic Git commit created with clear rollback point
```

If any item fails: **STOP immediately, investigate, fix, and re-verify.**

---

## 8. Stage 3.5 — Read-Path Latency Optimization Sub-Stages (post Gate 3)

Between Migration Gate 3 and Stage 4, the read-only FastAPI endpoints were profiled
and optimized in isolation. Adapter-layer only: no authoritative engine, strategy
math, dataset, or safety-invariant change. Each is one focused commit + a
`tests/test_stage35*.py` suite, benchmarked with an in-process `TestClient` against
live Postgres.

| Sub-stage | Endpoint(s) | Change |
| :-- | :-- | :-- |
| **3.5A** | `/api/market/snapshot/{symbol}`, `/api/preferences`, `/api/positions` | Single-symbol snapshot path (no full-universe scan); thread-safe `_PREFERENCES_CACHE`; `database.get_open_positions(ttl_sec=2.0)`. |
| **3.5B** | `/api/watchlist` | Bounded-concurrency price batching + aligned `market_data._PRICE_CACHE` TTL. |
| **3.5C** | `POST /api/risk/preview` | Reuse the 3.5A 2 s open-position cache; opt-in `risk_gateway.get_pair_correlation(ttl_sec=300)` memo used **only** by the calculation-only preview — `evaluate_trade_risk()` keeps reading correlations uncached. Warm P50 ≈ 1,530  ms → ≈ 2.5 ms. |
| **3.5D** | `GET /api/forward-evidence/state` | `Phase49MonitoringFacade.get_cached_forward_state_snapshot()`: bounded, thread-safe, process-local, 60 s TTL, single-slot; explicitly invalidated by `SequentialEvidenceGovernanceEngine.record_milestone_snapshot()`. The read path no longer calls `Phase50Facade.get_phase50_full_state()` (its output was never used in the response), removing ~15.3 s of Phase 50 work, ~3.1 s of duplicate Phase 49 computation, and — critically — the per-request `xauusd_phase50_operational_audits` INSERT. Warm P50 ≈ 14,650 ms → ≈ 2.3 ms; cold ≈ 1.6 s (one authoritative `evaluate_full_forward_state`). |

**3.5D audit semantics**: the operational-audit INSERT in
`Phase50E2EOperationalProofEngine.audit_end_to_end_pipeline()` is preserved and
still runs from the Streamlit cockpit (`load_cockpit_state()`) and explicit
pipeline audits. Only the polled read endpoint stopped triggering it, so UI polling
can no longer create duplicate audit rows. No forensic evidence removed.
