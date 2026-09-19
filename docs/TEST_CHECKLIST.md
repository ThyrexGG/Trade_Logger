# TradeLogger — things to check (phone, desktop, web)

Tick each box as you go. If something fails, note the **step number + what you saw**
(a screenshot is perfect) and send it to Claude. Nothing here has been run on a real
phone yet — everything was verified by type-checks, bundling, and automated tests only.

Legend: ✅ = should just work · ⚠️ = newest / least certain, look closely

> ⚠️ **Trade alerts (phone AND desktop) only work while the server's auto-sync is ON.**
> I checked your account: it is currently **OFF** (default). Turn it on once — in the phone's
> **More → Account & alerts → Auto-sync trades**, or on the website's Positions page (Auto toggle). With it off, alerts
> only appear after you tap **Sync now** or open the website.

---

## A. Phone app in Expo Go (no setup beyond Expo Go)

Start it: on the PC, `cd C:\Users\Asus\Desktop\Trade_Logger\mobile` then `npm start`, scan the QR
in Expo Go. Same Wi-Fi. If it hangs: `npm start -- --tunnel`.

**A1 · Start & connection (M1)**
- [ ] Gold **TradeLogger** login screen appears (dark, gold accents)
- [ ] After login, More → Account & alerts shows a green **"API connected · NN ms"**
- [ ] Turn phone Wi-Fi/data **off** → within ~15 s a red banner "Can't reach the server…" shows on Positions/Journal; turn back on, tap it → gone

**A2 · Login (M2)**
- [ ] Wrong password → red message "Wrong email or password."
- [ ] Right password → lands on the tabs (Positions · Journal · Analytics · More)
- [ ] Fully close Expo Go, reopen → **still signed in**
- [ ] More → Account & alerts → **Log out** → back to login

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
- [ ] More → Account & alerts → **Lock the app** on → put the app in the background ≥ 30 s → returning asks for fingerprint/PIN
- [ ] Taking a photo (camera) does **not** trigger the lock when you come back
- [ ] Saving edits gives a small vibration

**A9 · Analytics tab (new, M10)** ⚠️ — needs a new build/Expo Go; compare each number with the website's Analytics page for the same account + range
- [ ] Analytics tab opens; if you have one account it is already selected (chips only appear with 2+ accounts)
- [ ] Range chips (7 days · 30 days · This month · 90 days · All time) change the numbers
- [ ] **Starting balance**: type a value → "Saving…" then "✓ Saved for <account>"; close the app, reopen, pick the same account → the value is still there
- [ ] The 8 tiles (Balance, Win rate, Profit factor, Max drawdown, Expectancy, SQN, Avg holding time, Best/worst) match the website
- [ ] Calendar: ‹ › change month, green/red days, the month total on top matches the website's calendar chips
- [ ] Tap a day with trades → list of that day's trades → tap one → the trade screen (notes/screenshots) opens
- [ ] Balance curve draws (green when up, red when down), dashed line = starting balance
- [ ] P&L by symbol / by tag bars and Long vs Short match the website
- [ ] Pull down to refresh works; turning Wi-Fi off shows the red banner, not a blank screen

**A10 · Price alerts (new, M11)** ⚠️ — More → Price alerts
- [ ] Type a symbol (e.g. `XAU`) → suggestions appear; tap one to fill it
- [ ] Pick above/below, enter a target price → **Add alert** → it appears under **Active**
- [ ] The same alert shows on the website's Price Alerts page (and one made on the website shows here after pulling down)
- [ ] **Delete** asks to confirm, then removes it
- [ ] An unknown symbol shows a red message instead of crashing
- [ ] (Only while the PC's MT5 auto-sync daemon runs) a crossed alert moves to **Triggered** and sends a phone + desktop notification; tapping the phone one opens Price alerts

**A11 · Log a trade (new, M12)** ⚠️ — More → Log a trade
- [ ] Account chips show your accounts; typing a new name (e.g. OWN_MONEY) also works
- [ ] Buy/Sell toggle, numeric keyboards, the **Entered** / **Closed** fields open a date dialog then a time dialog
- [ ] Filling Profit shows "Net result" = profit + commission + swap
- [ ] Saving with no symbol/profit shows a red message; a Closed time before Entered is rejected
- [ ] **Save trade** returns to More; the trade appears in Journal (All time) and in Analytics/calendar for that day, and on the website

**A12 · Risk gateway (new, M13)** ⚠️ — More → Risk gateway. Compare with the website's Risk Gateway using the same numbers
- [ ] Symbol chips (your most-traded first), Buy/Sell, balance, risk %, entry, stop, optional TP1/TP2
- [ ] **Calculate risk** → big "Recommended position … lots", estimated risk $, risk %, stop distance, margin, reward and R:R — identical to the website
- [ ] Empty/zero fields show red messages under the field; entry = stop is refused
- [ ] Change a number after calculating → the result dims with "Inputs changed — calculate again"
- [ ] Close and reopen → balance, risk % and symbol are remembered

**A13 · AI assistant (new, M14)** ⚠️ — More → AI assistant
- [ ] Top line shows "n/N messages used today" (or "not set up on the server")
- [ ] Tap a suggestion → your message appears, "Thinking…", then a formatted reply (can take 10–30 s)
- [ ] Ask a follow-up → it remembers the conversation; ask "How did I perform today?" and compare with Analytics
- [ ] Turn Wi-Fi off, send → red error bubble + **Try again** works after Wi-Fi is back
- [ ] Close and reopen the app → the conversation is still there; **Clear** removes it; **Log out** also removes it

**A14 · Killzone scanner (new, M15)** ⚠️ — More → Killzone scanner. Compare with the website's scanner for the same symbol + timeframe
- [ ] It scans by itself on opening (spinner), then shows a "Higher-timeframe bias" card, "Draw on liquidity", candidate events, unmitigated FVGs
- [ ] Symbol chips and the 1m/5m/15m/1h chips re-scan; typing a symbol + keyboard "done" scans; pull down re-scans
- [ ] Candidate cards show sweep/shift levels + times (in your phone's time zone), entry/stop/target/R:R and the ✓/✗ confluence list; same candidates as the website
- [ ] **Plan this** opens a new note pre-filled as a Trade plan (symbol, title, all the numbers) → **Save note** → it appears in Journal → Ideas and on the website
- [ ] A bad symbol shows a red message instead of crashing
- [ ] Not on the phone on purpose: the live candle chart and the Markdown export

---

## B. Installed Android app + trade alerts (needs your setup first)

Guide: `docs/MOBILE_ANDROID_BUILD.md`. Order: Expo account → `npx eas-cli login` → `npx eas-cli init` →
Firebase project → `google-services.json` in `mobile/` → FCM key via `npx eas-cli credentials` →
`npm run preflight` → `npx eas-cli build -p android --profile preview`.

- [ ] `npm run preflight` (in `mobile/`) shows all ✓
- [ ] The build finishes and gives a download link/QR
- [ ] APK installs on the phone (allow "install from this source"); app opens with the gold icon, no Expo Go
- [ ] All of section A still works in the installed app
- [ ] More → Account & alerts → **Auto-sync trades** ON (required — see the note at the top)
- [ ] More → Account & alerts → **Trade alerts** on → allow notifications
- [ ] **Send a test notification** → arrives within seconds. If it shows an error, send it to Claude (it names the missing piece)
- [ ] **Real alert:** open a small demo trade → notification "US500 BUY opened — 0.5 @ price" within ~2 min
- [ ] Close it → "US500 closed +$X.XX" within ~2 min
- [ ] **Close the app completely** (swipe away) and repeat → notification still arrives
- [ ] Tap the notification → opens that trade's screen
- [ ] A partial close gives its own "closed" notification
- [ ] More → Account & alerts → Trade alerts **off** → no more notifications; **Log out** also stops them

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
