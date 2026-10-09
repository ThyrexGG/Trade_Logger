# Journal review fields (stop placement, exit reason)

Shipped 2026-10-09.

## Why

The NQ/ES research (Phases 101–115) found no mechanical edge in the TJR-style
setups. Whatever edge a trader has is in **which setups they take and how they
manage them**. These two answers per trade, together with "Skipped setup"
notes, let a journal be analysed later, e.g. "do my trades with the stop
beyond the sweep do better than ones with the stop beyond the 2nd low?" or
"how much do I give up by closing early?". Fixed choices, not free text, so
trades can be grouped by them.

## What it does

Journal → Cards view, under each trade's links, two dropdowns that **autosave**
like the rest of the card:

| Where was your stop? | How did the trade end? |
|---|---|
| Beyond the sweep high/low (`sweep`) | Hit my target (`target`) |
| Beyond the 2nd high/low (pullback) (`second`) | Took a partial, then closed the rest (`partial_runner`) |
| Beyond the gap (FVG) (`fvg`) | Stopped out (`stopped`) |
| Beyond another swing point (`structure`) | Stopped at breakeven (`breakeven`) |
| Fixed points / pips (`fixed`) | Closed early by hand (`cut_early`) |
| Other (`other`) | Out of time (end of my window) (`time`) |
| | Other (`other`) |

"Not answered" clears the answer.

## How it's stored

| Piece | Where |
|---|---|
| Table | `journal_review (trade_id, stop_placement, exit_reason, updated_at, user_id)`, primary key `(user_id, trade_id)`. A row exists only while at least one answer is set. |
| Creation | on first use (`database._ensure_journal_review`) and in `init_db()`, like `journal_links`. No migration needed. |
| DB helpers | `get_journal_review(trade)`, `update_journal_review(trade, stop_placement=, exit_reason=)` (`""` clears, omitted keeps), `journal_review_by_owner()`. All tenant-scoped. |
| Cleanup | deleting a hand-logged trade deletes its answers. |
| Sync safety | not columns on `closed_trades`, so a broker re-sync can't overwrite them. |

## API

- `PATCH /api/operations/journal/{trade_id}` accepts `stop_placement` and
  `exit_reason` (either can be the only field). Values outside the lists above
  are refused (422); `""` clears.
- `GET /api/operations/journal` and every journal-entry reply include both
  fields (`null` when unanswered).

Schema: `StopPlacement` / `ExitReason` in `api/schemas.py`. Frontend labels:
`frontend/src/components/journal/reviewOptions.ts`. Tests:
`tests/test_journal_review.py`.

## Not included (yet)

- Not editable from the Table view, the Analytics calendar editor or the
  Android app (they ignore the fields, nothing breaks).
- No report grouping by them yet. That's the planned analysis once ~50 trades
  are answered.
