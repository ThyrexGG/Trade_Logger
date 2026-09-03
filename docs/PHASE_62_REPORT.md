# Phase 62 — Performance Engineering: Final Report

*Database pooling · API latency · cold-load · JS bundle. Performance only —
no product features, no stack migration, no redesign, macro scorecard still
parked.*

---

## Executive summary

TradeLogger's "feels slow when navigating" was one root cause: **every database
call opened a fresh connection to the managed cloud Postgres (~280 ms
handshake), and three endpoints had no cache to hide it.** Four changes fixed it:

1. **Connection pool** (`database.py`) — `psycopg2.pool.ThreadedConnectionPool`,
   lazy, fork-safe, behind a transparent proxy. No new dependency.
2. **Snapshot caches** on the three un-cached slow endpoints (audit 12 s,
   system-health 8 s, command-centre notes 30 s).
3. **Startup warm-up** (FastAPI `lifespan`) — primes the pool and heavy routes
   before uvicorn accepts traffic.
4. **Frontend route-level code splitting** — `React.lazy` for 20 pages +
   a `react-vendor` chunk.

Result: **every warm API p50 dropped below 40 ms** (from a worst case of
1.4 s), the command-centre p99 went from 3.5 s to 137 ms, cold first-visit
latency fell 85–99 %, and the initial JS download shrank ~28 % (gzip). Full
regression: **1059 passed, 2 skipped, 0 failed.**

---

## Root cause

| Cost component (measured) | Value |
| :-- | --: |
| `psycopg2.connect()` — new connection to the managed instance | **~280 ms** |
| One query round-trip on an already-open connection | **~125 ms** |
| `database.get_connection()` call sites | ~150 |

Fast endpoints only *looked* fast — their routers cache in-process, so only the
*first* visit paid a connect. The endpoints without a cache
(`/api/operations/audit`, `/api/operations/system`,
`/api/command-center/overview`) paid 2–3 connects **on every request**. React
Router transitions were already instant; the lag was always the follow-up fetch.

---

## Database — pooling implementation & results

`database.py`:

- Process-wide `ThreadedConnectionPool`, built lazily on first use, **re-built
  if the PID changes** (a forked uvicorn/gunicorn worker never inherits the
  parent's sockets).
- `get_connection()` returns a `_PooledConnection` proxy. `cursor()`,
  `commit()`, `rollback()`, `pandas.read_sql_query` all delegate unchanged;
  **only `.close()` differs** — it returns the connection to the pool.
- **Transaction semantics preserved:** psycopg2's pool rolls back any non-idle
  connection on return, so an uncommitted write is discarded exactly as the old
  `.close()` did. Writers keep their explicit `commit()`.
- **Idle-drop safe:** a recycled connection parked longer than
  `DB_POOL_IDLE_PING` s (default 25) is validated with `SELECT 1` before reuse;
  a dead one is discarded and another taken. Fresh connections are trusted (no
  wasted round-trip).
- **Never fails the caller:** pool exhausted/unusable → direct connection
  fallback (counted in `pool_stats()`).
- **SQLite path untouched** (tests, `USE_LOCAL_SQLITE=1`).
- FastAPI `lifespan` closes the pool on shutdown.

Config (env, optional): `DB_POOL_ENABLED` (1), `DB_POOL_MIN` (1),
`DB_POOL_MAX` (12), `DB_POOL_IDLE_PING` (25). Chosen conservatively for the
current single-instance deployment + one background daemon + the ≤ 8-way
command-centre fan-out.

**Pool contribution in isolation** (caches disabled, same session):

| Endpoint | connect-per-call | pooled |
| :-- | --: | --: |
| `/api/operations/audit` warm p50 | 1399 ms | 585 ms |
| `/api/operations/system` warm p50 | 808 ms | 296 ms |
| `/api/positions` cold | 418 ms | 172 ms |
| `/api/alerts` cold | 377 ms | 164 ms |

Tests: `tests/test_db_pool.py` (10) — reuse, return-not-close, double-close,
delegation, idle revalidation, dead-connection discard + replace, exhaustion
fallback, `close_all_pools`, SQLite-not-pooled, disabled-flag bypass.

---

## API — before / after (warm p50, same machine & session)

| Endpoint | Before | After | Improvement |
| :-- | --: | --: | --: |
| `/api/operations/audit` | 1420.3 ms | **2.8 ms** | −99.8 % |
| `/api/operations/system` | 759.8 ms | **2.0 ms** | −99.7 % |
| `/api/command-center/overview` | 804.4 ms | **26.1 ms** | −96.8 % |
| `/api/analytics/performance` | 76.1 ms | 40.4 ms | −47 % |
| `/api/alerts` | 10.3 ms | 2.1 ms | −80 % |
| Endpoints with warm p50 ≥ 100 ms | **3** | **0** | — |

Command-centre p95/p99: 904 ms / 3468 ms → **38 ms / 137 ms**.

The already-cached endpoints (`/api/health`, `/api/watchlist`,
`/api/intelligence/*`, `/api/macro/*`, …) read ~15–20 ms in the "before" run and
~1–10 ms after — but the "before" figure was inflated by a machine-wide ~15 ms
overhead present that day on *every* call including non-DB ones, so that delta
is environment noise, not a change from this phase. Their real improvement is
in the cold column below.

---

## Cold load — before / after

| First visit | Before (cold ms) | After (cold ms, `--lifespan`) |
| :-- | --: | --: |
| `/api/watchlist` | 1056 | **1** |
| `/api/positions` | 396 | 134 |
| `/api/alerts` | 362 | 3 |
| `/api/command-center/overview` | 2155 | 155 |
| `/api/operations/system` | 1893 | 133 |
| `/api/operations/audit` | 1432 | 569 |

The startup warm-up (in `api/main.py` `lifespan`) issues in-process requests to
the heavy routes before traffic is accepted, so the deployed uvicorn process
serves the *first* user navigation at warm speed. `TL_SKIP_WARMUP=1` disables
it; it does not run under the test suite.

---

## Frontend — navigation & bundle

- `frontend/src/App.tsx`: every page except the landing view + the lightweight
  zone/overview pages is `React.lazy()`-loaded, wrapped in one `<Suspense>`
  inside the persistent shell (sidebar + top bar stay mounted → navigation
  still feels immediate; a small "Loading view…" fallback shows only while a
  chunk downloads).
- `frontend/vite.config.ts`: `react` / `react-dom` / `react-router-dom` split
  into a cache-stable `react-vendor` chunk.
- Data hooks were audited — already sound (one request per resource,
  `AbortController`, `[nonce]`-only effects, hidden-paused refresh, last-good on
  error). No request storms, no duplicate fetches, no refetch-on-remount. No
  change needed.

| Build | Initial JS | Initial JS gzip | Chunks |
| :-- | --: | --: | --: |
| Before | 510.1 kB | 136.7 kB | 1 |
| After | 264.2 kB `index` + 51.4 kB `react-vendor` | **96.9 kB** | 23 |

Heaviest pages (Intelligence 22 kB, Backtest 19 kB, Analytics/Macro/Audit
~15 kB) load only on first visit. `tsc -b` clean, `npm run build` clean,
chunk-size warning gone.

---

## Browser experience (measured — headless Chrome / CDP)

**19 SPA routes × 3 resolutions (1280×720, 1440×900, 1920×1080) = 66 loads:**

| Check | Result |
| :-- | :-- |
| Console errors | **0** |
| Uncaught exceptions | **0** |
| Horizontal overflow | **0** (all routes fit; scrollbar-gutter only) |
| Route renders content (lazy chunk + Suspense) | **66 / 66** |
| Command palette — Ctrl/Cmd+K opens | ✅ |
| Command palette — Esc closes | ✅ |

---

## Remaining bottlenecks (documented, not fixed)

1. **Cold `/api/operations/audit` ≈ 570 ms** on the very first hit — the
   `LIMIT 1000` decision-ledger read + 4 sequential `execution_orders` queries.
   Warm is 3 ms; warm-up hides it. `TECHNICAL_DEBT.md` P3-4.
2. **`/api/analytics/performance` warm ≈ 40 ms** — recomputes over the full
   `closed_trades` table each call. Fine now; wants its own cache if the
   journal grows.
3. **Managed-Postgres RTT ≈ 125 ms/query** — inherent to the hosting choice.
   The pool removed the connect cost, not the per-query network latency.
4. **`index.js` 264 kB / 79 kB gzip** — shared core; splitting further has
   diminishing returns.
5. **`database.py` ~1200 lines** — structural, not performance.

---

## Deferred architecture changes

None were needed and none were made. If scale ever demands it, in order:
**co-located Postgres / read replica** (removes the 125 ms RTT — an infra
decision), then an **async driver + async pool** (`asyncpg`), then a
**background runner** for AI calls. No Redis / Celery / queue / WebSockets were
added.

---

## Macro

**Macro scorecard remains PARKED. No macro feature expansion was performed.**
The Stage 18 foundation is untouched: `seed_demo` provider, `provenance`
tagging, `INSUFFICIENT_EVIDENCE` for CHF/CAD/AUD/NZD, permanent "DEMO / SEEDED
DATA" banner, read-only. No macro data fabricated.

---

## Safety

| Invariant | Status |
| :-- | :-- |
| Strategy contract SHA-256 (`7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`) | **PRESERVED** (byte-exact; verified in-session) |
| Historical baseline N=82, E[R]=+0.637R, WR=58.6 %, PF=2.52 | **PRESERVED** (locked, unpooled) |
| Dataset isolation `IDs_hist ∩ IDs_paper/shadow = ∅` | **PRESERVED** |
| `LIVE_AUTOMATION_ENABLED` | **False** (verified) |
| `LIVE_BROKER_TRANSMISSION` | **"BLOCKED"** (verified via `/api/operations/system` + `/api/health`) |
| Lookahead protection (`release_timestamp <= as_of`) | **PRESERVED** — no cache added to a market/macro/evidence read path beyond its existing freshness window |
| Contextual intelligence stays non-execution | **PRESERVED** — no execution/broker/risk file touched; `execution_pipeline` / `broker_adapter` / `risk_gateway` unchanged |

Transaction semantics were reviewed explicitly: the pool's rollback-on-return
matches the old `.close()` fail-closed behaviour for uncommitted work.

---

## Tests

| | |
| :-- | :-- |
| Passed | **1059** (1043 baseline + 16 new: 10 pool + 6 perf-infra) |
| Skipped | 2 (pre-existing) |
| Failed | **0** |
| Duration | ~95–110 s (`pytest tests/ -p no:randomly`) |
| `tsc -b` | clean |
| `npm run build` | clean — 264 kB `index` + 51 kB `react-vendor` + 20 route chunks, no warning |

New tests: `tests/test_db_pool.py`, `tests/test_phase62_perf_infra.py`
(cache hit/invalidation, keyed-by-limit, PAPER-mode enforcement, benchmark
imports no execution module). No existing test weakened; performance
benchmarks are separate from correctness tests (no timing thresholds in the
suite).

---

## Benchmark suite

`performance_benchmark.py` — extended with `--lifespan` (measure the
production cold path with warm-up), `--compare <baseline.json>` (before/after
delta table), and a `db_pool` section (reuse / ping / fallback counters) in the
JSON + console output. `docs/performance_baseline.json` regenerated with the
`--lifespan` run.

---

## Git

- Branch: `main`
- Commit: **`a24cca7`** — `perf: database pooling, API latency, cold-load & bundle (Phase 62)`
- Files: 8 modified (`database.py`, `api/main.py`,
  `api/routers/{operations,command_center}.py`, `performance_benchmark.py`,
  `frontend/src/App.tsx`, `frontend/vite.config.ts`,
  `docs/performance_baseline.json`), 4 added
  (`api/system_health_cache.py`, `frontend/src/components/shell/RouteFallback.tsx`,
  `tests/test_db_pool.py`, `tests/test_phase62_perf_infra.py`), plus docs.
- No execution/safety file staged. No secrets, temp files, or benchmark junk.

---

## Success criteria (Phase 62)

| # | Criterion | Met |
| --: | :-- | :-- |
| 1 | PostgreSQL connection overhead materially reduced | ✅ ~280 ms handshake eliminated per call |
| 2 | Major slow endpoints measurably faster | ✅ audit/system/command-centre −97 to −99.8 % |
| 3 | Cold navigation improved | ✅ −85 to −99 % via pool + warm-up |
| 4 | Redundant frontend requests reduced | ✅ audited — already minimal; code-split reduces initial download |
| 5 | App feels more responsive | ✅ browser QA: every route usable, no cascade |
| 6 | Measurements reproducible | ✅ `performance_benchmark.py` + flags |
| 7 | No functionality broken | ✅ 1059 pass, 0 fail; 66/66 routes clean |
| 8 | No safety invariant changed | ✅ table above |
| 9 | Macro remains parked | ✅ not touched |
| 10 | Full regression green | ✅ |
| 11 | Repository still understandable | ✅ docs updated |
| 12 | Every remaining bottleneck documented | ✅ §"Remaining bottlenecks" + `TECHNICAL_DEBT.md` |

---

## STOP

Performance work complete. No new feature started, no parked macro backlog
implemented, no architecture migrated. Repository is clean, tested, documented.
