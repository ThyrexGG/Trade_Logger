# TradeLogger Mobile App (React Native / Expo) — Step-by-Step Plan

Companion to `WEB_MOBILE_PLATFORM_PLAN.md` (W5 covered the PWA; this is the
native app). Decided 2026-09-19.

## Approach

- **Expo (React Native + TypeScript)** in a new `mobile/` folder. Web (`frontend/`),
  desktop (`desktop/`) and the API are untouched.
- **A companion, not a port.** The phone app covers what gets used on a phone:
  login, open positions, the trade journal (notes / tag / rating / screenshots),
  and push alerts. The heavy analysis pages (Analytics, Killzone Scanner, Chart
  Analyzer, research) stay on web + desktop.
- **No backend rewrite.** Verified in the code (2026-09-19):
  - `POST /api/auth/login` already returns `token` in the JSON body and every
    `/api/*` route already accepts `Authorization: Bearer <token>`
    (`api/main.py::_auth_gate`, `api/routers/auth.py`). So the app stores the token
    in the phone's secure storage — the cross-site-cookie problem that breaks
    native WebViews never applies.
  - Endpoints the app uses: `GET /api/positions`, `PATCH /api/positions/{id}`,
    `GET /api/operations/journal`, `PATCH /api/operations/journal/{trade_id}`,
    `GET|POST /api/operations/journal/{id}/screenshots`,
    `GET /api/operations/journal/screenshot/{id}`, `POST /api/system/sync/run`.
  - Only genuinely new backend work: push-notification device registration +
    sending (step M7).
- **Types are copied, not shared.** Metro (React Native's bundler) and Vite don't
  share a workspace cleanly; the handful of response types the app needs are
  re-declared in `mobile/src/types/`. If the API shape changes, update both.
- **API base URL:** `https://tradelogger-api-sg.onrender.com` (the Singapore
  Starter service), configurable in `mobile/src/config.ts`.

## How each step works

Every step ends with a **CHECKPOINT**: I stop, tell you exactly what to do on your
phone, and list what you should see. If it passes, say "next". If not, tell me what
you saw and I fix it before moving on. Every step is committed and pushed.

Testing tool for M1–M6: **Expo Go** (free app from the App Store / Play Store).
Your phone and PC must be on the same Wi-Fi (or use tunnel mode if not).

---

## M1 — Scaffold + "hello API"
**Build:** Expo TypeScript app in `mobile/`, dark gold/black/gray theme matching the
web brand, one screen that calls `GET /api/health` and shows a green/red API
status pill (same idea as the web pill).
**Checkpoint M1:** install Expo Go → run `npm start` in `mobile/` → scan the QR code
→ you see the TradeLogger screen and a green **"API connected"** pill. Turn Wi-Fi
off on the phone briefly → pill goes red, back on → green.

## M2 — Login (token auth)
**Build:** email + password login screen → `POST /api/auth/login` → token stored in
`expo-secure-store` → every request sends `Authorization: Bearer`. Auto-login on
app start (`GET /api/auth/me`), logout button, 401 → back to login. Wrong password
shows the server's message.
**Checkpoint M2:** log in with your real account → see a "Signed in as <email>"
screen. Fully close Expo Go and reopen → still signed in. Log out → back to login.
Try a wrong password → clear error.

## M3 — Open positions
**Build:** Positions tab: your open trades as cards (symbol, BUY/SELL, volume,
entry, current, floating P&L in green/red), total floating P&L on top, refresh
every 45 s + pull-to-refresh, a **Sync now** button that calls the sync endpoint
then reloads.
**Checkpoint M3:** with a trade open on Capital.com, the phone shows the same
positions as the web app with the same P&L. Pull down to refresh. Tap Sync now.

## M4 — Journal list + filters
**Build:** Journal tab: closed trades newest-first, summary bar (trades / wins /
losses / net P&L), date filter chips **Today · This week · This month · All time**
(default This week, same rules as the web), account filter when there's more than
one. Open trades appear on top under "Open now". Tap a row → trade detail screen
(read-only for now).
**Checkpoint M4:** numbers match the web Journal for the same filter. Switching
filters updates the summary. Tapping a trade opens its detail.

## M5 — Journal editing (closed + open trades)
**Build:** on the detail screen: notes, setup tag, chart-link, star rating —
autosaves (debounced, like the web) via `PATCH`. Works identically for an open
trade (`PATCH /api/positions/{id}`), carrying over when it closes.
**Checkpoint M5:** edit notes + rating on the phone → open the web Journal → same
text/stars are there. Edit on web → pull to refresh on phone → appears. Do it on
an open trade too.

## M6 — Screenshots
**Build:** "Add screenshot" → choose from gallery or take a photo → upload →
big un-cropped previews on the detail screen (open trades too), tap for
full-screen (pinch-zoom on iPhone; Android zoom comes in M8), Delete from the viewer. Images are downscaled before upload (API limit is 4 MB).
**Checkpoint M6:** add a photo on the phone → shows on the web Journal for that
trade. Add on web → shows on phone. Delete works.

## M7 — Push notifications
**Build:** backend: `push_devices` table + `POST /api/push/register`; the sync
cycle sends a push via Expo's push service when a position opens or closes
("US500 closed +$32.10"). App: ask permission, register the device token, tapping
a notification opens that trade.
**Needs (verify at this step):** a *development build* instead of Expo Go on
Android (Expo Go no longer supports remote push there); on iPhone, push requires a
paid Apple Developer account ($99/yr). I'll confirm exactly what your phone needs
before starting and we decide together.
**Checkpoint M7:** close the app completely, open + close a demo trade → a
notification arrives within ~2 minutes; tapping it opens the trade.

## M8 — Polish
**Build:** app icon + splash from the existing brand assets, biometric lock
(Face ID / fingerprint) option, empty/error/offline states, safe areas, haptics on
save, "last updated" timestamps.
**Checkpoint M8:** a full pass on the phone — nothing cropped, nothing stuck
loading, biometric lock works, offline shows a clear message not a blank screen.

## M9 — Installable app
**Build:** EAS Build → Android `.apk` you install directly (free); iPhone via
TestFlight (needs the Apple account). Optional: Play Store / App Store listing.
**Checkpoint M9:** the app is on your home screen with its own icon, opens without
Expo Go or the PC running, and every earlier checkpoint still works.

---

## Cost & risk summary
| Item | Cost |
|---|---|
| Expo, Expo Go, EAS free tier, Android APK | Free |
| Google Play listing (optional) | $25 one-time |
| Apple Developer (TestFlight / App Store / iPhone push) | $99/yr |
| Extra Render cost | None — same API |

Risks: (1) Expo Go SDK version must match the project's — we use the current
store version. (2) Push on iOS/Android has the platform limits above. (3) Two UIs
to maintain: new web features do not automatically appear in the app.

## Progress log
- M1 built 2026-09-19 (Expo SDK 57, RN 0.86; typecheck + Metro bundle + expo-doctor 21/21 pass) — **awaiting phone checkpoint**
- M2 built 2026-09-19 (login + secure token storage; typecheck + Android/iOS bundle pass; live 401 messages verified) — **awaiting phone checkpoint**
- M3 built 2026-09-19 (Positions tab, 45s poll, pull-to-refresh, Sync now, bottom tabs; bundles on both platforms; doctor 21/21) — **awaiting phone checkpoint**
- M4 built 2026-09-19 (Journal tab: date + account filters, summary, Open now, trade detail; filter logic unit-tested; bundles OK) — **awaiting phone checkpoint**
- M5 built 2026-09-19 (journal editing for closed + open trades: notes, tag, rating, chart link; debounced autosave; root stack navigation; bundles OK) — **awaiting phone checkpoint**
- M6 built 2026-09-19 (camera/library upload, auto-downscale to <=1600px JPEG, big gallery, full-screen viewer, delete; **also fixed a backend bug: uploading a screenshot to a still-open position returned 404** — affected the web too, commit 0aca67e; bundles OK) — **awaiting phone checkpoint**
- M8 built 2026-09-19, ahead of M7 (icon + adaptive icon + splash from the brand candle logo, optional Face ID / fingerprint app lock that ignores camera/picker trips, connection banner, save haptics; bundles OK) — **awaiting phone checkpoint**. Android pinch-zoom in the screenshot viewer is not done (iPhone zoom works).
- M9 prep: mobile/eas.json written (Android APK profile). Needs the owner to log in to a free Expo account — not runnable unattended.
- M7 built 2026-09-19 for **Android** (user is on Android): server-side `trade_events` log + `push_devices` (`trade_notify.py`, `api/routers/push.py`, 17 tests), Expo push on new open/closed trades, app registers token, Account → Trade alerts switch + "Send a test notification", tap opens the trade. **Needs the installed APK (not Expo Go) + Firebase — see `docs/MOBILE_ANDROID_BUILD.md`** — awaiting owner setup.
- Desktop (built alongside): fixed stale Oregon API URLs in `desktop/main.js` + `preload.js`, added native trade notifications from the same event log, "Start with Windows", v1.1.0 installer.
- Parity pass (2026-09-19): `npm run parity` runs the website's own Journal filter code against the phone's over 672 cases in 7 time zones (+ chart-link resolver) — identical. Added to the phone: chart-link image preview, "your record on this tag" line, Ideas & reviews (list/create/edit/delete + screenshots), Android pinch/double-tap zoom, Auto-sync switch. `npm run preflight` checks the Android build prerequisites.
- **Finding:** the account's server auto-sync is OFF (no `sync_auto_enabled` row), so trade alerts (phone + desktop) only fire after a sync. Switch added to the phone Account screen; the website's Positions page has the same toggle.
- Full test list for the owner: `docs/TEST_CHECKLIST.md`.
- [ ] M9 build itself (needs the owner's Expo login + Firebase file)
- **Phase 2 (owner-approved 2026-09-19)** — bring more of the website to the phone. In: Analytics (+ calendar), Price Alerts, Manual trade entry, Risk Gateway, AI Assistant, Killzone Scanner. Owner first left out Challenge Tracker and Chart Analyzer, then asked for them on 2026-09-20 (M20, M21); not planned: Command Center, Market, Research pages, System/Connections/Partners. Tabs are now Positions · Journal · Analytics · More (Account moved under More).
  - [x] M10 Analytics: filters (account, range), starting balance that saves, 8 stat tiles, month calendar with day drill-down to trades, balance curve, period returns, P&L by symbol/tag, long vs short. (The website's radar "performance index" is presentation-only and left out.)
  - [x] M11 Price Alerts: create / list / delete on the phone (More → Price alerts); a triggered alert also becomes a push + desktop notification (new `alert` event kind in `trade_notify`, 2 tests).
    - **Fixed 2026-09-20 — alerts could never fire before.** The check read prices only from MetaTrader 5, which is switched off (terminals uninstalled), so no alert ever triggered on the website, phone or PC. Now `auto_sync.check_price_alerts` uses MT5 if enabled, else `market_data.get_verified_price` (FMP / Binance / Yahoo — never the placeholder default prices, which would have fired false alerts). The server sync loop also evaluates users with active alerts who have no broker connection or auto-sync off (`sync_service._check_alerts_for`); creating an alert starts that loop. A user's alert is only pushed to their own devices — Telegram/Discord/toast stay owner-only. 6 tests in `tests/test_price_alert_watch.py`.
    - **Caveats:** prices are public feeds (Yahoo gold/index futures can differ a few points from the broker's CFD price); checked ~every 2 minutes; the free Render server sleeps when idle, and alerts are not checked while it sleeps.
  - [x] M12 Manual trade entry (More → Log a trade): account, symbol, buy/sell, prices, profit/fees, native date+time pickers, tag, notes; saves through the same endpoint as the website and appears in Journal/Analytics.
  - [x] M13 Risk Gateway (More → Risk gateway): entry / stop / TPs / balance / risk % → server's position size, risk, margin, reward, R:R, warnings; remembers balance, risk % and symbol.
  - [x] M14 AI Assistant (More → AI assistant): same read-only chat as the website (Gemini on the server), suggestion prompts, replies with headings/bullets/bold, retry, daily-usage line, transcript kept on the phone (cleared on log out).
  - [x] M15 Killzone Scanner (More → Killzone scanner): symbol + entry timeframe, higher-timeframe bias ladder, draw on liquidity, candidate events with entry/stop/target/R:R and the 0-5 confluence checklist, unmitigated FVGs, auto-refresh every 5 min, and **Plan this** which pre-fills a Trade-plan note. The live candle chart and the Markdown export were added afterwards (see M16).
  - [x] M16 Killzone chart + Markdown export (2026-09-20): candlestick chart in the Killzone scanner (`components/scanner/KillzoneChart.tsx`, react-native-svg) with the website's killzone boxes (New York clock, follows daylight saving), BSL/SSL, FVG edges + confirming-candle dots, previous day/week levels, S/M arrows per candidate, and the focused candidate's entry/stop/target ("Show on chart"); tap a candle for its prices; View/History chips; refuses to draw the offline placeholder candles. **Share scan as Markdown** uses the phone's share sheet. Pure helpers are in `src/scanner/chartLogic.ts` and unit-tested: `npm run test:chart`.
  - [x] M17 Today (2026-09-20): More → Today, the phone version of the website's Daily Command Center (session clock, today's P&L, account, open risk, alerts, market context, watchlist), refreshing every minute. The website's research-state section is left out. Contract tests added for `/api/market/candles` and `/api/command-center/overview`.
  - [x] M18 Fix / delete a hand-logged trade (2026-09-20): `PUT` and `DELETE /api/operations/journal/trades/{id}` (only `MANUAL_` trades of the signed-in user; broker-synced trades are refused with 409 because the next sync would bring them back; screenshots go with the trade). Phone: Journal → trade → "Logged by hand" card → Edit trade / Delete trade. Analytics now refreshes when you return to its tab. 5 tests in `tests/test_manual_trade_edit_delete.py`.
  - [x] M19 Loss limits (2026-09-20): per-account daily-loss limit ($) and drawdown limit (% below peak balance, needs the account's starting balance). `api/loss_limits.py` + `/api/loss-limits`; a notification (`risk` event kind -> phone push + desktop toast) at 80% and at 100%, once per level per day (daily) or per peak (drawdown). Checked after each sync cycle, after a hand-logged trade, and by the server's 2-minute watcher (also for users with no broker). Closed trades only. 10 tests in `tests/test_loss_limits.py`. Phone: More → Loss limits.
  - [x] M20 Challenge tracker on the phone (2026-09-20): More → Challenge tracker — the website's tracker (`/api/challenge/*`): set the rules, phase progress, drawdown / daily-loss budgets, profit days, mark phase passed, restart, stop tracking.
  - [x] M21 Chart analyzer on the phone (2026-09-20): More → Chart analyzer — screenshot (camera/library, downscaled) or TradingView link -> Gemini vision reading (entry/stop/target/R:R, 1-10 rating, pattern, confluences, caveats). "Size this trade" opens the Risk gateway pre-filled; "Save as note" pre-fills an Idea note. Screenshot is not attached to the note (the website can).
  - [x] M22 Broker connection on the phone (2026-09-20): More → Broker connection — list / test / sync / delete / add a Capital.com connection (`/api/connections`). Credentials are typed once, encrypted on the server, never sent back.
  - **Phase 2 complete (M10–M15) — all built, none run on a phone yet.** Next: owner test pass (docs/TEST_CHECKLIST.md A9–A14), then a new APK build to get these onto the installed app.
- **Emulator run (2026-09-19/20):** first time the app was actually executed. Android 35 emulator + Expo Go + a throwaway local API (sqlite, fake data, non-owner user so it can never reach the real broker). Bugs found and fixed: calendar rendered 6 columns not 7 (percentage widths), screenshot upload never worked (`Unsupported FormDataPart implementation` from Expo's fetch -> now XMLHttpRequest), Account screen had no Auto-sync switch (only its import was ever committed), empty profit read as 0, expo-notifications crashed Expo Go at startup, AI replies showed raw `---`/`*italic*`, Gemini 5xx retried server-side. Contract test `tests/test_mobile_api_contract.py` guards the API<->phone types. **A new APK build is needed to get these onto the installed app.**

