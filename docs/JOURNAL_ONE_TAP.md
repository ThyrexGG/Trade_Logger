# Journal: one tap per trade

Shipped 2026-10-10.

## Why
Tagging each trade with a free-text tag, stars and two long dropdowns was too much, so trades went untagged (200 trades in the last month, none tagged).
The research (see `docs/PHASE_131_132_STRUCTURE_ENTRY.md` onward) says any edge is in the trader's own judgement, which can only be measured if trades are labelled.
So the label is now one tap.

## What it does
Under each trade in Journal -> Cards: **How was this trade?**  [ By my rules ]  [ Bent my rules ]  [ Rushed / off-plan ].
Tap again to clear. It autosaves like the rest of the card.
- It is stored as the trade's existing **setup tag** (`By my rules`, `Bent my rules`, `Rushed`), so the existing tag record ("which kind of trade pays") works with no backend change.
- Everything else (chart link, links, stop placement, how it ended, your own tag, stars) moved behind a **More details** toggle. It opens by itself only when something in it is already filled in.
- The note box is optional and two lines tall.
- Page guide text for the journal updated.

Files: `frontend/src/components/journal/JournalFeed.tsx`, `reviewOptions.ts` (`QUICK_TAGS`), `frontend/src/lib/pageGuides.ts`.
Verified in a browser (dark + light, 1360px + 390px, isolated sqlite): the tap saves, survives a reload, clears, no horizontal scroll.
