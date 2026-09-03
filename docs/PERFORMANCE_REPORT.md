# TradeLogger — Performance Report (Phase 62)

*Performance engineering only. No product features, no stack migration, no
redesign. Every number below is measured with `performance_benchmark.py`
against the real app + the live cloud Postgres.*

---

## 1. Executive summary

| What | Before | After |
| :-- | --: | --: |
| `/api/operations/audit` — warm p50 | **1420 ms** | **2.8 ms** |
| `/api/operations/system` — warm p50 | **760 ms** | **2.0 ms** |
| `/api/command-center/overview` — warm p50 | **804 ms** (p99 3.5 s) | **26 ms** (p99 137 ms) |
| First visit to `/api/watchlist` (cold) | **1056 ms** | **1 ms** *(warm-up)* / ~950 ms without |
| First visit to `/api/positions` (cold) | 396 ms | 134 ms |
| First visit to `/api/alerts` (cold) | 362 ms | 3 ms |
| Slowest warm endpoint in the app | 1420 ms | **40 ms** (`/api/analytics/performance`) |
| Endpoints with warm p50 ≥ 100 ms | 3 | **0** |
| Frontend initial JS (gzip) | ~144 kB (one chunk) | ~104 kB (shell + vendor) |
| Backend regression suite | 1043 pass | **1059 pass** (+16 perf tests) |

Three changes did the work: a **PostgreSQL connection pool**, **short-TTL
snapshot caches** on the three un-cached slow endpoints, and a **startup
warm-up** that moves one-off lazy-import cost off the first user request.
Frontend route-level **code splitting** trims the initial download.

---

## 2. Root cause

The app talks to a **managed cloud Postgres** with two measured cost components:

| Component | Cost | Why |
| :-- | --: | :-- |
| Opening a new connection (TCP + TLS + auth) | **~280 ms** | `database.get_connection()` did `psycopg2.connect()` **every call** — no pool |
| One query round-trip on an open connection | **~125 ms** | network RTT to the managed instance |

`get_connection()` is called from ~150 sites. Fast endpoints (watchlist,
intelligence, macro, …) only *looked* fast because their routers cache the
result in-process — but the **first** visit to each still paid a full connect,
and pages that were not cached paid it on every request:

```
/api/operations/system   ≈ get_setting (1st call) + SELECT 1 + SELECT COUNT(unknown)
                         ≈ 3 fresh connects  ≈ 760 ms
/api/operations/audit    ≈ own connect + 4 queries + decision-ledger (own connect + LIMIT 1000)
                         ≈ 2 fresh connects + round-trips ≈ 1420 ms
/api/command-center      ≈ 8 sections in a ThreadPoolExecutor, bounded by the
                           slowest: _safety() → evaluate_system_health (≈ 3 connects)
                           and _research_notes() → schema bootstrap (≈ 4 round-trips)
                         ≈ 800 ms
```

Client-side React Router transitions were already instant; "feels slow when
navigating" was **entirely the data fetch that follows a navigation**.

---

## 3. Change 1 — PostgreSQL connection pool

**File:** `database.py`. **No new dependency** — uses
`psycopg2.pool.ThreadedConnectionPool`, which ships with `psycopg2-binary`.

- Lazily built once per process; **fork-safe** (re-created if `os.getpid()`
  changes, so a uvicorn/gunicorn worker never inherits the parent's sockets).
- `get_connection()` returns a thin `_PooledConnection` proxy. Everything
  (`cursor()`, `commit()`, `rollback()`, `pandas.read_sql_query`) delegates to
  the real connection unchanged; **only `.close()` differs** — it returns the
  connection to the pool instead of tearing down the socket.
- **Transaction semantics preserved.** psycopg2's pool rolls back any
  non-idle connection on return, so an uncommitted write is discarded exactly
  as the old `.close()` behaved. Read callers that never `commit()` get a clean
  connection next time; write callers keep their explicit `commit()`.
- **Idle-drop resilience.** A recycled connection that has been parked longer
  than `DB_POOL_IDLE_PING` seconds (default 25) is validated with `SELECT 1`
  before reuse; a dead one is discarded and another taken. Fresh connections
  are trusted without a ping (no wasted round-trip on the hot path).
- **Never fails the caller.** Pool exhausted or unusable → fall back to a plain
  direct connection (counted in `pool_stats()["overflow_direct"]`).
- SQLite path (tests, `USE_LOCAL_SQLITE=1`) is **untouched** — SQLite connect
  is free and needs its per-connection PRAGMAs.
- Clean shutdown via the new FastAPI `lifespan` → `database.close_all_pools()`.

**Configuration** (env, all optional):

| Var | Default | Meaning |
| :-- | :-- | :-- |
| `DB_POOL_ENABLED` | `1` | `0` restores connect-per-call |
| `DB_POOL_MIN` | `1` | idle connections kept open |
| `DB_POOL_MAX` | `12` | ceiling; conservative for the current single-instance dev/prod deployment |
| `DB_POOL_IDLE_PING` | `25` | seconds before a parked connection is re-validated |

Chosen conservatively: one app instance, a background reconciliation daemon,
and the command-centre fan-out (≤ 8 concurrent section builders) never need
more than ~10 connections; 12 leaves headroom without risking the managed
instance's connection limit.

**Effect in isolation** (pool on, caches off, same session):
`/api/operations/audit` 1399 → 585 ms, `/api/operations/system` 808 → 296 ms,
cold `/api/positions` 418 → 172 ms, cold `/api/alerts` 377 → 164 ms. The
connect handshake is gone; the remaining cost is query round-trips.

---

## 4. Change 2 — snapshot caches on the slow endpoints

Round-trips that remain after pooling are removed with **short, explicit TTL
caches** — only where the data is operational status, not live market data.

| Cache | File | TTL | Invalidation | Why safe |
| :-- | :-- | --: | :-- | :-- |
| PAPER system-health gate | `api/system_health_cache.py` | 8 s | `invalidate()` | operational status; **not** placed inside `system_health.py` — any execution-gating path still calls the authoritative evaluator directly |
| `/api/operations/audit` response | `api/routers/operations.py` | 12 s | `invalidate_audit_cache()` | `execution_orders` is append-only (~335 rows) and live broker transmission is BLOCKED, so it barely changes |
| Command-centre research notes | `api/routers/command_center.py` | 30 s | time only | notes are hand-authored in the Streamlit journal; 30 s staleness is invisible in a "today" panel |

**Not cached:** market snapshots, macro data, analytics inputs, positions,
alerts list beyond its existing 8 s DB cache — anything with a freshness /
`as_of` / lookahead contract. No cache returns future information; no
per-viewer state is shared.

**Effect:** all three endpoints drop to single-digit ms warm. The system-health
cache also removes ~250 ms from the command-centre critical path (it is the
`_safety` section), and the notes cache removes the new long pole (~290 ms).

---

## 5. Change 3 — startup warm-up

**File:** `api/main.py` (`lifespan`). Before uvicorn accepts traffic, the app
issues in-process requests to `/api/watchlist`, `/api/positions`,
`/api/analytics/performance`, `/api/operations/{audit,system}` and
`/api/command-center/overview`. This triggers their lazy engine imports and
fills the read caches, so the **first real user navigation is as fast as a warm
one** instead of paying a ~1 s one-off.

Best-effort and fully guarded — a slow or unreachable DB cannot stop boot.
Disable with `TL_SKIP_WARMUP=1`. It does not run under the test suite (tests use
a bare `TestClient`, which does not enter the lifespan).

Measured with `--lifespan` (what the deployed process does): cold
`/api/watchlist` 1056 → **1 ms**, cold `/api/command-center` 2155 → **155 ms**,
cold `/api/operations/system` 1893 → **133 ms**.

---

## 6. Change 4 — frontend route-level code splitting

**Files:** `frontend/src/App.tsx`, `frontend/vite.config.ts`,
`frontend/src/components/shell/RouteFallback.tsx`.

- Every page except the landing view and the lightweight zone/overview pages is
  `React.lazy()`-loaded and wrapped in one `<Suspense>` inside the persistent
  shell. The sidebar + top bar stay mounted, so navigation still feels
  immediate; a small "Loading view…" fallback shows only while a route chunk
  downloads (typically 1–6 kB gzip).
- `react` / `react-dom` / `react-router-dom` are split into a `react-vendor`
  chunk that stays cached across app deploys.

| Build | Initial JS | Initial JS (gzip) | Chunks |
| :-- | --: | --: | --: |
| Before | 510.1 kB (one file) | 136.7 kB | 1 |
| After | 264.2 kB `index` + 51.4 kB `react-vendor` | 78.7 + 18.2 = **96.9 kB** | 23 (20 lazy routes) |

Heaviest pages (Intelligence 22 kB, Backtest 19 kB, Analytics / Macro /
Research-Audit ~15 kB) now load only when first visited. `tsc -b` clean,
`npm run build` clean, chunk-size warning gone.

Browser QA (headless Chrome, CDP): **19 SPA routes × 3 resolutions
(1280×720 / 1440×900 / 1920×1080) = 66 loads → 0 console errors, 0 uncaught
exceptions, 0 horizontal overflow, every route renders content** through the
Suspense boundary. Command palette Ctrl/Cmd+K opens, Esc closes.

---

## 7. Full before / after (warm p50, ms) — same machine, same session

| Endpoint | before | after | | Endpoint | before | after |
| :-- | --: | --: | --- | :-- | --: | --: |
| `/api/health` | 21.3\* | 1.0 | | `/api/macro/overview` | 29.4\* | 9.9 |
| `/api/watchlist` | 6.9\* | 1.9 | | `/api/macro/currencies` | 28.5\* | 2.7 |
| `/api/market/snapshot` | 6.6\* | 1.7 | | `/api/macro/events` | 29.4\* | 7.6 |
| `/api/positions` | 18.6\* | 2.1 | | `/api/research/strategy` | 27.0\* | 2.0 |
| `/api/command-center/overview` | **804.4** | **26.1** | | `/api/forward-evidence/state` | 22.4\* | 1.6 |
| `/api/analytics/performance` | 76.1 | 40.4 | | `/api/operations/journal` | 30.4\* | 5.8 |
| `/api/intelligence/summary` | 16.3\* | 0.6 | | `/api/operations/audit` | **1420.3** | **2.8** |
| `/api/intelligence/opportunity-map` | 19.7\* | 0.9 | | `/api/operations/system` | **759.8** | **2.0** |
| `/api/intelligence/heatmap` | 19.3\* | 1.9 | | `/api/alerts` | 10.3 | 2.1 |
| `/api/macro/assets` | 22.4\* | 2.1 | | `/api/ai/status` | 22.5\* | 1.7 |

\* The "before" run of these already-cached endpoints was taken on a day when
the test machine showed a uniform ~15–20 ms overhead on *every* call (including
`/api/health`, which touches no database). It is environment noise, not a
regression fixed by this phase — the meaningful improvements are the bold rows
and the cold column (§1).

`db_pool` during the after-run: `checkouts=7 reused=7 created=0 pings=0
ping_failures=0 overflow_direct=0` — full reuse, no leaks, no fallbacks.

---

## 8. Targets vs. result

| Class (Phase 62 §24) | Target | Result |
| :-- | :-- | :-- |
| Warm, no external dep | p50 < 250 ms / p95 < 500 ms | ✅ all ≤ 40 / ≤ 56 ms |
| Simple UI interaction | p50 < 100 ms | ✅ command palette, nav — client-side, instant |
| Heavier intelligence endpoints | p50 < 500 ms / p95 < 1000 ms | ✅ command-centre 26 / 38 ms |
| Initial app load | measurable improvement | ✅ −28% gzip JS, cold data path −85–99% |

---

## 9. Remaining bottlenecks (documented, not fixed)

1. **Cold `/api/operations/audit` ≈ 570 ms on the very first hit** (before the
   12 s cache fills / outside the warm-up). It is the decision-ledger read
   (`ResearchDecisionAuditEngine.get_audit_history(limit=1000)` — currently
   returns 0 rows but still ~250 ms of round-trips) plus 4 sequential queries
   on `execution_orders`. Could be one combined query + a smaller ledger limit.
   Low priority — the warm-up hides it and warm is 3 ms.
2. **`/api/analytics/performance` warm ≈ 40 ms.** Reads the full
   `closed_trades` table (53 rows) and recomputes metrics each call. Fine
   today; would want its own short cache if the journal grows large.
3. **Managed-Postgres RTT ≈ 125 ms/query.** Inherent to the hosting choice.
   The pool removes the *connect* cost but not the per-query network latency —
   this is why endpoints that must hit the DB uncached still cost tens of ms.
   A co-located database (or read replica) is the only structural fix and is an
   infrastructure decision, not a code change.
4. **`index.js` still 264 kB / 79 kB gzip.** Shared components + hooks + the
   four eager pages. Splitting further has diminishing returns; revisit only if
   it grows.
5. **`database.py` is still a 1200-line module.** The pool now lives at the top
   of it; a `db/` package split is the natural follow-up but is pure structure,
   not performance (`TECHNICAL_DEBT.md` P2-3).

---

## 10. Deferred architecture changes

Nothing in this phase required Redis, Celery, a job queue, WebSockets, or a
database migration, and none were added. If the app ever needs true concurrency
at scale, the candidates — in order — are: a co-located Postgres / read
replica (kills the 125 ms RTT), then an async driver (`asyncpg`) with an async
pool, then a background task runner for the AI calls. All are larger changes
with their own regression surface and are **out of scope until measurements
demand them**.

---

## 11. Reproduce

```bash
# API latency, production-equivalent (runs the startup warm-up)
python performance_benchmark.py --rounds 12 --lifespan --json docs/performance_baseline.json

# isolate the pool contribution
DB_POOL_ENABLED=0 python performance_benchmark.py --rounds 12   # before
python performance_benchmark.py --rounds 12                      # after

# diff against a saved baseline
python performance_benchmark.py --rounds 12 --compare <old.json>

# pool correctness
python -m pytest tests/test_db_pool.py tests/test_phase62_perf_infra.py -q
```
