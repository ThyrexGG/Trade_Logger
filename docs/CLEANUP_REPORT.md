# TradeLogger — Stabilization Pass Report

*Current-state cleanup, architecture clarity, UX clarity & performance baseline.
No new feature expansion.*

---

## Baseline (before any change)

| Gate | Result |
| :-- | :-- |
| Full backend suite (`pytest tests/ -p no:randomly`) | **1043 passed · 2 skipped · 0 failed** · ~84 s |
| Frontend `tsc -b` | clean · ~5 s |
| Frontend `npm run build` | clean · ~2 s · 165 modules · 510.1 kB JS / 136.7 kB gzip (one-chunk warning) |
| Test file count | 324 |
| Repo | 104 root `.py` files, 15 API routers, 24 React pages |

Baseline API latency captured to `docs/performance_baseline.json` via the new
`performance_benchmark.py`.

---

## Cleanup performed

**Documentation (the main deliverable):**
- `docs/CURRENT_ARCHITECTURE.md` — plain-English map: 3 surfaces (React SPA is
  the product; `app.py` and `server.py` are legacy), frontend layout + hook
  pattern, router→engine table, data sources, persistence, caching, state,
  where trading safety is enforced, AI / research / evidence locations, testing.
- `docs/CURRENT_STATE.md` — what TradeLogger is now, what's implemented,
  read-only by design, disabled by design, production-safe vs **demo/seeded
  (all macro)**, incomplete, must-not-change list, recommended next area.
- `docs/TECHNICAL_DEBT.md` — P1–P3 with location / impact / recommended fix /
  why deferred.
- `docs/FUTURE_WORK.md` — CURRENTLY IMPLEMENTED / NEXT / LATER / **PARKED**
  (the EdgeFinder-style macro scorecard backlog, spelled out but explicitly not
  a task).
- `docs/performance_baseline.json` + `performance_benchmark.py` — reproducible
  in-process latency baseline for every navigation-relevant endpoint.

**Code (small, obvious, safe only):**
| Change | File | Effect |
| :-- | :-- | :-- |
| Null-safe numeric extraction for open positions | `api/routers/positions.py` | fixes a latent `TypeError` crash when a position has a `NULL` `tp` (previously only surfaced under randomized test ordering) |
| Short-TTL cache for the price-alert list + invalidation on write | `database.py` (`get_all_price_alerts(ttl_sec=)`, `create/delete/mark_*`), `api/routers/alerts.py`, `api/routers/command_center.py` | `/api/alerts` **warm p50 372 ms → 2.6 ms** (was opening a fresh Postgres connection every call) |
| Command palette closes on **Esc** from any focus | `frontend/src/components/shell/AppShell.tsx` | window-level Escape handler (the bubbled React handler missed some focus states) |
| Removed 2 unused imports introduced in Stages 15/18 | `api/ai_context.py`, `api/macro_service.py` | — |

No working code was refactored for style. No files were renamed. No dependencies
added or removed. `app.py`, `server.py`, `macro_intelligence_engine.py`,
`execution_pipeline.py`, `broker_adapter.py`, `risk_gateway.py` — untouched.

---

## Architecture — what became easier to understand

- A new reader now knows in one page which of the three backends is "the"
  backend, and that `api.main:app` is a **thin adapter** over authoritative
  engines (not a re-implementation).
- The router→engine table makes "where does X's data come from" a lookup instead
  of a code hunt.
- The recurring React data-hook pattern (`[nonce]`-only effect, AbortController,
  hidden-paused refresh, last-good-on-error) is documented once.
- Caching, freshness rules and the safety-enforcement boundary are each stated
  explicitly.

## UI/UX — what became clearer

- Command palette now behaves predictably: Ctrl/Cmd+K toggles, **Esc always
  closes**, a plain `k` typed in an input does **not** trigger it (verified).
- Browser QA confirmed every screen is legible with no layout breakage at all 3
  target resolutions (see below).
- Macro dashboard already carries a permanent "DEMO / SEEDED DATA" banner and
  `INSUFFICIENT_EVIDENCE` states — verified still correct.

No screens were redesigned; the TradeLogger visual identity is unchanged.

---

## Performance — measured, before / after

In-process `TestClient` (excludes user network latency; includes DB round-trip +
compute + cache). Warm = median of 10 calls.

| Operation (endpoint) | Before (warm p50) | After (warm p50) | Note |
| :-- | --: | --: | :-- |
| Price alerts (`/api/alerts`) | **372 ms** | **2.6 ms** | ✅ fixed — TTL cache |
| Health / watchlist / market / positions / intelligence / macro / research / evidence / journal / analytics / ai-status | 2–30 ms | 2–30 ms | already fast (router caches) |
| First visit to a Workspace page (cold) | `/api/watchlist` 771 ms, `/api/positions` 411 ms, `/api/analytics` 369 ms | unchanged | cache-miss + fresh Postgres connect — needs pooling |
| `/api/operations/audit` | ~1300 ms | ~1349 ms | ⏸ deferred (P1-2) |
| `/api/operations/system` | ~720 ms | ~783 ms | ⏸ deferred (P1-3) |
| `/api/command-center/overview` | ~715 ms | ~731 ms | ⏸ deferred (dominated by `system_health`, P1-3) |

Client-side route transitions (React Router) are instant; the "feels slow"
report is entirely the **data fetch that follows a navigation** on the 2–3 slow
endpoints above.

### Root cause of navigation slowness

`database.get_connection()` opens a **fresh `psycopg2` connection (~340 ms)** on
every call — there is **no connection pool**. Every uncached endpoint pays it;
cold page loads pay it several times. This is the single biggest lever and is a
**dedicated performance-phase change** (`TECHNICAL_DEBT.md` P1-1) — it touches
the shared persistence layer used by every engine and the sync daemons, so it is
out of scope for a cleanup pass. The pass mitigated the worst repeated offender
(`/api/alerts`) with a TTL cache.

### Remaining bottlenecks (for the performance phase)

1. **P1-1** — no DB connection pooling (~340 ms/connection).
2. **P1-2** — `/api/operations/audit` uncached (~1.3 s): counts + group-bys +
   200-row select on `execution_orders` + a 1000-row decision-ledger scan.
3. **P1-3** — `/api/operations/system` uncached (~0.7 s): full `system_health`
   diagnostic gate re-run every request; also the dominant cost of the command
   centre.
4. **P2-1** — frontend is one 510 kB JS chunk (route-level splitting).

Macro-related changes are **deferred/parked** and were not made.

---

## Technical debt summary

| Priority | Items |
| :-- | :-- |
| P0 | none |
| P1 | connection pooling (P1-1); cache `/operations/audit` (P1-2), `/operations/system` (P1-3); cold-load stacking (P1-4, subsumed by P1-1) |
| P2 | one-chunk bundle (P2-1); minor unused `typing` imports (P2-2); `database.py` is a 900-line grab-bag (P2-3); two legacy surfaces still in-tree (P2-4) |
| P3 | `research_analytics` MAE/MFE heuristic (P3-1); command-centre per-section timeout (P3-2); dead-ish `PlaceholderPage` (P3-3) |

Full detail in `docs/TECHNICAL_DEBT.md`.

---

## Macro

The EdgeFinder-inspired macro scorecard gaps remain **PARKED** — not implemented
in this pass. The Stage 18 foundation is intact: `seed_demo` provider,
`provenance` tagging on every response, `INSUFFICIENT_EVIDENCE` for
CHF/CAD/AUD/NZD, permanent "DEMO / SEEDED DATA" UI banner, read-only behaviour.
No macro data was fabricated. Backlog documented in `docs/FUTURE_WORK.md`.

---

## Safety verification

| Invariant | Status |
| :-- | :-- |
| Strategy contract SHA-256 (`xauusd_market_conditions.FROZEN_CONTRACT_HASH` = `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76`) | **PRESERVED** (byte-exact; the master-prompt quoted a `21bda769` typo — the real constant is `21dba769` and is unchanged) |
| Historical baseline N=82, E[R]=+0.637R, WR=58.6%, PF=2.52 | **PRESERVED** (locked, unpooled; `test_phase56_safety` + evidence tests pass) |
| Dataset isolation `IDs_hist ∩ IDs_paper = ∅`, `IDs_hist ∩ IDs_shadow = ∅` | **PRESERVED** (isolation tests pass) |
| `LIVE_AUTOMATION_ENABLED` | **False** (verified) |
| `LIVE_BROKER_TRANSMISSION` | **"BLOCKED"** (verified) |
| Lookahead protection (`release_timestamp <= as_of`) | **PRESERVED** (no cache added beyond its freshness window; macro/evidence read paths unchanged) |
| Contextual intelligence non-execution | **PRESERVED** (macro / AI / analytics modules bind no execution symbol — binding + import-graph tests pass) |
| `execution_pipeline` / `broker_adapter` / `risk_gateway` / reconciliation / Stage 11 cache | **untouched** (`git diff --cached --name-only` confirmed) |

---

## Tests (final)

| | |
| :-- | :-- |
| Passed | **1043** |
| Skipped | **2** |
| Failed | **0** |
| Duration | **92.95 s** (`pytest tests/ -p no:randomly`; run-to-run 82–93 s — a few tests hit the cloud Postgres) |
| tsc `-b` | clean |
| `npm run build` | clean (165 modules, 510.1 kB JS / 136.7 kB gzip) |

No tests were added (nothing new to cover; the positions fix and the alert cache
are exercised by existing suites — verified in both orderings). No test was
weakened.

---

## Browser QA

Chrome headless (CDP), resolutions **1280×720 / 1440×900 / 1920×1080**, all 19
SPA routes:

| Check | Result |
| :-- | :-- |
| Body overflow (horizontal scroll) | **0** at every route × resolution |
| Console errors | **0** |
| Uncaught exceptions | **0** |
| Command palette — Ctrl/Cmd+K opens | ✅ (22 commands) |
| Command palette — Esc closes | ✅ (fixed this pass) |
| Plain `k` in an input triggers palette | ❌ no (correct — inputs don't trigger global shortcuts) |
| Loading / empty / insufficient-data / error states | present and correct on every page |
| Macro "DEMO / SEEDED DATA" banner + `INSUFFICIENT_EVIDENCE` | shown |

Perceived navigation latency: client-side transitions instant; the follow-up
data fetch is <30 ms for most pages, ~0.7–1.3 s for `/operations/audit`,
`/operations/system`, `/workspace/command-center` (documented, deferred).

---

## Git

- Branch: `main`
- Commit: **`68c44e5`** — `chore(stabilization): current-state docs, perf baseline, small fixes`
- Working tree: clean after commit
- Files: 6 modified (`database.py`, `api/ai_context.py`, `api/macro_service.py`,
  `api/routers/{alerts,command_center,positions}.py`, `frontend/.../AppShell.tsx`),
  7 added (`performance_benchmark.py`, `docs/CURRENT_ARCHITECTURE.md`,
  `docs/CURRENT_STATE.md`, `docs/TECHNICAL_DEBT.md`, `docs/FUTURE_WORK.md`,
  `docs/CLEANUP_REPORT.md`, `docs/performance_baseline.json`). No execution/safety
  file staged. No secrets, temp files, or generated artifacts.

---

## Outcome

The repository now has: a plain-English architecture map, an explicit
current-state source-of-truth, a prioritized technical-debt list, a separated
future-work backlog (with the macro scorecard clearly parked), and a
reproducible performance baseline that names the real bottleneck (no DB
connection pooling). Two small latent bugs fixed. All 1043 tests still pass, all
safety invariants verified. No new feature was started.
