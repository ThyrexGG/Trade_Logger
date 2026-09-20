# TradeLogger — things to check (phone, desktop, web)

Tick each box as you go. If something fails, note the **step number + what you saw**
(a screenshot is perfect) and send it to Claude. Nothing here has been run on YOUR real
phone yet — Claude ran most of it in an Android emulator (see the note below), plus type-checks and automated tests.

Legend: ✅ = should just work · ⚠️ = newest / least certain, look closely

> ⚠️ **Trade alerts (phone AND desktop) only work while the server's auto-sync is ON.**
> I checked your account: it is currently **OFF** (default). Turn it on once — in the phone's
> **More → Account & alerts → Auto-sync trades**, or on the website's Positions page (Auto toggle). With it off, alerts
> only appear after you tap **Sync now** or open the website.

> **Already run by Claude in an Android emulator (2026-09-19/20)** against a local copy of the server with fake data,
> checking every number against the server's raw data: A1 (login screen, offline banner), A2, A3, A4 (This week),
> A5 (rating, tag, notes, tag record), A6 (chart preview), A7 (library + camera upload, big view, double-tap zoom, delete),
> A7b, A9 (all cards, calendar, day drill-down, starting balance survives an app restart), A10, A11, A12, A13, A14 and the
> Account switches. That found and fixed 6 bugs (calendar lost Sundays, screenshot upload never worked, Auto-sync switch was
> missing, empty profit counted as 0, Expo Go crash, AI reply formatting).
> **Still only checkable on your real phone:** push alerts (section B), fingerprint lock (A8), two-finger pinch zoom,
> vibration, your real broker data, and a side-by-side look at the website's Analytics.

---

## A. Phone app (the installed APK)

Use the installed TradeLogger app (second build, 2026-09-19). To try changes that aren't built yet: on the PC,
`cd C:\Users\Asus\Desktop\Trade_Logger\mobile` then `npm start`, scan the QR in Expo Go (same Wi-Fi;
if it hangs: `npm start -- --tunnel`).

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
- [ ] Set an alert that is already true (e.g. XAUUSD **above** 1) → within about 2 minutes it moves to **Triggered** and you get a phone notification (installed APK only) and a desktop one. It runs on the server, so the PC does not need to be on

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
- [ ] **Share scan as Markdown** (top card) opens the phone's share sheet with the scan as text — same layout as the website's "Copy as Markdown"

**A15 · Killzone chart (new)** ⚠️ — Killzone scanner → the **Chart** card. Compare with the website's chart for the same symbol
- [ ] Candles draw with a price scale on the right; killzone boxes (ASIA / LONDON / NY AM / NY PM) sit over the right hours; **Killzones** chip turns them (and previous-day/week levels) off and on
- [ ] Dashed BSL/SSL lines, dotted FVG edges with a dot on the confirming candle, blue PDH/PDL, a grey **Last** price line — each with its price tag on the right
- [ ] Each candidate has an **S** (sweep) and **M** (structure shift) arrow on the right candles
- [ ] Tap a candle → its open/high/low/close and time appear above the chart; scroll sideways for history
- [ ] **Show on chart** on a candidate → page jumps to the chart, the view centres on it, entry/stop/target lines appear and the other candidates fade; **Hide from chart** undoes it
- [ ] The View chips (1m/5m/15m/1h) and History (150/300/500 bars) reload the chart; arrows stay on the right candles
- [ ] With the market feed down it says so instead of drawing fake candles

**A16 · Today (new)** ⚠️ — More → Today. Compare with the website's Daily Command Center
- [ ] "Right now" shows the current trading session and when the next one starts
- [ ] Today: net P&L, trades (W/L), win rate — matches Analytics for today
- [ ] Account: balance, all-time P&L, profit factor, max drawdown — matches the website
- [ ] Open positions: count, floating P&L and per-symbol lines match the Positions tab
- [ ] Price alerts: active / triggered counts and recent triggers; **Manage alerts** opens Price alerts
- [ ] Market context and Watchlist show; pull down refreshes; it also refreshes by itself every minute

**A17 · Fix or delete a trade you logged by hand (new)** ⚠️ — Journal → tap a trade you entered yourself (its id starts with MANUAL) → the **Logged by hand** card at the bottom
- [ ] **Edit trade** opens the form already filled in (account, symbol, prices, profit, times, tag, notes) with "Save changes"
- [ ] Change the profit and save → the trade screen, Journal, Analytics and the calendar show the new number (pull down on Analytics if it does not update by itself)
- [ ] **Delete trade** asks to confirm, then the trade is gone from Journal, Analytics and the calendar (and its screenshots with it)
- [ ] A trade that came from a broker sync has no such card — it cannot be edited or deleted here

**A18 · Loss limits (new)** ⚠️ — More → Loss limits
- [ ] Every account you trade on has a card; set a **Daily loss limit ($)** and/or a **Drawdown limit (%)** and tap **Save limits** — it says "Saved"
- [ ] The card shows today's loss against the limit as a bar: green, amber from 80%, red once reached
- [ ] Drawdown shows "x% below peak"; if it says it needs a starting balance, enter one for that account in Analytics first
- [ ] Log a losing trade by hand that takes you past 80% of the daily limit → within a few seconds a **"close to"** notification arrives on the phone (installed APK) and the desktop app; past 100% → a **"reached"** one. Each comes once, not again every couple of minutes
- [ ] Tapping the phone notification opens Loss limits. **Clear** removes the limits
- [ ] Not counted on purpose: an open position's floating loss (closed trades only)

**A19 · Challenge tracker (new)** ⚠️ — More → Challenge tracker. Compare with the website's Challenge Tracker (Analytics page) for the same account
- [ ] Pick an account, fill the rules (defaults are 5ers $5K) → **Start tracking** → Phase 1 progress, drawdown, daily-loss and profit-day cards appear
- [ ] Balance, drawdown used/floor and today's loss match the website
- [ ] **Edit the rules** changes numbers without restarting progress; **Mark Phase 1 passed** asks to confirm and moves to Phase 2 (then Funded); **Restart** and **Stop tracking** ask to confirm

**A20 · Chart analyzer (new)** ⚠️ — More → Chart analyzer
- [ ] **Choose or take a screenshot** → pick a chart with entry/stop/target drawn on it → "Reading the chart…" for 10–30 s → symbol, timeframe, direction, entry, stop, target and R:R match what is on the chart
- [ ] A setup rating out of 10 with reasoning, pattern and confluences; anything it could not see says "not visible" instead of a made-up number
- [ ] **Size this trade** opens the Risk gateway with the symbol, direction and levels filled in
- [ ] **Save as note** opens a new note with the reading written into it
- [ ] A TradingView share link (https://www.tradingview.com/x/…) works too; a non-TradingView link is refused with a message

**A21 · Broker connection (new)** ⚠️ — More → Broker connection
- [ ] It lists your Capital.com connection(s) (the same ones as the website's Connections page); no password or key is ever shown
- [ ] **Test** says OK (or a clear failure such as "auth failed (401)"); **Sync now** pulls your trades and they show up in Journal / Positions
- [ ] Adding a connection needs account ID, API key, login email and API password; the form clears after a successful add
- [ ] **Delete** asks to confirm and removes it. Only do this with a spare connection unless you mean it

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

**Now on the phone too (Phase 2):** Analytics with the calendar, Price alerts, Log a trade (manual entry), Risk gateway, AI assistant, Killzone scanner (scan list + "Plan this"; the live candle chart and Markdown export stay website-only).

**Not on the phone — on purpose** (the phone app is a companion, not a copy):
- Command Center, Market, Macro / Market Intelligence, Crypto Carry, Research
- Chart Analyzer and Challenge Tracker (you chose to leave them out)
- System Health, Connections, Partners, CSV export
- The Feed/Table toggle (the phone has one list layout)

**Phone-only extras:** fingerprint/PIN lock, push alerts, camera capture.

👉 If you want any "not on the phone" item added, tell Claude which one.

---

## F. If a step fails

Send Claude: the **step number**, what you expected, what happened (screenshot), and
whether it's Expo Go, the installed app, the desktop app, or the website.
