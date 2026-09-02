# STAGE 10 — Final Integration, Performance Benchmark & Full Regression Gate

**Roadmap reference:** `docs/REACT_MIGRATION_AUDIT.md` §6, STAGE 10
**Baseline commit:** `d23a54f` — `fix(risk): currency-convert FX position sizing and margin to USD`
**Date:** 2026-09-02
**Verdict:** ✅ **PASS** — the React SPA migration (roadmap Stages 4–9, plus the
Strategy Lab / Backtesting and Operations suites) is feature-complete, parity-verified
against the authoritative Python core, and safe. No feature code was added in this
stage; it is a validation, benchmark and documentation gate.

---

## 1. Scope

This stage runs the roadmap's final gate before "Streamlit Legacy UI Retirement
Evaluation":

- Full backend regression (categorised: new / pre-existing / unrelated)
- Frontend `tsc -b` + production build
- Browser QA across **every** migrated route (render, real data, responsive,
  a11y, console/exception cleanliness)
- Network QA (request counts, N+1, polling, hidden-tab, StrictMode, mutations)
- Safety QA (fail-closed invariants, execution-control / mutation-endpoint scan)
- Golden-reference parity vs. the authoritative Python engines
- Measured performance (no fabricated numbers)

**Not in scope** (explicitly deferred): Streamlit retirement, code-splitting,
backend cleanup, new features, the embedded AI assistant.

---

## 2. Migrated surface — final inventory

All 12 sidebar items are `status: 'live'`; there are no remaining shell or
placeholder pages. `PlaceholderPage` is an unreachable fallback; `ZoneOverviewPage`
is used only for the `/research` landing (a genuine 3-link overview).

| Route | Page | Backend endpoint(s) |
| :-- | :-- | :-- |
| `/` → `/workspace` | redirect | — |
| `/workspace`, `/workspace/market` | MarketWorkspacePage | `/api/watchlist`, `/api/market/snapshot/{sym}` |
| `/workspace/risk` | RiskGatewayPage | `POST /api/risk/preview`, `/api/positions`, `/api/watchlist` |
| `/workspace/positions` | PositionsPage | `/api/positions` |
| `/research` | ZoneOverviewPage | — |
| `/research/intelligence` | IntelligencePage | `/api/intelligence/{summary,opportunity-map,heatmap}` |
| `/research/intelligence/asset/:symbol` | AssetProfilePage | `/api/intelligence/asset-profile/{symbol}` |
| `/research/strategy` | StrategyLabPage | `/api/research/strategy` |
| `/research/backtest` | BacktestWorkspacePage | `/api/research/strategy`, `POST /api/research/backtest` |
| `/evidence` | EvidenceCommandCenterPage | `/api/forward-evidence/state` |
| `/evidence/forward` | ForwardEvidencePage | `/api/forward-evidence/state` |
| `/evidence/statistics` | EvidenceStatisticsPage | `/api/forward-evidence/state` |
| `/evidence/governance` | EvidenceGovernancePage | `/api/forward-evidence/state` |
| `/operations` | OperationsOverviewPage | `/api/operations/{system,journal,audit}`, `/api/positions` |
| `/operations/journal` | JournalPage | `/api/operations/journal` |
| `/operations/audit` | AuditPage | `/api/operations/audit` |
| `/operations/system` | SystemHealthPage | `/api/health`, `/api/operations/system` |
| `*` | NotFoundPage | — |

Every page also consumes `/api/health` via the app-wide `HealthProvider` (slow
poll, hidden-paused) for the connection/safety ribbon.

---

## 3. API surface & mutation audit

18 endpoints (OpenAPI `/openapi.json`):

| Method | Count | Endpoints | Mutates? |
| :-- | :-- | :-- | :-- |
| GET | 14 | `/`, `/api/health`, `/api/watchlist`, `/api/market/snapshot/{sym}`, `/api/preferences`, `/api/intelligence/{summary,opportunity-map,heatmap}`, `/api/intelligence/asset-profile/{sym}`, `/api/positions`, `/api/forward-evidence/state`, `/api/operations/{journal,audit,system}`, `/api/research/strategy` | No |
| PUT | 1 | `/api/preferences` | User terminal layout/settings only — no execution, risk, strategy or evidence state (Stage 3) |
| POST | 2 | `/api/risk/preview` (calculation-only; `live_broker_transmission: "BLOCKED"`, transmits nothing), `/api/research/backtest` (research-only; runs `backtester.run_backtest` on yfinance history, fail-closed `LiveTradingSafetyBarrier` check, no broker path) | No trading/account/broker state |

**Zero** order / execute / close / modify / cancel / transmit / automation-enable
endpoints exist. During browser QA, **no non-GET request fired on any route load**
(`nonGetApi: []` for all 18 routes).

---

## 4. Backend regression

Command: `python -m pytest tests/ -q` (tracked suite) and full-tree run.

| Scope | Result |
| :-- | :-- |
| **Tracked suite (`tests/`)** | **898 passed, 2 skipped, 0 failed** (75 s) |
| Full tree (incl. gitignored root scratch files) | 905 passed, 2 skipped, **2 failed** (177 s) |

**The 2 failures are in gitignored, untracked, root-level scratch files** (`/test_*.py`
is in `.gitignore`), pre-existing and unrelated to the migration or the risk fix:

| Test | Category | Detail |
| :-- | :-- | :-- |
| `test_backtester.py::TestBacktester::test_lot_rounding` | pre-existing / unrelated | Fails on the clean `b40450b` tree; `backtester.py` last changed `fd70f7f` (2026-09-01, before Stage 4); untouched by Stages 4–11 and the risk fix. Per the risk-fix report, deliberately not "fixed" by editing `backtester.py`. |
| `test_ws.py::test_websocket_stream` | pre-existing / infrastructure | "async def functions are not natively supported" — `pytest.mark.asyncio` with no `pytest-asyncio` plugin registered. Experimental websocket scratch file, not part of the product or the migration; installing the plugin is a dependency change out of scope. |

No **new** failures. No **migration-introduced** failures.

Targeted re-runs during this gate: `test_api_parity_stage2/3` (20 passed),
`test_stage35c/d`, `test_stage10_research_adapter`, `test_stage11_operations_adapter`,
`test_forex_position_sizing` (12) — all green.

---

## 5. Frontend build

| Check | Result |
| :-- | :-- |
| `npx tsc -b` | ✅ clean, no errors |
| `npm run build` (`tsc -b && vite build`) | ✅ 142 modules, built in ~1.8 s |
| Bundle | `index.js` **431.81 kB / 119.20 kB gzip**, `index.css` 34.40 kB / 6.79 kB gzip, `index.html` 0.52 kB |
| Dependencies | unchanged since Stage 11 — `react`, `react-dom`, `react-router-dom` only; no chart library, no Axios/React-Query/Redux/Zustand, no WebSockets |

---

## 6. Browser QA (headless Chrome, CDP)

All 18 routes navigated at 1440×900; table-heavy routes also at 1920×1080,
1280×720 and 390×844.

| Check | Result |
| :-- | :-- |
| Renders with a heading + populated `<main>` | ✅ 18/18 |
| Real backend data (route-specific `/api/*` present) | ✅ every route |
| Console errors | ✅ **0** across all routes |
| Uncaught exceptions | ✅ **0** across all routes |
| Body-level horizontal overflow @ 1440 | ✅ none (18/18) |
| Body-level horizontal overflow @ 1920 / 1280 / 390 | ✅ none (8 table-heavy routes × 3 widths = 24/24) |
| 404 route → NotFoundPage ("Page not found") | ✅ |
| Command palette (Ctrl/Cmd+K) opens, lists 16 routes | ✅ |
| Loading / empty / error / retry states | ✅ verified per-stage (Stages 6–11) and re-confirmed: skeletons on load, distinct "no data" vs "unavailable / Retry" vs "not exposed", retry issues exactly one request and recovers |
| Accessibility | ✅ semantic `<section aria-label>`, labelled controls, `role="radiogroup"`/`role="radio"` toggles, `role="img"` + aria-label on bars/sparklines, `aria-live` on refresh/status, table semantics, colour + text on every status, visible focus, reduced-motion inherited |

---

## 7. Network QA

| Check | Result |
| :-- | :-- |
| N+1 / request-per-row | ✅ none — trade/audit/position tables render from one list response; no per-row detail fetch (no such endpoint) |
| Duplicate-fetch loops / fetch-on-render | ✅ none — every data hook runs its fetch inside a `[nonce]`-only effect |
| Request-per-keystroke on filters | ✅ none — all journal/audit/intelligence/heatmap filters are client-side (0 `/api/*` on filter) |
| Runaway polling | ✅ none — watchlist 20 s, market snapshot 10 s, positions 30 s, evidence 60 s, journal 60 s, audit 60 s, system 20 s, health ~30 s; all fixed-interval |
| Hidden-tab pause | ✅ verified — 0 requests over a 6 s window with `document.hidden = true` on `/operations/system` |
| Request cancellation / disposed-response guard | ✅ `AbortController` + request-id / `disposed` flag in every hook; verified race-safe in Stages 8–11 |
| StrictMode double-submit | ✅ none — `POST /api/risk/preview` and `POST /api/research/backtest` fire only on explicit click (`riskAutoPosts: 0`, `backtestAutoPosts: 0`) |
| Module-cache reuse | ✅ operations resources share a 12 s module cache so the `/operations` overview reuses sub-page fetches |
| Unintended mutations | ✅ none — no PUT/POST/DELETE on any route load |

Per-route backend call counts (excluding the shared `/api/health` poll and Vite
dev `*.ts` module loads, which vanish in the production bundle): 1 endpoint for
single-source pages, 3 for the intelligence command center (`Promise.allSettled`),
4 for the operations overview fan-out. No page exceeds 4.

---

## 8. Safety QA

| Invariant | State |
| :-- | :-- |
| `LIVE_AUTOMATION_ENABLED` | **False** — `/api/health.automation_enabled=false`, `/api/operations/system.live_automation_enabled=false` |
| `LIVE_BROKER_TRANSMISSION` | **BLOCKED** — returned by `/api/health`, `/api/operations/system`, `/api/risk/preview`, `/api/operations/audit`; shown as `🔒 LIVE BLOCKED` (topbar) and `SAFETY BLOCKED` (ribbon) on every page |
| Execution controls added | **NO** — full-DOM scan of all 18 routes for buy/sell/execute/submit-order/place-order/send-order/transmit/close-position/modify-position/cancel-order/go-live/enable-automation found **only** the Risk Gateway `BUY`/`SELL` **`role="radio"`** toggle, which selects the trade *direction for the position-sizing calculation*. It transmits nothing. The only action buttons on that page are "Calculate Risk" and the command-palette trigger. `anyOrderButton: []`. |
| Unexpected mutation endpoints | **NO** — see §3. `PUT /api/preferences` (UI layout) is the only mutation and predates the migration. |
| AI / analytics | read-only; no embedded assistant exists |
| Strategy Contract SHA-256 | `7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76` — served verbatim by `/api/forward-evidence/state` and `/api/research/strategy`, matches `FROZEN_CONTRACT_HASH` |
| Dataset separation | Positions (operational) / Journal (`closed_trades`) / Audit (`execution_orders`) / Backtest (yfinance research) / Forward Evidence (Phase 49) are distinct surfaces with their authoritative `mode`/`account`/`source` retained; never merged |

---

## 9. Golden-reference parity (Python engine vs FastAPI adapter, live)

| Surface | Engine | Adapter | Match |
| :-- | :-- | :-- | :-- |
| Risk preview `calculated_lot_size` / `actual_risk_usd` / `actual_risk_pct` / `estimated_margin_usd` / `target_risk_usd` (USDJPY SELL 159.487/159.921, 3%, $10k) | 1.1 / 299.33 / 2.99 / 1100.0 / 300.0 | identical | ✅ |
| Positions count | `database.get_open_positions` → 2 | `total_open` → 2 | ✅ |
| Journal count | `database.get_closed_trades` → 53 | `total_trades` → 53 | ✅ |
| Forward evidence `sample_n` | `Phase49MonitoringFacade` → 0 | 0 | ✅ |
| Contract hash | `FROZEN_CONTRACT_HASH` | identical | ✅ |
| Safety flags | `False` / `BLOCKED` | identical on `/api/health` and `/api/operations/system` | ✅ |

The `tests/test_api_parity_stage2.py` + `test_api_parity_stage3.py` semantic-parity
suites (20 tests) also pass. Streamlit remains operational — `:8501/_stcore/health`
→ `ok` — and was not modified.

---

## 10. Performance (measured, dev server, warm, median of 5)

**Backend API latency (browser `fetch` → FastAPI on :8010):**

| Endpoint | Median |
| :-- | --: |
| `/api/health` | 4 ms |
| `/api/watchlist` | 4 ms |
| `/api/positions` | 5 ms |
| `/api/market/snapshot/XAUUSD` | 3 ms |
| `/api/intelligence/summary` | 4 ms |
| `/api/intelligence/opportunity-map` | 5 ms |
| `/api/intelligence/heatmap` | 6 ms |
| `/api/forward-evidence/state` | 5 ms |
| `/api/research/strategy` | 5 ms |
| `/api/operations/journal` | 8 ms |
| `POST /api/risk/preview` | 5 ms |
| `/api/operations/system` | **738 ms** |
| `/api/operations/audit` | **1,379 ms** |

The Stage 3.5A–D optimizations hold — the intelligence, evidence, risk-preview,
watchlist, snapshot and positions read paths are all single-digit-millisecond warm.

**Route render (navigate → first heading / → primary content populated), dev:**

| Route | First heading | Populated |
| :-- | --: | --: |
| `/evidence` | 251 ms | 255 ms |
| `/operations/audit` | 268 ms | 269 ms |
| `/research/strategy` | 144 ms | 259 ms |
| `/workspace/positions` | 269 ms | 611 ms |
| `/workspace/market` | (h2, ~250 ms) | 888 ms |
| `/research/intelligence` | 1,627 ms | 1,639 ms |
| `/operations` | 148 ms | 2,011 ms |

`/research/intelligence` first-paint and `/operations` populated-time are inflated
by (a) the Vite **dev** module graph for the heaviest pages and (b) the slow
`/api/operations/audit` endpoint feeding the `/operations` fan-out. Production
(bundled, tree-shaken) removes (a); (b) is the deferred item below.

---

## 11. Findings & deferred items

Nothing blocks the gate. Recorded for a future performance sub-stage:

1. **`/api/operations/audit` (~1.4 s) and `/api/operations/system` (~0.7 s) are
   uncached.** Both are Stage 11 read-only adapter endpoints. `audit` runs 3
   aggregate `COUNT`/`GROUP BY` queries + a 200-row SELECT on `execution_orders`
   per call; `system` runs `system_health.evaluate_system_health` (several DB
   round-trips + reconciliation health). The frontend already throttles them
   (60 s / 20 s poll, hidden-paused, 12 s module cache), so idle load is bounded,
   but a cold load and the `/operations` overview are slow. **Recommended
   follow-up:** a bounded process-local TTL cache consistent with Stage 3.5A–D
   (e.g. `audit` 10 s, `system` 5 s), as one focused commit with a
   `tests/test_stage35*`-style benchmark. Not done here — this gate does not add
   or modify feature code.
2. **`test_backtester.py::test_lot_rounding`** — pre-existing failure in a
   gitignored scratch file; a future stage may evaluate the backtester lot-rounding
   policy directly.
3. **`test_ws.py`** — experimental websocket scratch file; would need
   `pytest-asyncio` registered to run. Not product code.
4. **Streamlit retirement** — the roadmap's next step ("Streamlit Legacy UI
   Retirement Evaluation") is a separate decision, not part of this gate.

---

## 12. Verdict

✅ **PASS.** The React SPA is a complete, parity-verified, fail-closed replacement
for the Streamlit presentation layer's operational surfaces. All authoritative
calculation, research, evidence, risk and safety logic remains in Python;
FastAPI is a thin adapter; React is presentation only. Streamlit stays operational
as the golden reference. No execution capability, no live automation, no broker
transmission was introduced anywhere in Stages 4–11 or this gate.
