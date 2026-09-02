# TradeLogger — Technical Debt

*Recorded during the stabilization pass. Priorities: P0 critical · P1 important ·
P2 improvement · P3 nice-to-have. Nothing here is a safety-invariant risk.*

---

## P1 — Important

### P1-1 · No database connection pooling
- **Location:** `database.py :: get_connection()`
- **Impact:** with the cloud Postgres backend, every call opens a fresh
  `psycopg2.connect()` — **~340 ms** measured. Every uncached endpoint pays it
  once; cold page loads pay it several times. This is the dominant cause of the
  "feels slow when navigating" report. Warm latencies are fine because the
  routers cache, but *first* visit to each area stalls.
- **Recommended solution:** a `psycopg2.pool.ThreadedConnectionPool` (or
  SQLAlchemy engine with `pool_pre_ping`) created once at process start, handed
  out via a context manager; SQLite path unchanged. Requires a thread-safety
  review of the ~40 `get_connection()` call sites and the reconciliation worker.
- **Why deferred:** touches the shared persistence layer used by every engine
  and the sync daemons — needs its own focused change + full regression, not a
  cleanup-pass edit. The stabilization pass added short-TTL caches to the worst
  read paths instead (`price_alerts` 8 s).

### P1-2 · `/api/operations/audit` uncached — warm p50 ≈ 1.3 s
- **Location:** `api/routers/operations.py :: get_audit`
- **Impact:** every call runs `SELECT COUNT(*)` + 2 `GROUP BY` + a 200-row
  `SELECT` on `execution_orders` (335 rows) over Postgres, **plus**
  `_decision_ledger_count()` → `ResearchDecisionAuditEngine.get_audit_history(limit=1000)`.
  No cache. Slowest endpoint in the app.
- **Recommended solution:** a bounded-TTL snapshot cache (Stage 3.5-style, e.g.
  15–30 s) keyed by `limit`; skip `_decision_ledger_count` unless requested.
- **Why deferred:** explicitly parked at Stage 11 for the performance phase.

### P1-3 · `/api/operations/system` uncached — warm p50 ≈ 0.7 s
- **Location:** `api/routers/operations.py :: get_system` → `system_health.evaluate_system_health`
- **Impact:** re-runs the full PAPER-mode diagnostic gate (kill-switch, DB
  connectivity, reconciliation worker heartbeat, unresolved-order scan) on every
  request. Also the largest single contributor to `/api/command-center/overview`
  (~0.7 s) because `_safety()` calls it.
- **Recommended solution:** short-TTL cache (10 s) on `evaluate_system_health`
  output, or expose a lighter "flags-only" fast path for the command centre.
- **Why deferred:** same as P1-2.

### P1-4 · Cold-load cache miss + connection cost stacks
- **Location:** `/api/watchlist` (cold 814 ms), `/api/positions` (411 ms),
  `/api/analytics/performance` (369 ms)
- **Impact:** first visit to a Workspace page is noticeably slow; warm is <5 ms.
- **Recommended solution:** subsumed by P1-1 (pooling removes most of it). A
  cheap partial mitigation: a startup warm-up task that primes the hot read
  caches after the app boots.
- **Why deferred:** depends on P1-1.

---

## P2 — Improvement

### P2-1 · Frontend bundle is one 510 kB chunk
- **Location:** `frontend/` Vite build (chunk-size warning).
- **Impact:** whole SPA JS downloaded up front (~137 kB gzip). Acceptable today,
  grows with each feature.
- **Recommended solution:** route-level `React.lazy` + `manualChunks` for the
  heavy areas (research, macro, evidence).
- **Why deferred:** not a correctness or perceived-latency problem yet;
  unrelated to this pass's scope.

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

### P3-3 · `PlaceholderPage` / `ZoneOverviewPage` are dead-ish
- **Location:** `frontend/src/pages/`
- **Impact:** `PlaceholderPage` is referenced as a fallback but every nav item
  is now live, so it never renders. Harmless.
- **Recommended solution:** keep as the fallback contract; no action.

---

## Resolved during this stabilization pass

| Was | Fix |
| :-- | :-- |
| `api/routers/positions.py:34` — `float(pos.get("tp", 0.0))` crashed on a NULL `tp` (only surfaced under randomized test ordering) | null-safe `_f()` helper for all position numeric fields |
| `/api/alerts` warm p50 ≈ 372 ms (fresh Postgres connection every call) | `get_all_price_alerts(ttl_sec=8.0)` + cache invalidation on create/delete/trigger → warm p50 ≈ 3 ms |
| 2 unused imports introduced in Stages 15/18 (`ai_context.List`, `macro_service._CCY_BY_COUNTRY`) | removed |
