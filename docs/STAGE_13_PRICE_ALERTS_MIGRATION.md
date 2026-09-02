# STAGE 13 — Price Alerts Migration

**Roadmap reference:** `docs/STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md` §11 —
migration unit 2 of 4 ("`GET/POST/DELETE /api/alerts` + React Price Alerts page —
`alerts.py` is a clean, bounded module").
**Baseline commit:** `6c53633` — `feat(journal): migrate journal editing to React`
**Date:** 2026-09-02
**Scope:** price-target alert CRUD only. No custom notification-rules engine, no
Analytics / Daily Command Center / Research Lab / AI Assistant / paper execution.

---

## 1. Original Streamlit behavior

`app.py` → "TRADING WORKSPACE" zone → "PRICE ALERTS" subview (`app.py:3960–4026`):

1. A TradingView symbol picker (HTML component) plus a form:
   - **Target Asset** — `st.selectbox` over `TV_CATALOG` ids, or `CUSTOM` → free text.
   - **Target Price ($)** — `st.number_input`, step 0.5, 2 decimals.
   - **Condition** — `st.selectbox` `ABOVE` ("Rose Above (>=)") / `BELOW` ("Dropped Below (<=)").
   - **Alert Notes** — `st.text_input`, optional.
2. "Set Price Alert" → `database.create_price_alert(symbol, target_price, condition, notes)`
   (rejects only an empty symbol client-side) → `st.rerun()`.
3. A list of the latest 50 alerts (`database.get_all_price_alerts(limit=50)`),
   each with a status badge (`ACTIVE` / `TRIGGERED`) and a **Delete** button →
   `database.delete_price_alert(id)` → `st.rerun()`.
4. A separate "RULES" sub-tab wraps `alerts.get_alert_rules` /
   `save_alert_rules` (trade-close notification thresholds) — **not part of this
   migration** (documented as remaining Streamlit-only, §9).

### Evaluation mechanism (unchanged, not touched)

The `auto_sync.py` daemon loop (`auto_sync.py:77–109`) — independent of any UI —
reads `database.get_active_price_alerts()`, fetches the live MT5 bid for each
symbol, and on a cross calls `alerts.notify_price_alert(...)`
(OneSignal / Telegram / Discord / Windows toast) + `database.mark_price_alert_triggered(id)`.
**Stage 13 adds no evaluation, polling or notification code** — the new router
is pure CRUD over the same table.

### Execution coupling: NONE

`alerts.py` contains only outbound notification helpers (HTTP POST to
OneSignal / Telegram / Discord, a local PowerShell toast) and a JSON rules file.
It never imports `execution_pipeline`, a broker adapter, or the risk gateway,
and cannot submit / modify / cancel / transmit an order. Verified by
`test_stage13_price_alerts.py::test_alerts_router_imports_no_execution_modules`.

---

## 2. Alert data model (`price_alerts` table)

| Column | Type | Origin | Notes |
| :-- | :-- | :-- | :-- |
| `id` | INTEGER PK AUTOINCREMENT | **server** | never client-controlled |
| `symbol` | TEXT NOT NULL | client → normalized | stored as the canonical symbol |
| `target_price` | REAL NOT NULL | client | `> 0`, finite |
| `condition` | TEXT NOT NULL | client | `ABOVE` \| `BELOW` |
| `account_id` | TEXT DEFAULT `'ALL'` | — | always `ALL` (Streamlit never set it either) |
| `status` | TEXT DEFAULT `'ACTIVE'` | **server** | → `TRIGGERED` by the daemon |
| `created_at` | TEXT NOT NULL | **server** | ISO-8601 UTC |
| `triggered_at` | TEXT NULL | **server** | set by the daemon |
| `notes` | TEXT NULL | client | ≤ 500 chars |

**Condition semantics** (preserved exactly from `auto_sync.py`):
`ABOVE` fires when `current_price >= target_price`; `BELOW` fires when
`current_price <= target_price`.

---

## 3. API contract — `/api/alerts`

### `GET /api/alerts`
`AlertsResponse { alerts: AlertItem[], total, active, triggered, supported_symbols: string[], source: "price_alerts", live_broker_transmission: "BLOCKED", timestamp }`
— the latest 50 rows from `database.get_all_price_alerts`, newest first.
`supported_symbols` is `sorted(symbol_mapping.CANONICAL_SYMBOLS)` (19) so the
client never maintains its own symbol list.

### `POST /api/alerts`  → `201`
Request `AlertCreateRequest` (`extra="forbid"`):

| Field | Rules |
| :-- | :-- |
| `symbol` | 1–32 chars; `normalize_symbol()` must resolve it (canonical or alias, e.g. `gold`→`XAUUSD`) → else **422** |
| `target_price` | `> 0`, finite → else **422** |
| `condition` | `ABOVE` \| `BELOW` (exact, case-sensitive) → else **422** |
| `notes` | optional, ≤ 500 chars |

Any other key (`id`, `status`, `created_at`, `triggered_at`, `account_id`, …) → **422**.
Persistence: `database.create_price_alert(symbol=<canonical>, …)`. Response
`AlertCreateResponse { alert: AlertItem, live_broker_transmission, timestamp }`
with the **re-read** row.

### `DELETE /api/alerts/{alert_id}`  → `200`
`alert_id` must be an integer ≥ 1 (else **422**). Unknown id → **404**.
Deletes via `database.delete_price_alert`. Response
`AlertDeleteResponse { deleted: true, alert_id, timestamp }`.

### No `PUT` / `PATCH`
The Streamlit workflow has no edit path (delete + recreate). None added.
`PUT /api/alerts` and `PATCH /api/alerts/{id}` → **405**.

CORS `allow_methods` gains `DELETE` (dev is same-origin via the Vite proxy;
relevant only for a future hosted cross-origin build).

---

## 4. React functionality — `/workspace/alerts`

New nav item `workspace.alerts` ("Price Alerts", `BellIcon`) under Trading
Workspace; `PriceAlertsPage` + `components/alerts/AlertsPanel.tsx`.

- **Create form** — symbol (`<input>` + `<datalist>` fed by
  `supported_symbols`), target price, condition (`≥ above` / `≤ below`), note.
  Submit disabled until symbol + a positive numeric price are present.
  `Setting…` state; inline API/validation error; green confirmation flash.
- **List** — table: symbol, condition, target, status tag, note, created
  (+ "fired …" for `TRIGGERED`), Delete. Per-row `Deleting…` state; row-level
  error line; delete disabled while another delete is in flight.
- **States** — skeleton on first load, `SectionError` + retry on hard failure,
  "showing last good list" banner on a failed refresh, empty state explaining
  the daemon checks active alerts.
- **Requests** — `useAlerts` does one `GET` on mount + a 60s interval refresh
  (paused while the tab is hidden) to catch daemon-side `TRIGGERED`
  transitions; create/delete each fire one request then one authoritative
  `refetch()`. No optimistic alert state, no per-row polling, no N+1.
  `AbortController` + `disposed` guards.
- **No execution controls** — verified by browser scan (0 buy/sell/execute/…).

---

## 5. Rules-engine reuse

- Persistence: **reused** `database.create_price_alert` / `get_all_price_alerts`
  / `delete_price_alert` verbatim — no SQL duplicated, no second alert store.
- Symbol validation: **reused** `symbol_mapping.normalize_symbol` /
  `CANONICAL_SYMBOLS` — no second symbol list.
- Evaluation + notification: **untouched** — still `auto_sync.py` +
  `alerts.notify_price_alert`. The API neither imports nor triggers them.
- The `alerts.py` custom trade-close **rules engine** (`get_alert_rules` /
  `save_alert_rules` / `notify_trade_closed`) is **out of scope** and unchanged.

---

## 6. Validation

| Rule | Enforcement |
| :-- | :-- |
| unknown symbol | `normalize_symbol` → `None` → 422 |
| symbol alias | normalized & stored canonical (`gold`→`XAUUSD`, `us100`→`NAS100`) |
| `target_price <= 0` / NaN / inf | pydantic `gt=0` + finite validator → 422 |
| bad `condition` | `Literal["ABOVE","BELOW"]` → 422 |
| missing required field | pydantic → 422 |
| unknown field | `extra="forbid"` → 422 |
| non-integer `alert_id` | FastAPI path `int` → 422 |
| unknown `alert_id` | existence check → 404 |
| server fields in body | rejected as unknown (422) |

---

## 7. Safety verification

| Check | Result |
| :-- | :-- |
| `execution_pipeline` / `broker_adapter` / `risk_gateway` / order-submission files touched | **none** (`git diff --stat`) |
| router namespace binds any execution/broker symbol | **no** (`test_alerts_router_imports_no_execution_modules`) |
| `automation_enabled` after create+delete | `false` (unchanged) |
| `live_broker_transmission` after create+delete | `BLOCKED` (unchanged) |
| `execution_orders` count / `mode_counts` after CRUD | unchanged |
| `open_positions` after CRUD | unchanged |
| React page execution controls (buy/sell/execute/transmit/…) | **0** |
| unexpected order/execution/broker/risk request from the page | **none** (browser network scan) |

---

## 8. Parity status

| Streamlit capability | React / API | Status |
| :-- | :-- | :-- |
| List price alerts (50, status badges) | `GET /api/alerts` + table | **FULLY_REPLACED** |
| Create alert (symbol, price, condition, notes) | `POST /api/alerts` + form | **FULLY_REPLACED** (stricter: canonical symbols only) |
| Delete alert | `DELETE /api/alerts/{id}` + row button | **FULLY_REPLACED** |
| `ACTIVE` / `TRIGGERED` display | status tag + "fired …" timestamp | **FULLY_REPLACED** |
| Arbitrary custom symbols (`SOLUSDT`, …) | rejected 422 | **INTENTIONAL DELTA** — see §9 |
| TradingView symbol-picker widget | `<datalist>` of canonical symbols | **INTENTIONAL DELTA** (no TV iframe, consistent with Stage 6) |
| Custom notification-rules sub-tab | — | **NOT MIGRATED** (Streamlit-only) |

**Price Alerts CRUD can now be removed from the Streamlit UI** (the
`app.py:3960–4026` block) without loss of function — the React page + API cover
it and the daemon is UI-independent. **Not doing so in this stage** (scope =
migration, not retirement). The `database.*_price_alert` helpers and the
`price_alerts` table must stay regardless (the daemon and the new API both use
them).

---

## 9. Remaining Streamlit capabilities / deferred

- **Custom notification-rules engine** — `alerts.get_alert_rules` /
  `save_alert_rules` + the "RULES" sub-tab (big-win / max-loss / daily-drawdown
  thresholds, `notify_on_all_trades`). No API, no React. Still Streamlit-only.
- **Arbitrary non-canonical symbols** — Streamlit stored any free-text symbol;
  the API restricts to the 19 canonical instruments (+ aliases). If a
  non-canonical instrument is genuinely needed, extend `CANONICAL_SYMBOLS` /
  `SYMBOL_ALIASES` rather than loosening the validator.
- **Alert editing** — neither Streamlit nor this stage supports it (delete +
  recreate). Not added.
- **Per-account alerts** — column exists, always `ALL`. Not exposed.
- **Next migration units** (unchanged): `GET /api/analytics/*` + React Analytics,
  then Daily Command Center, Research Lab, AI Assistant, paper execution.
- **Pre-existing latent bug (still out of scope):** `api/routers/positions.py:34`
  unguarded `float(pos.get("tp", 0.0))` on a NULL `tp`.

---

## 10. Tests & validation

**`tests/test_stage13_price_alerts.py`** (27 cases incl. parametrized): GET
shape + canonical-model match · POST creates / normalizes alias · POST rejects
7 invalid payloads · POST rejects unsupported symbol + condition · 6 unknown
fields rejected · DELETE removes / 404 unknown / 422 non-integer · persistence
survives GET + direct DB read · no PUT/PATCH (405) · CRUD leaves
`execution_orders` / `open_positions` / automation / broker flags unchanged ·
router imports no execution module.

| Gate | Result |
| :-- | :-- |
| Full suite `pytest tests/ -p no:randomly` | **948 passed, 2 skipped, 0 failed** (was 921/2/0; +27) |
| `tests/test_phase26_alerts.py`, `tests/test_phase45_alert_deduplication.py` | pass (unrelated `XAUUSDAlertEngine`; not weakened) |
| `npx tsc -b` | clean |
| `npm run build` | clean — 146 modules, 446.83 kB JS / 122.43 kB gzip |
| Browser smoke — `/workspace/alerts` | load, create (POST 201→refetch), unsupported symbol → 422 + error shown, delete (200→refetch, row gone); 0 console errors, 0 exceptions, no forbidden requests |
| Browser regression — `/workspace`, `/workspace/positions`, `/operations{,/journal,/audit,/system}` | all load, 0 console errors |

No frontend unit-test infra in `frontend/` — covered by the CDP browser smoke.

---

## 11. Files changed

| File | Change |
| :-- | :-- |
| `api/schemas.py` | `+AlertCondition`, `+AlertItem`, `+AlertsResponse`, `+AlertCreateRequest` (`extra="forbid"` + finite-price validator), `+AlertCreateResponse`, `+AlertDeleteResponse`; `+Literal` import |
| `api/routers/alerts.py` | **new** — `GET/POST/DELETE /api/alerts` thin CRUD adapter |
| `api/main.py` | register `alerts.router`; CORS `allow_methods` `+DELETE` |
| `frontend/src/api/client.ts` | `+apiDelete<T>()` |
| `frontend/src/types/alerts.ts` | **new** — alert contracts |
| `frontend/src/api/alerts.ts` | **new** — `getAlerts` / `createAlert` / `deleteAlert` |
| `frontend/src/lib/useAlerts.ts` | **new** — one-GET hook, 60s hidden-paused refresh, abortable |
| `frontend/src/components/alerts/AlertsPanel.tsx` | **new** — create form + list + delete + states |
| `frontend/src/pages/PriceAlertsPage.tsx` | **new** — `/workspace/alerts` |
| `frontend/src/lib/icons.tsx` | `+BellIcon` |
| `frontend/src/lib/navigation.ts` | `+workspace.alerts` nav item |
| `frontend/src/App.tsx` | route `workspace.alerts` → `PriceAlertsPage` |
| `tests/test_stage13_price_alerts.py` | **new** — 27 cases |
| `docs/STAGE_13_PRICE_ALERTS_MIGRATION.md` | **new** — this document |
| `PROJECT_STATE.md` | `+§9.4`; header → Session 43 |
