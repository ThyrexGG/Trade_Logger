# Handoff — start here

*Last updated 2026-10-10. Read this first in a new session; it is the shortest path to being useful. The older `PROJECT_STATE.md` (to Phase 100 + web/mobile) and `CURRENT_STATE.md` (to Phase 74) are history, not the current picture.*

## What this project is

Trade Logger: a personal trading journal, analytics and research platform for MT5 and Capital.com trades. It is **read-only toward brokers** (never places, changes or cancels an order; live automation is disabled in code). Beginner traders use it, so UI copy is plain English: summary first, details behind a toggle.

| Piece | Where | Notes |
| :-- | :-- | :-- |
| Backend | `api/` (FastAPI, `api.main:app`) | Postgres (Neon) via `DATABASE_URL`, SQLite fallback |
| Web app | `frontend/` (React 19, Vite, Tailwind v4) | Design system "Precision" (navy + ice cyan), see `docs/DESIGN_SYSTEM.md` |
| Phone app | `mobile/` (Expo SDK 57, Android) | Same Precision tokens in `mobile/src/theme.ts`; build steps in `docs/MOBILE_ANDROID_BUILD.md` |
| Desktop | `desktop/` (Electron shell around the web app) | |
| MT5 push agent | `agent/` | Sends trades from the user's PC to the cloud |
| TradingView scripts | `tradingview/` | Pine scripts, see `tradingview/README.md` |
| Research | root `phaseNNN_*.py` + `docs/PHASE_NNN_*.md` | Phases 62–135 |

## Hosting and deploy

- Pushing to `main` auto-deploys both: **Cloudflare Pages** (frontend) and **Render** (backend). Pushing is production, so confirm with the user first.
- Phone APK is **not** auto-deployed: build with EAS (see below) and install with adb.
- `docs/DEPLOY.md` has the full setup.

## Rules that bite

1. **The repo `.env` `DATABASE_URL` is the live production Neon database.** Never run tests or scripts against it. Use a temporary SQLite file or a fake tenant. Do not read or print `.env`.
2. Never put the user's personal email in public pages.
3. Every shipped change gets its `docs/` update in the same commit.
4. Verify UI in a real browser (both themes, phone width) before pushing. Recipe: isolated SQLite backend, Vite with `VITE_AUTH_MODE=local`, Playwright with the cached chromium. A passing build has missed layout bugs before.
5. Commit messages end with the Co-Authored-By line given in the session's system reminder.
6. MT5 is read-only; do not re-enable any order-placing path.
7. Be honest about research results. Do not tune a rule until it looks good (that is curve-fitting); say plainly when there is no edge.

## What the research concluded (so you do not redo it)

- **Only one usable edge exists:** delta-neutral crypto funding carry, about 2% a year over cash (Phases 94–99). Weekly forward check: `python -m phase98_carry_forward_evidence --refresh`.
- **Intraday NQ/ES/FX (Phases 101–135): no edge distinguishable from zero.** Covered: TJR-style sweep and MSS, IFVG, follow-the-sweep, partials, breakeven, structure and internal stops, re-entries, MSS+FVG entries, window entries, timeframes 1/5/15m, 9 global session opens. Full detail in each `docs/PHASE_1xx_*.md`; the year-by-year table is in `docs/PHASE_108_MY_PATTERN.md`.
- **Gap fade** (big overnight gap on NQ/ES, enter 09:45, target yesterday's close, exit 12:00) is the best-looking idea but only positive in 2025–26 and regime-dependent. Management changes (partial, BE) change win rate, not average R. It is a watch-list candidate, not a proven strategy.
- Costs matter: tight stops lose about 0.2R to spread and slippage. FundedNext MT5 server clock is NY+7 (NY+6 before 2024-07-28); history cap was lifted to Unlimited.
- What would actually help next: **the user's own tagged trades** (see Journal) and a longer forward record. Do not start another strategy hunt unless they ask.

## TradingView scripts (`tradingview/`)

- `big_gap_fade_strategy.pine` — **main strategy, the simple rule** (no partials, BE or re-entries). The user explicitly asked to revert to this.
- `big_gap_fade_strategy_v1.pine` — exact file behind the +17.6% Jul–Oct 2026 run.
- `big_gap_fade_strategy_experimental.pine` — everything we tried (MSS/FVG entries, ladders, internal stops, re-entry, BE). Kept as options only.
- `big_gap_fade.pine` (indicator), `mss_entry.pine`, `tjr_sweep_checklist.pine`, `killzone_*.pine`.
- Pine gotchas learned: set `margin_long/short=0` or the tester shows no trades; round qty to the symbol step; Strategy Tester shows no costs by default; compare variants on the same market and window.

## Journal (one tap)

- Each trade card has one question: **By my rules / Bent my rules / Rushed**, stored in `setup_tag`. Everything else (stop placement, how it ended, stars, links, own tag) is behind "More details". Never add another required field. See `docs/JOURNAL_ONE_TAP.md`.
- Same row on the phone (`mobile/src/components/AnnotationEditor.tsx`). Constants: `QUICK_TAGS` in `frontend/src/components/journal/reviewOptions.ts`.
- Not yet checked on the phone: opening a trade card to see the one-tap row.
- Journal state at last check (live phone data, 2026-10-10): 210 trades, net −$143.60. USDJPY was the main leak; NY-open Nasdaq trades were the profitable ones. Zero tags until the one-tap change, so the next useful step is for the user to tag about 50 trades, then compare their picks with mechanical rules.

## Phone app

- Build: from inside `mobile/` run `eas build --platform android --profile preview --no-wait`, then poll `eas build:view <id> --json` for the APK URL. Piping a background `eas build` fails with "Run this command inside a project directory".
- Install: `adb install -r <apk>`. adb lives in `%LOCALAPPDATA%\Android\Sdk\platform-tools` (not on PATH). Phone is a Xiaomi 24090RA29G.
- **Before tapping anything, check `dumpsys window | grep mCurrentFocus` is `site.tradelogger.mobile`.** The user uses the phone while it is plugged in; find labels with uiautomator dump, never blind-tap coordinates.
- Latest: build 5 (EAS 34393082) with the Precision theme, then a Journal/Positions overlap fix (commit 56bb5f9, rebuilt and installed). Free EAS builds are limited each month (about 11 left in October).
- Not done: Geist font on the phone (needs per-weight families on every style), light theme.

## Pending items for the user (not code)

SMTP, Sentry, legal inbox, `TL_MAX_USERS`, a `/code-review ultra` pass, then `TL_SIGNUP_OPEN` before public launch (see `docs/DEPLOY.md`). Remind them until done.

## Where things are documented

`README.md` (overview) · `docs/DESIGN_SYSTEM.md` (UI) · `docs/DEPLOY.md` · `docs/MOBILE_ANDROID_BUILD.md` · `docs/JOURNAL_*.md` · `docs/PHASE_*.md` (research, one per phase) · `docs/PROJECT_STATE.md` (long history to Phase 100 and the web/mobile platform, sections 1–21) · `tradingview/README.md`.

Claude Code also keeps private memory notes outside the repo (per user, per machine). They duplicate the key points above, so the repo copy is the one that survives a new machine.
