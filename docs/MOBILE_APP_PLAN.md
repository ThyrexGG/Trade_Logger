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
thumbnails on the detail screen, tap for full-screen (un-cropped, pinch-zoom),
long-press to delete. Images are downscaled before upload (API limit is 4 MB).
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
- [ ] M3 · [ ] M4 · [ ] M5 · [ ] M6 · [ ] M7 · [ ] M8 · [ ] M9
