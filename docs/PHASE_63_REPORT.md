# Phase 63 — Production Performance Verification & Next-Bottleneck Discovery

*Verification phase. No feature work, no infrastructure changes, no arbitrary
optimization. All numbers measured this session against the real app + the live
managed Postgres.*

---

## Executive summary

Phase 62's improvements are **real, stable, and reproducible**. Re-measured
today they match the Phase 62 report (differences are machine noise, not
regression). The connection pool provides essentially perfect reuse; the
snapshot caches are correct, not just fast; the code-split bundle loads and
renders on every route.

**No application-level P1 bottleneck was found.** The remaining ~85–125 ms cost
on an uncached database query is the managed-Postgres network RTT —
infrastructure, not application code, and it only bites on a cache miss (warm
navigation makes **zero** database round-trips). One P2 was identified: the
command-centre overview fans out to ~8 concurrent pool checkouts per *cold*
request, which would pressure the pool under heavy concurrent load; it does not
affect the current single-instance deployment and needs a proper uvicorn load
test to size, not a TestClient one.

**Code changes made: NONE.** A candidate change (making the command-centre
sequential) was implemented, measured, and reverted — it was not a clear
improvement and the concurrency question needs a real load test first.

---

## Repository state

```
git working tree : clean (only untracked docs/reference/*.jpg — EdgeFinder
                   screenshots the user added for the PARKED macro backlog)
Phase 62 commits : a24cca7 (perf) + 47e6c7f (report) present
pytest           : 1059 passed, 2 skipped, 0 failed  (~69–110 s)
tsc -b           : clean
npm run build    : clean — index 264.21 kB + react-vendor 51.42 kB, no warning
contract SHA-256 : 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76 — unchanged
```

---

## Three latency states

Measured with `performance_benchmark.py` (in-process TestClient — excludes the
user's network to the app, includes DB round-trip + compute + cache).

### A. Process Cold — brand-new process, no pool, no cache, no warm-up
`TL_SKIP_WARMUP=1`. The **first DB-touching endpoint** pays the whole one-off
cost: build the pool (`psycopg2.pool` import + open `DB_POOL_MIN` connection)
+ the route's lazy engine imports + the first query.

| First request of the process | cold ms |
| :-- | --: |
| `/api/watchlist` (first DB endpoint hit) | **652** (pool build + imports + query) |
| direct `get_connection()` first call, isolated | **956** |
| `/api/command-center/overview` as the first hit | ~2470 (import-heavy engine chain) |

Every *subsequent* endpoint's "first hit" is much cheaper because the pool is
already up — e.g. `/api/operations/system` 131 ms, `/api/positions` 148 ms,
`/api/alerts` 6 ms (its list is tiny).

### B. Startup-Warmed — FastAPI lifespan ran the warm-up, then first user request
`--lifespan`.

| First user request | cold ms |
| :-- | --: |
| `/api/watchlist` | **1** |
| `/api/operations/audit` | 2 |
| `/api/operations/system` | 2 |
| `/api/alerts` | 2 |
| `/api/analytics/performance` | 28 |
| `/api/command-center/overview` | 145 |
| `/api/positions` | 130 |

The two >100 ms (`command-center`, `positions`) each make ~1 live DB
round-trip whose short cache (2 s) can lapse between warm-up and the request —
i.e. ~1× the Postgres RTT, not application overhead.

### C. Warm — steady state, endpoint already served

| Endpoint | warm p50 | p95 | p99 |
| :-- | --: | --: | --: |
| `/api/health`, `/api/watchlist`, `/api/market/snapshot`, `/api/intelligence/*`, `/api/research/strategy`, `/api/forward-evidence/state`, `/api/ai/status` | 0.7 – 2.0 ms | ≤ 4 ms | ≤ 5 ms |
| `/api/alerts`, `/api/operations/audit`, `/api/operations/system`, `/api/macro/currencies`, `/api/macro/assets` | 1.5 – 2.4 ms | ≤ 4 ms | ≤ 6 ms |
| `/api/macro/events`, `/api/macro/overview`, `/api/operations/journal` | 6 – 10 ms | ≤ 12 ms | ≤ 13 ms |
| `/api/command-center/overview` | **15.5 ms** | 17.5 | 18.9 |
| `/api/analytics/performance` | **34.5 ms** | 48 | 48 |

**All warm p50 < 100 ms. All warm p95 < 250 ms.** No endpoint in the "slow"
list. Matches Phase 62 (audit 2.8→2.0, system 2.0→1.7, command-centre 26→15.5 —
lower today, machine noise).

---

## Database — pool verification

| Measurement | Value |
| :-- | --: |
| 1st connection acquisition (builds the pool) | **956 ms** (one-off per process) |
| 2nd acquisition | **0.24 ms** |
| steady-state acquisition (median of 30) | **0.036 ms** (max 0.09 ms) |
| query round-trip `SELECT 1` on a checked-out connection | **84.5 ms** median (min 83.4, p95 85.8) |
| 52 checkouts → | 51 reused · 1 created · **0 overflow_direct** · 0 pings · 0 ping_failures |

The application **no longer pays the ~406 ms connect-per-call** measured
pre-Phase-62 — checkout is now 0.036 ms. The ~85 ms that remains on a real query
is the network RTT to the managed instance, unchanged by pooling.

**Warm DB-checkout audit** — one warm request to each navigation endpoint:

```
/api/health .............. 0      /api/operations/audit .... 0
/api/watchlist ........... 0      /api/operations/system ... 0
/api/market/snapshot ..... 0      /api/command-center ...... 0
/api/intelligence/summary  0      /api/positions ........... 0
/api/macro/overview ...... 0      /api/alerts .............. 0
/api/analytics/performance 0
```

**In warm steady state every navigation endpoint makes zero database
round-trips** — reads are fully absorbed by the in-process caches. The pool
only matters for: cold start, cache-expiry rebuilds, and writes (alert CRUD,
journal PATCH).

---

## Pool stress test

`ThreadPoolExecutor` driving an in-process `TestClient` at concurrency 2 / 5 /
10 / 20, `conc × 3` requests each. **Caveat: `TestClient` + Python threads is
not a faithful load generator** (GIL, sync transport, portal) — read these
**directionally**, not as production numbers.

| Concurrency | `/api/positions` p50 / errors | `/api/command-center/overview` p50 / errors |
| --: | :-- | :-- |
| 2 | 2.9 ms / 0 | 39 ms / 0 |
| 5 | 6.4 ms / 0 | 101 ms / 0 |
| 10 | 13.2 ms / 0 | 203 ms / 0 |
| 20 | 24.2 ms / 0 | **5160 ms** / 0 (pool overflow → slow direct connects) |

- **`/api/positions` scales cleanly** — linear, 0 errors, 1 checkout per request.
- **`/api/command-center/overview` degrades non-linearly past ~pool size**
  because it runs its 8 sections in a `ThreadPoolExecutor`, so **one cold
  overview request checks out up to ~8 pooled connections at once**. At
  concurrency 20 that is ~160 simultaneous checkout attempts against a pool of
  12 → `overflow_direct` fires repeatedly, each paying a full ~400 ms connect.
- **No errors, no exhaustion failures, no leaks, no ping failures** at any
  level — the overflow-to-direct fallback keeps every request succeeding, just
  slowly.

---

## Cache verification (correctness, not just speed)

| Cache | first → second | after `invalidate()` | keyed correctly | content stable across hits |
| :-- | :-- | :-- | :-- | :-- |
| `/api/operations/audit` (12 s) | uncached → cached (same `timestamp`) | fresh `timestamp` | ✅ by `limit` (5 vs 99) | ✅ identical `state_counts` / `total_records` |
| PAPER system-health (8 s) | uncached → cached | fresh | n/a (single key) | ✅ `safety_gate` identical; fail-closed values preserved (`live_automation_enabled=False`, `BLOCKED`) |
| command-centre notes (30 s) | uncached → cached | (time only) | n/a | ✅ |

### Staleness audit — could any response mislead during its TTL?

| Cache | TTL | Worst-case staleness | Verdict |
| :-- | --: | :-- | :-- |
| audit response | 12 s | an `execution_orders` state change invisible for ≤ 12 s | Safe — table is append-only and `LIVE_BROKER_TRANSMISSION="BLOCKED"`; `invalidate_audit_cache()` exists for any writer |
| PAPER system-health | 8 s | kill-switch flip invisible in the *status view* for ≤ 8 s | Safe — real execution gating calls `system_health.evaluate_system_health` directly, uncached |
| command-centre notes | 30 s | a new hand-written note absent for ≤ 30 s | Safe — invisible on a "today" panel |
| `open_positions` (2 s) | 2 s | floating PnL 2 s stale | Safe — UI refreshes on a 20 s interval anyway |
| `closed_trades` (5 s) / `price_alerts` (8 s) | — | journal / alert list slightly stale | Safe |

No cache returns future information. No per-viewer state exists (every cached
response is shared, read-only). A cached response's `timestamp` is the
cache-fill time — an *honest* "data as of T", not a misleading current-time
stamp. **No cache is inappropriate; no TTL needs changing.**

---

## Browser — realistic navigation (production build, `frontend/dist`)

Headless Chrome / CDP against the **real bundle** on a static server proxying
`/api` (not the Vite dev server — dev mode's React StrictMode double-invokes
effects and is not representative).

### Initial cold load
| | |
| :-- | --: |
| time to content stable | **503 ms** |
| initial JS transferred | **308.6 kB** (index 264 + vendor 51 + landing route chunk) |
| API calls on load | **3** (`/api/health`, `/api/watchlist`, `/api/market/snapshot/XAUUSD`) |
| TTFB / DOMContentLoaded / load | 2 ms / 33 ms / 34 ms |

### SPA session navigation (14 transitions: workspace → command-centre → intelligence → strategy → audit → macro → evidence → journal → ops-audit → ops-system → analytics → positions → alerts → back)
| | |
| :-- | --: |
| client-side route change | **2–3 ms** every route |
| route chunk transferred | 5 – 22 kB (0 kB on return to an already-visited route) |
| API requests per route | **0 – 4**, one per resource |
| **duplicate API requests** | **0** |
| slowest single API in the walk | `intelligence/heatmap` 607 ms, `watchlist` 677 ms, `operations/system` 460 ms — one-off cold-cache hits (≈ a few Postgres RTTs); every other call < 25 ms |

Content-visible time per route is ~50–120 ms (the ~460 ms "stable" figure in the
raw log is dominated by the detector's 350 ms settle window).

### In-page actions
| Action | Cost | Requests |
| :-- | --: | :-- |
| Asset switch (watchlist → chart) | **0.6 ms** API | 1 (`/api/market/snapshot/<SYM>`) |
| Watchlist filter | instant | **0** (client-side filter of the loaded list) |
| Timeframe switch | n/a | external TradingView `<iframe>` — not app-controlled |
| Command palette open | **6 ms** | 0 |

### Regression QA — 19 routes × 3 resolutions (1280×720 / 1440×900 / 1920×1080) = 66 loads
```
console errors ... 0        horizontal overflow ... 0
uncaught exceptions ... 0   routes rendering content ... 66/66
command palette Ctrl+K opens ... yes    Esc closes ... yes
lazy route chunks load + render ... all    re-download on return ... no
```

---

## Network request audit

- **No duplicate requests** in the production build. The `2×` seen against the
  Vite dev server is React `<StrictMode>` double-invoking effects in
  development only — expected, not a defect.
- Each route fetches **one request per resource**; the market-intelligence and
  macro pages fire 3–4 parallel independent requests (summary / opportunity-map
  / heatmap ; overview / currencies / events / assets) — correctly parallel, no
  dependency chain to collapse.
- Largest payloads: the operations-journal and operations-audit route chunks
  (~10 kB gzip) and their JSON (audit ~5 kB text). Nothing oversized.
- No request is fired that the current UI does not consume.

---

## Frontend rendering & bundle

| | Phase 62 | Phase 63 verified |
| :-- | --: | --: |
| initial JS (transfer) | ~315 kB total | **308.6 kB** measured on load |
| `index.js` | 264.2 kB | 264.21 kB (unchanged) |
| `react-vendor.js` | 51.4 kB | 51.42 kB (unchanged) |
| route chunks | 20 lazy | 20, 0.4–22 kB, load on first visit, cached on return |
| Suspense fallback | present | renders correctly, no flash-of-empty |

No long tasks or expensive re-renders observed during the session walk (route
change → content in ~50–120 ms, no layout shift, no console warnings). No
rendering change was warranted.

---

## Slowest user actions — ranked (measured)

| # | Action | Cost | Nature |
| --: | :-- | --: | :-- |
| 1 | **Initial application load** | ~500 ms to usable content | one-off; 309 kB JS + 3 API calls |
| 2 | **First visit to `/workspace/command-center` after a cache-cold window** | ~145 ms (warm-up) → up to ~700 ms (fully cold) | ~1–8 Postgres RTTs depending on which section caches lapsed |
| 3 | First hit of any endpoint whose cache has expired | ~200–680 ms | 1–4 Postgres RTTs (~85–125 ms each) |
| 4 | `/workspace/analytics` | ~35 ms warm / ~65 ms cold | recompute over `closed_trades` (53 rows) |
| 5 | Every other navigation / asset switch / palette | **1–20 ms** | client-side or cache hit |

Nothing a user would perceive as "slow" in normal steady-state use.

---

## Scaling thought experiment (analysis only — no infra changes)

Pool: `DB_POOL_MIN=1`, `DB_POOL_MAX=12`. Query RTT ~85–125 ms. Single uvicorn
worker. Warm reads = **0 DB checkouts** (cache-served).

| Concurrent users | Expectation |
| --: | :-- |
| **10** | Fine. Navigation is staggered in real use; cache hit rate high; pool rarely > 2–3 in use. Worst case (all hit a cold command-centre at once) → brief pool pressure, recovers. |
| **25** | Mostly fine. Risk window: every 8–30 s a cache TTL lapses and the first request rebuilds — if several land in that window on `/api/command-center/overview`, its 8× fan-out can transiently exhaust the pool (slow direct-connect fallbacks, no errors). |
| **50** | The command-centre fan-out and concurrent cache-miss stampedes need attention. The pool (12) and the managed-PG connection ceiling become the limit for uncached paths. |
| **100** | Requires: a larger pool, a command-centre fan-out cap (or sequential build), longer/shared cache, and realistically a co-located database to kill the RTT. Single uvicorn worker also becomes a CPU limit — add workers (each gets its own pool + cache). |

The architecture scales **well for cached read traffic** (the common case) and
has a **known soft spot on concurrent cache-miss on the fan-out endpoint**.

---

## Infrastructure limitations (NOT application problems)

1. **Managed PostgreSQL query RTT ≈ 85–125 ms.** Every uncached DB read pays it
   once; the pool removed the *connect* cost but not the per-query network
   latency. Structural fix = co-located database / read replica — an
   infrastructure decision, explicitly **out of scope** for this phase.
2. **Single uvicorn worker** in the current run model — one GIL, one pool. Fine
   now; a multi-worker deployment is the first lever if concurrency grows.
3. **TradingView chart widget** — external `<iframe>`; its load time is not
   application-controlled and not counted against the app.

---

## New optimizations

**None.** Phase 63 is a verification phase and found no application-level P1
bottleneck requiring an immediate code change.

A candidate change — replacing the command-centre `ThreadPoolExecutor` with a
sequential section build — was implemented and measured:

| | warm single-user p50 | concurrent (TestClient, noisy) |
| :-- | --: | :-- |
| current (ThreadPoolExecutor) | 22.5 ms | conc 20 → 5.2 s |
| sequential | 18.7 ms | conc 20 → 20.8 s (worse) / conc 10 → 132 ms (better) |

The single-user gain is marginal (~4 ms) and the concurrent picture was
inconsistent under the unreliable TestClient harness. **Reverted.** The right
way to settle this is a real `uvicorn` + `wrk`/`locust` load test — recorded as
deferred work below, not done here.

---

## Deferred work

| Item | Priority | Why deferred |
| :-- | :-- | :-- |
| Command-centre fan-out under concurrent load — measure with a real uvicorn load test, then decide: sequential build, `max_workers` cap, or a per-request connection budget | **P2** | Not affecting the single-instance deployment; needs a trustworthy load generator, not TestClient |
| Cold `/api/operations/audit` first hit ~570–607 ms — combine the 4 `execution_orders` queries + the `LIMIT 1000` ledger read into fewer round-trips | **P3** | Warm is 2 ms; warm-up hides it; carried from Phase 62 (`TECHNICAL_DEBT.md` P3-4) |
| `/api/analytics/performance` recompute over the full journal | **P3** | 35 ms warm today; only a problem if `closed_trades` grows large |
| Co-located Postgres / read replica to remove the ~100 ms RTT | infra | Infrastructure decision, out of scope |
| Multi-worker uvicorn for concurrency headroom | infra | Deployment decision |

---

## Safety invariants — verified unchanged

| Invariant | Status |
| :-- | :-- |
| Strategy contract SHA-256 `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` | **PRESERVED** (asserted in-session) |
| Historical baseline N=82, E[R]=+0.637R, WR=58.6 %, PF=2.52 | **PRESERVED** — no test touched, suite green |
| Dataset isolation `IDs_hist ∩ IDs_paper/shadow = ∅` | **PRESERVED** — isolation tests pass |
| `LIVE_AUTOMATION_ENABLED` | **False** (verified via `/api/operations/system`) |
| `LIVE_BROKER_TRANSMISSION` | **"BLOCKED"** (verified) |
| Lookahead protection `release_timestamp <= as_of` | **PRESERVED** — no cache added to any market/macro/evidence read path |
| Contextual intelligence stays non-execution | **PRESERVED** — no execution/broker/risk file touched (0 code changes) |

`execution_pipeline.py`, `broker_adapter.py`, `risk_gateway.py`, reconciliation
— **not touched.** Macro scorecard — **still PARKED**, not implemented. The 12
EdgeFinder screenshots the user added under `docs/reference/` are reference
material for that parked backlog only.

---

## Tests / build / QA

```
pytest tests/ -p no:randomly ... 1059 passed, 2 skipped, 0 failed  (69–110 s)
tsc -b ......................... clean
npm run build ................. clean — 264.21 kB index + 51.42 kB vendor, no chunk warning
browser QA .................... 19 routes × 3 resolutions = 66 loads
                                0 console errors · 0 exceptions · 0 overflow
                                command palette + keyboard shortcuts working
```

---

## Before / after / current

| Operation | Pre-62 | Phase 62 | Phase 63 verified | Status |
| :-- | --: | --: | --: | :-- |
| `/api/alerts` | 372 ms | 2.1 ms | **1.5 ms warm** | ✅ stable |
| `/api/operations/audit` | 1420 ms | 2.8 ms | **2.0 ms warm** / 607 ms cold | ✅ stable |
| `/api/operations/system` | 760 ms | 2.0 ms | **1.7 ms warm** / 131 ms cold | ✅ stable |
| `/api/command-center/overview` | 804 ms | 26 ms | **15.5 ms warm** / 145 ms warmed-cold | ✅ stable |
| `/api/watchlist` | 1056 ms cold | 1.9 ms warm | **1 ms warmed-cold / 1.9 ms warm** | ✅ stable |
| `/api/analytics/performance` | 462 ms cold | 40 ms | **34.5 ms warm** | ✅ stable |
| DB checkout (steady) | ~406 ms | — | **0.036 ms** | ✅ verified |
| DB query RTT | ~125 ms | ~125 ms | **~85–125 ms** | infra limit |
| Initial JS | 510 kB / 137 kB gz | ~315 kB chunks | **308.6 kB on load** | ✅ stable |
| SPA route change | — | — | **2–3 ms** | ✅ |

---

## PHASE 63 — COMPLETE

```
Status:                        PASS WITH DEFERRED ITEMS
Repository:                     CLEAN
Baseline:                       1059 passed / 2 skipped / 0 failed
TypeScript:                     PASS
Build:                          PASS (264.21 kB index + 51.42 kB vendor, no warning)
Browser QA:                     19 routes × 3 resolutions
                                0 errors / 0 exceptions / 0 overflow
Phase 62 performance:           VERIFIED — stable, reproducible, no regression
New P1 bottleneck:              NO
                                NO APPLICATION-LEVEL P1 BOTTLENECK FOUND
Remaining infrastructure limit: Managed PostgreSQL query RTT ≈ 85–125 ms per
                                uncached read (pool removed the ~406 ms connect
                                cost; per-query network latency is structural)
Deferred (P2):                  command-centre 8-way fan-out multiplies pool
                                checkouts under concurrent cache-miss — needs a
                                real uvicorn load test to size
Code changes:                   NONE
Commit:                         0fc7730  (docs only — report + reference images)
```

## STOP

Verification complete. No feature started, no infrastructure changed, no
arbitrary optimization made. We now know: warm navigation is 1–35 ms and makes
zero DB round-trips; the pool reuses perfectly; the caches are correct; the
initial load is ~500 ms / 309 kB; and the next real lever is either the
command-centre concurrency behaviour (P2, load-test first) or the managed-DB
RTT (infrastructure). The next engineering phase should be decided from that.
