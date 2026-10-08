# Journal links (TradingView and other links on trades and notes)

Shipped 2026-10-08.

## What it does

You can attach **web links** to:

- **Notes & ideas** (Journal → bottom of the page). The "Links" section in the
  new-note form and in edit mode starts with a TradingView field. Saved links
  show as chips under the note; a TradingView link gets a small **TV** mark.
- **Trades** (Journal → Cards view). Under each trade: "+ add a link
  (TradingView idea, news, video…)". Links **autosave** like the rest of the
  card. This sits alongside the existing single **chart link**
  (`chart_snapshot_url`), which still renders a TradingView *snapshot image*
  inline; the new links are for everything else (the idea page, a news
  article, a replay video…).

They also appear in:

- the Journal **Table** view, as chips in the notes column;
- the Analytics calendar, as a 🔗 count;
- the Overview day panel (click a calendar square), as a "Chart"/"Link"
  shortcut.

Up to **10 links** per trade or note, each with an optional name (up to 80
characters). Without a name, the chip shows the site ("TradingView",
"Forex Factory", "YouTube"…).

## Rules

- Only **web addresses** (`http://` / `https://`). A pasted
  `tradingview.com/x/…` without `https://` is completed automatically.
  Anything else (`javascript:`, `data:`, `ftp:`…) is refused both in the
  browser and by the API (422). That keeps a saved link from ever running
  script when clicked.
- Links open in a new tab with `rel="noopener noreferrer"`.
- A half-typed link on a trade card isn't saved until it's a real address. A
  note with a bad link shows an explanation instead of saving.

## How it's stored

| Piece | Where |
|---|---|
| Table | `journal_links (id, trade_id, url, label, position, created_at, user_id)`. `trade_id` is the owner: a closed-trade id **or** a journal-entry id, the same convention as `journal_screenshots`. |
| Creation | on first use (`database._ensure_journal_links`), and in `init_db()`. The API process doesn't run `init_db()` at boot, so this is what creates it in production. No Alembic migration is needed. |
| DB helpers | `database.replace_journal_links(owner, links)`, `list_journal_links(owner)`, `journal_links_by_owner()` (one query for list views). All are tenant-scoped. |
| Cleanup | deleting a note (`delete_journal_entry`) or a hand-logged trade (`delete_manual_trade`) deletes its links. |
| Sync safety | links are **not** columns on `closed_trades`, so a broker re-sync can't overwrite them. |

## API

The list is always **replaced as a whole** (send `[]` to remove all):

- `PATCH /api/operations/journal/{trade_id}` → `{"links": [{"url", "label"?}]}`
  (can be the only field). The response `entry.links` is the saved list.
- `POST /api/operations/journal/entries` → `links` optional on create.
- `PATCH /api/operations/journal/entries/{id}` → `links` (can be the only
  field).
- `GET /api/operations/journal`, `GET /api/operations/journal/entries` and the
  analytics day-trades endpoint include `links` on every item.

Schema: `JournalLink` in `api/schemas.py` (`MAX_JOURNAL_LINKS = 10`).
Frontend: `frontend/src/components/journal/JournalLinks.tsx`
(`JournalLinkChips`, `JournalLinksEditor`, `cleanLinks`, `normalizeUrl`).
Tests: `tests/test_journal_links.py`.

## Fixed along the way

- **Tenant scoping:** `_fetch_journal_row` (the single-trade read behind
  `PATCH /journal/{trade_id}` and the manual-trade endpoints) now filters by
  the signed-in user. Before, a PATCH naming another account's trade id
  returned that trade's details in the response (the write itself was already
  scoped). Covered by `test_another_accounts_trade_looks_missing`.
- **Tests never touch production:** `tests/conftest.py` now sets
  `USE_LOCAL_SQLITE=1` before anything imports. Several test modules call
  `database.init_db()` at import time, before pytest sets
  `PYTEST_CURRENT_TEST`, which used to run schema DDL against the
  `DATABASE_URL` in `.env` (the live database).

## Not included (yet)

- **Open positions** (Positions page and the Journal's open-trades strip)
  keep only their single chart link. Adding lists there needs the links
  re-keyed to the closed trade when the position closes, as screenshots are
  in `save_open_positions`.
- The **Android app** doesn't show links yet. It ignores the new field, so
  nothing breaks.
