# TradeLogger — things to check (phone, desktop, web)

Tick each box as you go. If something fails, note the **step number + what you saw**
(a screenshot is perfect) and send it to Claude. Nothing here has been run on a real
phone yet — everything was verified by type-checks, bundling, and automated tests only.

Legend: ✅ = should just work · ⚠️ = newest / least certain, look closely

> ⚠️ **Trade alerts (phone AND desktop) only work while the server's auto-sync is ON.**
> I checked your account: it is currently **OFF** (default). Turn it on once — in the phone's
> **Account → Auto-sync trades**, or on the website's Positions page (Auto toggle). With it off, alerts
> only appear after you tap **Sync now** or open the website.

---

## A. Phone app in Expo Go (no setup beyond Expo Go)

Start it: on the PC, `cd C:\Users\Asus\Desktop\Trade_Logger\mobile` then `npm start`, scan the QR
in Expo Go. Same Wi-Fi. If it hangs: `npm start -- --tunnel`.

**A1 · Start & connection (M1)**
- [ ] Gold **TradeLogger** login screen appears (dark, gold accents)
- [ ] After login, Account tab shows a green **"API connected · NN ms"**
- [ ] Turn phone Wi-Fi/data **off** → within ~15 s a red banner "Can't reach the server…" shows on Positions/Journal; turn back on, tap it → gone

**A2 · Login (M2)**
- [ ] Wrong password → red message "Wrong email or password."
- [ ] Right password → lands on the tabs (Positions · Journal · Account)
- [ ] Fully close Expo Go, reopen → **still signed in**
- [ ] Account → **Log out** → back to login

**A3 · Positions (M3)**
- [ ] With a trade open on Capital.com: same symbols, sizes and P&L as the website
- [ ] Total floating P&L at the top matches the website
- [ ] Pull down to refresh works; **Sync now** shows a spinner then updates
- [ ] With no open trades: friendly "No open positions" message

**A4 · Journal list (M4)**
- [ ] Chips **Today · This week · This month · All time** (default: This week)
- [ ] Trades / Wins / Losses / Net P&L match the website's Journal for the **same chip**
- [ ] Your open trades appear under **Open now**
- [ ] The chip you pick is remembered after closing the app
- [ ] Yesterday's late-evening trade lands in the right day (times shown in *your* phone's time)

**A5 · Edit a trade (M5)** — open any closed trade
- [ ] Set a star rating, type a setup tag, write notes → "Saving…" then "✓ Saved" after ~1 s
- [ ] Open the **website** Journal → same rating, tag, notes
- [ ] Edit on the website → pull to refresh on the phone → it appears
- [ ] Tag suggestion chips appear under the tag box; tapping one fills it
- [ ] ⚠️ Under the tag you see **"Your record on 'X': n trades · win % · avg"** (or "No prior trades on 'X'")
- [ ] Same editing on an **open** trade (tap it in Positions or Journal); when it closes the notes are still there

**A6 · Chart link (new)** ⚠️
- [ ] Paste a TradingView share link (`https://www.tradingview.com/x/…`) in **Chart link** → a big **uncropped** chart image appears under the box
- [ ] Tap the image → opens the link in your browser
- [ ] A non-image link shows just "Open link ↗"

**A7 · Screenshots (M6)**
- [ ] **＋ Add → Take photo** works (asks for camera permission the first time)
- [ ] **＋ Add → Choose from library** works
- [ ] Image shows **big and fully visible** (nothing cropped)
- [ ] The same screenshot shows on the **website** for that trade (and vice-versa)
- [ ] ⚠️ Tap image → full screen. **Pinch to zoom**, drag to pan, **double-tap** to zoom in/out (Android uses our own zoom)
- [ ] Delete from the full-screen view removes it (also on the website)
- [ ] Works on an **open** trade too (this used to fail — fixed)

**A7b · Ideas & reviews (new)** ⚠️ — Journal tab → **Ideas**
- [ ] List of your notes (same ones as the website's "Ideas & reviews")
- [ ] **＋ New note** → pick Idea/Review/Observation/Trade plan, fill in, **Save note**
- [ ] After saving it reopens with a Screenshots section; add a photo
- [ ] Edit → **Save changes** → "✓ Saved"; the website shows the change
- [ ] **Delete note** asks to confirm, then removes it

**A8 · Polish (M8)**
- [ ] New gold candle-chart icon/splash (icon shows on the *installed* app; Expo Go shows Expo's)
- [ ] Account → **Lock the app** on → put the app in the background ≥ 30 s → returning asks for fingerprint/PIN
- [ ] Taking a photo (camera) does **not** trigger the lock when you come back
- [ ] Saving edits gives a small vibration

---

## B. Installed Android app + trade alerts (needs your setup first)

Guide: `docs/MOBILE_ANDROID_BUILD.md`. Order: Expo account → `npx eas-cli login` → `npx eas-cli init` →
Firebase project → `google-services.json` in `mobile/` → FCM key via `npx eas-cli credentials` →
`npm run preflight` → `npx eas-cli build -p android --profile preview`.

- [ ] `npm run preflight` (in `mobile/`) shows all ✓
- [ ] The build finishes and gives a download link/QR
- [ ] APK installs on the phone (allow "install from this source"); app opens with the gold icon, no Expo Go
- [ ] All of section A still works in the installed app
- [ ] Account → **Auto-sync trades** ON (required — see the note at the top)
- [ ] Account → **Trade alerts** on → allow notifications
- [ ] **Send a test notification** → arrives within seconds. If it shows an error, send it to Claude (it names the missing piece)
- [ ] **Real alert:** open a small demo trade → notification "US500 BUY opened — 0.5 @ price" within ~2 min
- [ ] Close it → "US500 closed +$X.XX" within ~2 min
- [ ] **Close the app completely** (swipe away) and repeat → notification still arrives
- [ ] Tap the notification → opens that trade's screen
- [ ] A partial close gives its own "closed" notification
- [ ] Account → Trade alerts **off** → no more notifications; **Log out** also stops them

---

## C. Windows desktop app (v1.1) — opened for you

The new version is running and your **Desktop shortcut** now points to it
(`desktop\release-v1.1.1\win-unpacked\TradeLogger.exe`). Optional proper installer:
`desktop\release-v1.1\TradeLogger Setup 1.1.0.exe` (Windows will warn "unknown publisher" → More info → Run anyway).

- [ ] Window opens on tradelogger.site and you're still signed in
- [ ] Tray icon (bottom-right) has: Open TradeLogger · Backend: healthy · alerts · **Start with Windows** · Quit
- [ ] Tray says **"Backend: healthy"** (before the update it was checking the retired server)
- [ ] Close the window with ✕ → app stays in the tray; **Ctrl+Shift+L** brings it back
- [ ] (Auto-sync must be ON — see the note at the top) Open a trade on Capital.com → within ~2 min a **Windows notification** "… opened". Click it → opens the Journal
- [ ] Close the trade → "… closed +$X.XX" notification
- [ ] Quit the app, open/close a trade, start the app again → you get the notification(s) you missed (max 4 individually, otherwise one summary)
- [ ] Starting the app again does **not** replay old trades
- [ ] Tray → tick **Start with Windows**, restart the PC → app starts minimised in the tray (no window pop-up)
- [ ] Triggered price alert → taskbar badge shows a number

---

## D. Website regressions (things fixed earlier this week)

- [ ] tradelogger.site status pill says **Connected** (not stuck on "Checking")
- [ ] Journal → **Sync now** button works
- [ ] Journal date chips include **Today**, default **This week**
- [ ] Open trades show at the top of the Journal and can be journaled; **Table view** folds them into rows
- [ ] The US500 partial close (0.85 + the other part) both appear as closed trades
- [ ] Journal screenshots show fully (not cropped)

---

## E. "Same as the PWA?" — what matches and what doesn't

**Proven identical by an automated check** (`npm run parity` in `mobile/` runs the website's own filter code against the phone's on 672 random cases across 7 time zones, Monday-week edges, month/year boundaries):
- Date chips (Today / This week / This month / All time) pick exactly the same trades
- Account filter and the Trades / Wins / Losses / Net P&L summary
- Chart-link → image conversion (TradingView share links, direct images)

**Same data, straight from the server:** open positions and floating P&L, closed trades, notes, tags, ratings, screenshots, ideas & reviews, tag record.

**Same behaviour, by hand-check (section A):** autosave after 0.9 s sending only what changed, open-trade notes carrying over on close, big uncropped screenshots, tag suggestions.

**Not on the phone — on purpose** (the phone app is a companion, not a copy):
- Analytics, Command Center, Market, Macro, Killzone Scanner, Chart Analyzer, Challenge Tracker, Research, AI assistant
- Manual trade-entry form, CSV export, calendar view, Pre-Trade Checklist form
- The Feed/Table toggle (the phone has one list layout)

**Phone-only extras:** fingerprint/PIN lock, push alerts, camera capture.

👉 If you want any "not on the phone" item added, tell Claude which one.

---

## F. If a step fails

Send Claude: the **step number**, what you expected, what happened (screenshot), and
whether it's Expo Go, the installed app, the desktop app, or the website.
