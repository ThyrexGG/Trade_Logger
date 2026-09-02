# STAGE 12 — Journal Edit Migration

**Roadmap reference:** `docs/STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md` §11 —
migration unit 1 of 4 ("`PATCH /api/operations/journal/{trade_id}` + React
journal edit — smallest, no new engine").
**Baseline commit:** `231573f` — `docs(migration): evaluate Streamlit retirement`
**Date:** 2026-09-02
**Scope:** journal annotation editing only. No Price Alerts / Analytics / Daily
Command Center / Research Lab / AI Assistant / paper execution.

---

## 1. Previous Streamlit behavior

`app.py` → "OPERATIONS, JOURNAL & AUDIT" zone → "TRADE JOURNAL" subview →
**"Log & Review Trade Setup"** (`app.py:3388–3511`):

1. User picks a closed trade from a selectbox.
2. Three editable inputs:
   - **Strategy Setup Category** — `st.selectbox` over 10 presets
     (`BREAKOUT`, `SUPPORT / RESISTANCE BOUNCE`, `ORDER BLOCK / FVG`,
     `NEWS SCALP`, `TREND FOLLOWING`, `MEAN REVERSION`, `LIQUIDITY GRAB`,
     `SUPPLY & DEMAND`, `CHART PATTERN`, `CUSTOM SETUP`) → column `setup_tag`.
   - **Setup Description, Confluences & Lessons Learned** — `st.text_area`
     → column `notes`.
   - **Chart screenshot** — file upload (→ `data:` base64 URI) *or* a pasted
     TradingView / image URL → column `chart_snapshot_url`. A "Remove
     Screenshot" button writes `""`.
3. "SAVE TRADE SETUP & SNAPSHOT" → `database.update_trade_journal(trade_id, chart_snapshot_url, setup_tag, notes)` → `st.rerun()`.

Persistence: `database.update_trade_journal()` (`database.py:800`) —
`UPDATE closed_trades SET <provided cols> WHERE trade_id = ?`. `None` means "do
not touch this column". The Streamlit journal never edits `rating` (the column
exists and `update_trade_journal` accepts it, but no widget writes it).

Immutable in Streamlit: everything else on `closed_trades` (execution facts:
symbol, direction, volume, entry/exit price, commission, swap, gross/net
profit, entry/exit time, duration, trade_id, account_id).

---

## 2. React parity achieved

`/operations/journal` goes from read-only to **controlled in-place editing** of
the same three fields.

| Streamlit | React (Stage 12) |
| :-- | :-- |
| Select trade from dropdown | Per-row **Edit** button in the journal table |
| Setup category selectbox (10 presets) | Text input + `<datalist>` of the same 10 presets (free text allowed, matching `CUSTOM SETUP`) |
| Notes text area | Notes `<textarea>` |
| Screenshot upload **or** URL paste | Chart-snapshot **URL** text input (paste a link; existing `data:` URIs are shown/kept) |
| "Remove Screenshot" button | Clear the URL field → saves `""` |
| SAVE → full `st.rerun()` | Save → single `PATCH` → response spliced into the cached list (no refetch) |
| — | Explicit **Cancel**; **Saving…** state; inline API/validation error; Save disabled until a field actually changes; duplicate-submit guarded |

**Intentionally not ported:** in-browser file→base64 upload (the *field* is
editable via URL; base64 paste also works). Documented as a deferred item (§8).

---

## 3. API contract

### `PATCH /api/operations/journal/{trade_id}`

**Path param:** `trade_id` — 1–128 chars, must exist in `closed_trades`.

**Request body** (`JournalUpdateRequest`, `extra="forbid"`):

| Field | Type | Rules |
| :-- | :-- | :-- |
| `setup_tag` | `string?` | ≤ 120 chars; trimmed server-side |
| `notes` | `string?` | ≤ 20 000 chars; preserved verbatim |
| `chart_snapshot_url` | `string?` | ≤ 3 000 000 chars (accepts `data:` URIs); trimmed |

- At least one field must be present and non-null → else `422`.
- Any field **not** in the table above → `422` (`extra_forbidden`).
- `""` is a valid value and **clears** that column.
- Fields omitted from the body are left untouched.

**Responses:**

| Status | When |
| :-- | :-- |
| `200` | `JournalUpdateResponse` — `{ entry, updated_fields, writable: true, source: "closed_trades", live_broker_transmission: "BLOCKED", timestamp }`. `entry` is the **re-read** authoritative `JournalTradeItem`. |
| `404` | `trade_id` not in `closed_trades` |
| `422` | empty / all-null body, unknown field, or field too long |
| `405` | `POST` / `PUT` / `DELETE` on `/journal` or `/journal/{id}` (collection stays read-only; only `PATCH /{id}` mutates) |

`GET /api/operations/journal` is unchanged except `writable` is now `true`; the
`closed_trades` read cache is invalidated on every successful `PATCH` so the
next `GET` reflects the edit.

CORS `allow_methods` gains `PATCH` (dev uses the Vite proxy, so same-origin; the
entry matters for any future cross-origin hosted build).

---

## 4. Editable vs immutable fields

| Editable (annotations) | Immutable (execution / trade facts) |
| :-- | :-- |
| `setup_tag` | `trade_id`, `account_id` |
| `notes` | `symbol`, `direction`, `volume` |
| `chart_snapshot_url` | `entry_price`, `exit_price` |
| | `commission`, `swap`, `gross_profit`, `net_profit` |
| | `entry_time`, `exit_time`, `duration_minutes` |
| | `rating` (column exists; never edited by Streamlit either) |

Immutability is enforced structurally: `extra="forbid"` rejects any non-editable
key at the schema boundary, and the handler only ever forwards the three
whitelisted kwargs to `database.update_trade_journal`.

---

## 5. Persistence path

```
React JournalEditor
  → PATCH /api/operations/journal/{trade_id}   (frontend/src/api/operations.ts → apiPatch)
  → api/routers/operations.py :: patch_journal
      → _fetch_journal_row(trade_id)           (existence check → 404)
      → database.update_trade_journal(trade_id, **{editable subset})   ← canonical writer, unchanged
      → database.invalidate_db_cache("closed_trades")
      → _fetch_journal_row(trade_id) → _journal_item(...)              ← authoritative re-read
  → JournalUpdateResponse.entry
  → useJournal().applyEntry(entry)             (splice into module cache + state; no refetch)
```

No new SQL, no new table, no new engine. `_journal_item()` is the serializer
extracted from `get_journal()` so the `GET` list and the `PATCH` response are
byte-identical for the same row.

---

## 6. Safety verification

The endpoint is journal-only. It does not import or call `execution_pipeline`,
`broker_adapter`, order submission, the risk gateway, or any safety barrier.

| Check | Result |
| :-- | :-- |
| `execution_pipeline` / broker / order / risk-gateway / safety-barrier files touched | **none** (`git diff --stat` confirms) |
| `automation_enabled` after an edit | `false` (unchanged) |
| `live_broker_transmission` after an edit | `BLOCKED` (unchanged) |
| `execution_orders` row count / `mode_counts` after an edit | unchanged (`test_edit_does_not_write_execution_orders`) |
| `open_positions` after an edit | unchanged (`test_edit_does_not_change_safety_state`) |
| React Journal page — execution controls (buy/sell/execute/transmit/…) | **0** (browser scan) |
| React Journal page — non-safe requests other than the intended `PATCH` | **none** (browser network scan) |

---

## 7. Tests & validation

**Backend — `tests/test_stage12_journal_edit.py`** (24 cases incl. parametrized):
successful update returns authoritative record · partial update touches only
named fields · unknown trade → 404 · empty body → 422 · all-null body → 422 ·
oversized `setup_tag` → 422 · every immutable field rejected as unknown (10×) ·
immutable columns unchanged after edit · persisted value round-trips via direct
DB read · subsequent `GET` reflects the update · edit does not change safety
state · edit does not write `execution_orders` · collection path still 405s
POST/DELETE · clearing a field with `""`.

**Existing:** `tests/test_stage11_operations_adapter.py` updated for
`writable: true`.

| Gate | Result |
| :-- | :-- |
| Full suite `pytest tests/ -p no:randomly` | **921 passed, 2 skipped, 0 failed** (was 898/2/0; +23 new) |
| `test_api_parity_stage2/3`, `test_execution_safety`, `test_phase62_safety`, `test_forex_position_sizing`, `test_paper_execution` | 58 passed |
| `npx tsc -b` | clean |
| `npm run build` | clean — 142 modules, 436.50 kB JS / 120.47 kB gzip |
| React smoke — `/operations/journal` load | h1 "Trade Journal", 40 rows, 40 Edit buttons, no body overflow, 0 console errors, 0 exceptions |
| React smoke — edit → save | `PATCH …/journal/{id}` → `200`, editor closes, new note visible in cell, no order/execute/POST/PUT/DELETE request |
| React smoke — `/operations`, `/operations/audit`, `/operations/system` | load clean, 0 console errors (no regression) |

No frontend unit-test infra exists in `frontend/` (no vitest / testing-library);
covered by the CDP browser smoke instead.

---

## 8. Remaining migration gaps / deferred

- **File-upload screenshots** — Streamlit converts an uploaded image to a
  `data:` base64 URI. React exposes the `chart_snapshot_url` field as a URL
  paste (and renders/keeps existing `data:` URIs). A drag-and-drop uploader is
  deferred.
- **`rating`** — column and `update_trade_journal` support it, but neither the
  Streamlit journal nor this stage edits it. Left immutable to preserve
  Streamlit parity; add later if the product wants a star-rating control.
- **Journal creation / deletion** — no path in Streamlit either; rows come from
  the sync daemons. Not in scope.
- **Next migration units (unchanged from §11 of the retirement eval):**
  `GET/POST/DELETE /api/alerts` + React Price Alerts, then `GET /api/analytics/*`
  + React Analytics, then Daily Command Center / Research Lab / AI Assistant /
  paper execution (each a separate stage, the last only with explicit
  execution-scope authorization).
- **Pre-existing latent bug (out of scope):** `api/routers/positions.py:34`
  `float(pos.get("tp", 0.0))` raises `TypeError` on a NULL `tp`; only reproduces
  under randomized test ordering. Not touched here.

---

## 9. Files changed

| File | Change |
| :-- | :-- |
| `api/schemas.py` | `+JournalUpdateRequest` (`extra="forbid"`, ≥1-field validator), `+JournalUpdateResponse`, `+_JOURNAL_EDITABLE_FIELDS`; `JournalResponse.writable` default → `True` |
| `api/routers/operations.py` | `+PATCH /journal/{trade_id}`; extracted `_journal_item()` / `_fetch_journal_row()` / `_placeholder()` helpers; `get_journal` → `writable=True` |
| `api/main.py` | CORS `allow_methods` `+PATCH` |
| `frontend/src/api/client.ts` | `+apiPatch<T>()` |
| `frontend/src/api/operations.ts` | `+patchJournalEntry()` |
| `frontend/src/types/operations.ts` | `+JournalUpdateRequest`, `+JournalUpdateResponse` |
| `frontend/src/lib/useOperations.ts` | `OpsResource.setLocal`; `useJournal` → `JournalResource` with `applyEntry` |
| `frontend/src/components/operations/JournalView.tsx` | `+JournalEditor`; per-row Edit; editable annotations; chart link; copy updated |
| `frontend/src/pages/JournalPage.tsx` | wire `applyEntry`; copy updated |
| `tests/test_stage11_operations_adapter.py` | `writable` assertion `False` → `True` |
| `tests/test_stage12_journal_edit.py` | **new** — 24 cases |
| `docs/STAGE_12_JOURNAL_EDIT_MIGRATION.md` | **new** — this document |
| `PROJECT_STATE.md` | `+§9.3`; header → Session 42 |
