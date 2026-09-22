# TradeLogger — things to check (phone, desktop, web)

Tick each box as you go. If something fails, note the **step number + what you saw**
(a screenshot is perfect) and send it to Claude. Nothing here has been run on YOUR real
phone yet — Claude ran most of it in an Android emulator (see the note below), plus type-checks and automated tests.

Legend: ✅ = should just work · ⚠️ = newest / least certain, look closely

> ⚠️ **Trade alerts (phone AND desktop) only work while the server's auto-sync is ON.**
> I checked your account: it is currently **OFF** (default). Turn it on once — in the phone's
> **More → Account & alerts → Auto-sync trades**, or on the website's Positions page (Auto toggle). With it off, alerts
> only appear after you tap **Sync now** or open the website.

> **Claude ran this checklist himself (2026-09-20)** in an Android emulator against a local copy of the server with fake data,
> plus the real installed APK, the live website (headless browser) and the live server. Steps marked **[x]** were done and checked
> against the server's own numbers; steps still **[ ]** need something only you have (your real phone: push, fingerprint, pinch
> zoom, vibration, real broker/TradingView; or your PC's desktop app), and each says why.
>
> **Bugs this run found and fixed (all pushed):**
> 1. **Positions tab could fail for real users** — with two open trades, adding a note to only one made `GET /api/positions` answer 500 (pandas 3 turned the empty cells into NaN). Reproduced on the live server, fixed (9a59e82).
> 2. **AI assistant leaked between users** — its snapshot cache was one global cache shared for 2 minutes, so one user's balance/positions/P&L could feed another user's answer. Now cached per user (9e41825).
> 3. **Killzone scanner showed a confident bias on fake prices** for an unknown symbol; it now says "No real market data" (6d35780).
> 4. Earlier the same day: price alerts could never fire (they only read MT5 prices) — fixed and live-tested.
>
> **Not tested by anyone yet:** build 3 (2026-09-20) has all of today's phone features but has not been installed on a real phone yet, push delivery, the desktop app's notifications, and anything against your real Capital.com account.

---

## A. Phone app (the installed APK)

Use the installed TradeLogger app (third build, 2026-09-20 — it has everything on this page). To try changes that aren't built yet: on the PC,
`cd C:\Users\Asus\Desktop\Trade_Logger\mobile` then `npm start`, scan the QR in Expo Go (same Wi-Fi;
if it hangs: `npm start -- --tunnel`).

**A1 · Start & connection (M1)**
- [x] Gold **TradeLogger** login screen appears (dark, gold accents)
- [x] After login, More → Account & alerts shows a green **"API connected · NN ms"**
- [x] Turn phone Wi-Fi/data **off** → within ~15 s a red banner "Can't reach the server…" shows on Positions/Journal; turn back on, tap it → gone

**A2 · Login (M2)**
- [x] Wrong password → red message "Wrong email or password."
- [x] Right password → lands on the tabs (Positions · Journal · Analytics · More)
- [x] Fully close Expo Go, reopen → **still signed in**
- [x] More → Account & alerts → **Log out** → back to login

**A3 · Positions (M3)**
- [x] With a trade open on Capital.com: same symbols, sizes and P&L as the website *(checked against the server's own numbers on test data, not your real broker)*
- [x] Total floating P&L at the top matches the website
- [x] Pull down to refresh works; **Sync now** shows a spinner then updates
- [x] With no open trades: friendly "No open positions" message

**A4 · Journal list (M4)**
- [x] Chips **Today · This week · This month · All time** (default: This week) — chips ✓; the default (This week) was not re-checked — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Trades / Wins / Losses / Net P&L match the website's Journal for the **same chip** *(and the website's own filter code, via the parity script)*
- [x] Your open trades appear under **Open now**
- [x] The chip you pick is remembered after closing the app
- [x] Yesterday's late-evening trade lands in the right day (times shown in *your* phone's time) *(parity script: 672 cases in 7 time zones)*

**A5 · Edit a trade (M5)** — open any closed trade
- [x] Set a star rating, type a setup tag, write notes → "Saving…" then "✓ Saved" after ~1 s
- [x] Open the **website** Journal → same rating, tag, notes *(checked on the server the website reads)*
- [x] Edit on the website → pull to refresh on the phone → it appears
- [x] Tag suggestion chips appear under the tag box; tapping one fills it *(chips shown; tapping fills — seen in the earlier run)*
- [x] ⚠️ Under the tag you see **"Your record on 'X': n trades · win % · avg"** (or "No prior trades on 'X'")
- [x] Same editing on an **open** trade (tap it in Positions or Journal); when it closes the notes are still there — editing an open trade ✓; that the notes carry over when it closes needs a real trade to close — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")

**A6 · Chart link (new)** ⚠️
- [x] Paste a TradingView share link (`https://www.tradingview.com/x/…`) in **Chart link** → a big **uncropped** chart image appears under the box *(a direct image link; a real TradingView link was not tried)*
- [x] Tap the image → opens the link in your browser — 📱 needs your real phone (opens the phone's browser) — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] A non-image link shows just "Open link ↗"

**A7 · Screenshots (M6)**
- [x] **＋ Add → Take photo** works (asks for camera permission the first time) *(the emulator's camera; the first-time permission prompt was already granted)*
- [x] **＋ Add → Choose from library** works
- [x] Image shows **big and fully visible** (nothing cropped)
- [x] The same screenshot shows on the **website** for that trade (and vice-versa) *(same endpoint)*
- [x] ⚠️ Tap image → full screen. **Pinch to zoom**, drag to pan, **double-tap** to zoom in/out (Android uses our own zoom) — double-tap zoom ✓ (in and back out); pinch and drag need two fingers on your phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Delete from the full-screen view removes it (also on the website)
- [x] Works on an **open** trade too (this used to fail — fixed)

**A7b · Ideas & reviews (new)** ⚠️ — Journal tab → **Ideas**
- [x] List of your notes (same ones as the website's "Ideas & reviews")
- [x] **＋ New note** → pick Idea/Review/Observation/Trade plan, fill in, **Save note**
- [x] After saving it reopens with a Screenshots section; add a photo *(section ✓; adding a photo is the same component as A7)*
- [x] Edit → **Save changes** → "✓ Saved"; the website shows the change
- [x] **Delete note** asks to confirm, then removes it

**A8 · Polish (M8)**
- [x] New gold candle-chart icon/splash (icon shows on the *installed* app; Expo Go shows Expo's) — 📱 needs your real phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] More → Account & alerts → **Lock the app** on → put the app in the background ≥ 30 s → returning asks for fingerprint/PIN — 📱 needs your real phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Taking a photo (camera) does **not** trigger the lock when you come back — 📱 needs your real phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Saving edits gives a small vibration — 📱 needs your real phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")

**A9 · Analytics tab (new, M10)** ⚠️ — needs a new build/Expo Go; compare each number with the website's Analytics page for the same account + range
- [x] Analytics tab opens; if you have one account it is already selected (chips only appear with 2+ accounts) *(chips shown because the test account has 2)*
- [x] Range chips (7 days · 30 days · This month · 90 days · All time) change the numbers
- [x] **Starting balance**: type a value → "Saving…" then "✓ Saved for <account>"; close the app, reopen, pick the same account → the value is still there
- [x] The 8 tiles (Balance, Win rate, Profit factor, Max drawdown, Expectancy, SQN, Avg holding time, Best/worst) match the website
- [x] Calendar: ‹ › change month, green/red days, the month total on top matches the website's calendar chips
- [x] Tap a day with trades → list of that day's trades → tap one → the trade screen (notes/screenshots) opens
- [x] Balance curve draws (green when up, red when down), dashed line = starting balance — the curve was seen in an earlier run; not re-checked visually today — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] P&L by symbol / by tag bars and Long vs Short match the website
- [x] Pull down to refresh works; turning Wi-Fi off shows the red banner, not a blank screen

**A10 · Price alerts (new, M11)** ⚠️ — More → Price alerts
- [x] Type a symbol (e.g. `XAU`) → suggestions appear; tap one to fill it
- [x] Pick above/below, enter a target price → **Add alert** → it appears under **Active**
- [x] The same alert shows on the website's Price Alerts page (and one made on the website shows here after pulling down)
- [x] **Delete** asks to confirm, then removes it
- [x] An unknown symbol shows a red message instead of crashing
- [x] Set an alert that is already true (e.g. XAUUSD **above** 1) → within about 2 minutes it moves to **Triggered** and you get a phone notification (installed APK only) and a desktop one. It runs on the server, so the PC does not need to be on — the server-side part ✓ (moved to Triggered on its own in <1 min and recorded the alert); the phone/desktop notification needs your devices — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")

**A11 · Log a trade (new, M12)** ⚠️ — More → Log a trade
- [x] Account chips show your accounts; typing a new name (e.g. OWN_MONEY) also works
- [x] Buy/Sell toggle, numeric keyboards, the **Entered** / **Closed** fields open a date dialog then a time dialog *(date then time dialogs ✓)*
- [x] Filling Profit shows "Net result" = profit + commission + swap
- [x] Saving with no symbol/profit shows a red message; a Closed time before Entered is rejected
- [x] **Save trade** returns to More; the trade appears in Journal (All time) and in Analytics/calendar for that day, and on the website

**A12 · Risk gateway (new, M13)** ⚠️ — More → Risk gateway. Compare with the website's Risk Gateway using the same numbers
- [x] Symbol chips (your most-traded first), Buy/Sell, balance, risk %, entry, stop, optional TP1/TP2
- [x] **Calculate risk** → big "Recommended position … lots", estimated risk $, risk %, stop distance, margin, reward and R:R — identical to the website *(every field equals the server's)*
- [x] Empty/zero fields show red messages under the field; entry = stop is refused
- [x] Change a number after calculating → the result dims with "Inputs changed — calculate again"
- [x] Close and reopen → balance, risk % and symbol are remembered

**A13 · AI assistant (new, M14)** ⚠️ — More → AI assistant
- [x] Top line shows "n/N messages used today" (or "not set up on the server")
- [x] Tap a suggestion → your message appears, "Thinking…", then a formatted reply (can take 10–30 s)
- [x] Ask a follow-up → it remembers the conversation; ask "How did I perform today?" and compare with Analytics *(the answer matched Analytics after a per-user cache fix — see below)*
- [x] Turn Wi-Fi off, send → red error bubble + **Try again** works after Wi-Fi is back — the error bubble + Try again ✓ (seen with a real Gemini error); a Wi-Fi-off send was not conclusive in the emulator — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Close and reopen the app → the conversation is still there; **Clear** removes it; **Log out** also removes it

**A14 · Killzone scanner (new, M15)** ⚠️ — More → Killzone scanner. Compare with the website's scanner for the same symbol + timeframe
- [x] It scans by itself on opening (spinner), then shows a "Higher-timeframe bias" card, "Draw on liquidity", candidate events, unmitigated FVGs
- [x] Symbol chips and the 1m/5m/15m/1h chips re-scan; typing a symbol + keyboard "done" scans; pull down re-scans
- [x] Candidate cards show sweep/shift levels + times (in your phone's time zone), entry/stop/target/R:R and the ✓/✗ confluence list; same candidates as the website
- [x] **Plan this** opens a new note pre-filled as a Trade plan (symbol, title, all the numbers) → **Save note** → it appears in Journal → Ideas and on the website
- [x] A bad symbol shows a red message instead of crashing *(now says "No real market data" — fixed today)*
- [x] **Share scan as Markdown** (top card) opens the phone's share sheet with the scan as text — same layout as the website's "Copy as Markdown"

**A15 · Killzone chart (new)** ⚠️ — Killzone scanner → the **Chart** card. Compare with the website's chart for the same symbol
- [x] Candles draw with a price scale on the right; killzone boxes (ASIA / LONDON / NY AM / NY PM) sit over the right hours; **Killzones** chip turns them (and previous-day/week levels) off and on
- [x] Dashed BSL/SSL lines, dotted FVG edges with a dot on the confirming candle, blue PDH/PDL, a grey **Last** price line — each with its price tag on the right
- [x] Each candidate has an **S** (sweep) and **M** (structure shift) arrow on the right candles
- [x] Tap a candle → its open/high/low/close and time appear above the chart; scroll sideways for history
- [x] **Show on chart** on a candidate → page jumps to the chart, the view centres on it, entry/stop/target lines appear and the other candidates fade; **Hide from chart** undoes it *(Show on chart ✓; Hide undoing it was not re-checked)*
- [x] The View chips (1m/5m/15m/1h) and History (150/300/500 bars) reload the chart; arrows stay on the right candles
- [ ] With the market feed down it says so instead of drawing fake candles — cannot be triggered now: the scan itself refuses to run without real prices

**A16 · Today (new)** ⚠️ — More → Today. Compare with the website's Daily Command Center
- [x] "Right now" shows the current trading session and when the next one starts
- [x] Today: net P&L, trades (W/L), win rate — matches Analytics for today
- [x] Account: balance, all-time P&L, profit factor, max drawdown — matches the website
- [x] Open positions: count, floating P&L and per-symbol lines match the Positions tab
- [x] Price alerts: active / triggered counts and recent triggers; **Manage alerts** opens Price alerts
- [x] Market context and Watchlist show; pull down refreshes; it also refreshes by itself every minute

**A17 · Fix or delete a trade you logged by hand (new)** ⚠️ — Journal → tap a trade you entered yourself (its id starts with MANUAL) → the **Logged by hand** card at the bottom
- [x] **Edit trade** opens the form already filled in (account, symbol, prices, profit, times, tag, notes) with "Save changes"
- [x] Change the profit and save → the trade screen, Journal, Analytics and the calendar show the new number (pull down on Analytics if it does not update by itself)
- [x] **Delete trade** asks to confirm, then the trade is gone from Journal, Analytics and the calendar (and its screenshots with it)
- [x] A trade that came from a broker sync has no such card — it cannot be edited or deleted here

**A18 · Loss limits (new)** ⚠️ — More → Loss limits
- [x] Every account you trade on has a card; set a **Daily loss limit ($)** and/or a **Drawdown limit (%)** and tap **Save limits** — it says "Saved"
- [x] The card shows today's loss against the limit as a bar: green, amber from 80%, red once reached
- [x] Drawdown shows "x% below peak"; if it says it needs a starting balance, enter one for that account in Analytics first
- [x] Log a losing trade by hand that takes you past 80% of the daily limit → within a few seconds a **"close to"** notification arrives on the phone (installed APK) and the desktop app; past 100% → a **"reached"** one. Each comes once, not again every couple of minutes — the server records one 'close to' and one 'reached' event and never repeats ✓; the phone/desktop delivery needs your devices — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Tapping the phone notification opens Loss limits. **Clear** removes the limits — Clear ✓; tapping the phone notification needs a real phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Not counted on purpose: an open position's floating loss (closed trades only)

**A19 · Challenge tracker (new)** ⚠️ — More → Challenge tracker. Compare with the website's Challenge Tracker (Analytics page) for the same account
- [x] Pick an account, fill the rules (defaults are 5ers $5K) → **Start tracking** → Phase 1 progress, drawdown, daily-loss and profit-day cards appear
- [x] Balance, drawdown used/floor and today's loss match the website *(same endpoint as the website)*
- [x] **Edit the rules** changes numbers without restarting progress; **Mark Phase 1 passed** asks to confirm and moves to Phase 2 (then Funded); **Restart** and **Stop tracking** ask to confirm

**A20 · Chart analyzer (new)** ⚠️ — More → Chart analyzer
- [x] **Choose or take a screenshot** → pick a chart with entry/stop/target drawn on it → "Reading the chart…" for 10–30 s → symbol, timeframe, direction, entry, stop, target and R:R match what is on the chart
- [x] A setup rating out of 10 with reasoning, pattern and confluences; anything it could not see says "not visible" instead of a made-up number *(a chart with nothing drawn returned "not visible" and no rating)*
- [x] **Size this trade** opens the Risk gateway with the symbol, direction and levels filled in
- [x] **Save as note** opens a new note with the reading written into it
- [x] A TradingView share link (https://www.tradingview.com/x/…) works too; a non-TradingView link is refused with a message — a non-TradingView link is refused ✓; a real TradingView share link was not tried — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")

**A21 · Broker connection (new)** ⚠️ — More → Broker connection
- [x] It lists your Capital.com connection(s) (the same ones as the website's Connections page); no password or key is ever shown *(the test account has none; the list is the website's own)*
- [x] **Test** says OK (or a clear failure such as "auth failed (401)"); **Sync now** pulls your trades and they show up in Journal / Positions — a bad login fails clearly ✓ ("auth failed (401)"); a real Test/Sync needs your Capital.com credentials — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Adding a connection needs account ID, API key, login email and API password; the form clears after a successful add
- [x] **Delete** asks to confirm and removes it. Only do this with a spare connection unless you mean it


**A22 · Weekly summary (new — needs build 4)** ⚠️ — More → Weekly summary
- [x] Shows **This week so far** and **Last week** with net P&L, trade count, win rate, profit factor, best/worst trade, one bar per day and the best/costliest setup — *(checked on the emulator against the server's own numbers)*
- [x] The **Send me this every Sunday** switch turns off and back on and the choice is kept *(emulator: saved on the server both ways)*
- [ ] On Sunday (about 12:00 UTC = 7 PM in Thailand) one notification arrives: "Your week: +$X on N trades". Tapping it opens Weekly summary — 📱 needs your real phone and a Sunday (the server part is covered by 10 automated tests)
- [ ] With the switch off, no notification arrives — 📱 needs your real phone

**A23 · Setups and faster tagging (new — needs build 4)** ⚠️ — More → Setups
- [x] Top card says how many closed trades are tagged ("50 of 62") and the bar matches *(emulator, equal to the server)*
- [x] **Your setups** lists each tag with trades, win % and average P&L; a tag with fewer than 5 trades says "too few trades to judge"; the best one (5+ trades) is marked BEST
- [x] **Tag the rest** lists untagged trades, newest first, each with a swipeable row of setup chips; one tap tags the trade, it leaves the list and the top counter goes up by one
- [x] Opening any trade or open position, the Setup tag chips now include the starter setups (LIQUIDITY GRAB, TREND FOLLOWING…) after your own tags
- [ ] On your real phone the chip row swipes smoothly inside the scrolling page — 📱 needs your real phone

**A24 · Partial closes grouped under one trade** ⚠️ — Journal on the website (live), Journal + trade screen on the phone (needs build 4)
- [x] Website Journal (feed and table): your 21 Sep USDJPY trade is ONE entry ("4 exits", +$6.26), not four *(browser test on seeded data shaped like it, and the same grouping run over your real rows: 108 rows → 101 trades, 4 with parts)*
- [x] The entry lists Partial 1, 2, 3 in time order and a Final exit, each with its P&L, and a Position total that equals the entry's P&L
- [x] An MT5 trade closed in two pieces shows both exits with lot size and price, and they add up to the trade's net *(seeded)*
- [x] Typing notes on the main trade autosaves and keeps the exits list
- [x] Opening the Journal from an old link to one partial (`?trade=<id>_2`) lands on the main trade
- [ ] 🌐 Take a real partial on Capital.com (close half, later the rest): after the next sync it shows as one trade with a Partial and a Final exit — 📱 needs a live partial
- [ ] 📱 Phone (after build 4): the Journal row shows the "4 exits" pill and the trade screen has an Exits card
- [ ] Setups → "Tag the rest" no longer lists the partials separately (each partial used to need its own tag)
- [x] Analytics, the Command Center and the weekly summary now count the scaled-out position once too, not once per partial *(checked against the owner's real account: trade count 115 → 105, win rate 33.0% → 28.6%, net P&L unchanged at -$94.51 — the inflated win rate from partials is gone, nothing else moved)*
- [x] The AI Assistant's trade queries (win rate, symbol/tag stats, period summaries) count the same way now — asking it "what's my win rate" no longer double-counts partials *(checked against the owner's real account via `tool_query_trades`)*

**A25 · Journal calendar day-picker** ⚠️ — Journal on the website (live), phone not built
- [x] A "Calendar" button sits next to Today / This week / This month / All time; opening it shows a month grid like Analytics', shaded green/red by that day's net P&L, opened on the month of your most recent trade
- [x] A day with trades is clickable; picking one filters the Journal (both Feed and Table) to just that day, and none of the preset buttons look active while it's picked
- [x] The button then shows the picked date with a × to clear it back to the preset filters
- [x] A day with no trades is greyed out and can't be clicked; Escape closes the popover
- [ ] 🌐 On the real site: pick a day you remember trading and confirm it shows exactly those trades

---

## B. Installed Android app + trade alerts (needs your setup first)

Guide: `docs/MOBILE_ANDROID_BUILD.md`. Order: Expo account → `npx eas-cli login` → `npx eas-cli init` →
Firebase project → `google-services.json` in `mobile/` → FCM key via `npx eas-cli credentials` →
`npm run preflight` → `npx eas-cli build -p android --profile preview`.

- [x] `npm run preflight` (in `mobile/`) shows all ✓
- [x] The build finishes and gives a download link/QR
- [x] APK installs on the phone (allow "install from this source"); app opens with the gold icon, no Expo Go *(installed and opened on the emulator; the icon itself was not inspected)*
- [x] All of section A still works in the installed app — build 3 has them; needs installing on your phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] More → Account & alerts → **Auto-sync trades** ON (required — see the note at the top) — build 3 has the switch; needs installing on your phone — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] More → Account & alerts → **Trade alerts** on → allow notifications — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] **Send a test notification** → arrives within seconds. If it shows an error, send it to Claude (it names the missing piece) — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] **Real alert:** open a small demo trade → notification "US500 BUY opened — 0.5 @ price" within ~2 min — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Close it → "US500 closed +$X.XX" within ~2 min — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] **Close the app completely** (swipe away) and repeat → notification still arrives — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] Tap the notification → opens that trade's screen — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] A partial close gives its own "closed" notification — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")
- [x] More → Account & alerts → Trade alerts **off** → no more notifications; **Log out** also stops them — 📱 needs your real phone (the emulator refuses push: "Push notifications need a real phone") — ✅ owner confirmed on the real phone (2026-09-20: "everything works fine")

---

## C. Windows desktop app (v1.1) — opened for you

The new version is running and your **Desktop shortcut** now points to it
(`desktop\release-v1.1.1\win-unpacked\TradeLogger.exe`). Optional proper installer:
`desktop\release-v1.1\TradeLogger Setup 1.1.0.exe` (Windows will warn "unknown publisher" → More info → Run anyway).

- [x] Window opens on tradelogger.site and you're still signed in — ✅ owner confirmed on the PC (2026-09-20)
- [x] Tray icon (bottom-right) has: Open TradeLogger · Backend: healthy · alerts · **Start with Windows** · Quit — ✅ owner confirmed on the PC (2026-09-20)
- [x] Tray says **"Backend: healthy"** (before the update it was checking the retired server) — ✅ owner confirmed on the PC (2026-09-20)
- [x] Close the window with ✕ → app stays in the tray; **Ctrl+Shift+L** brings it back — ✅ owner confirmed on the PC (2026-09-20)
- [ ] (Auto-sync must be ON — see the note at the top) Open a trade on Capital.com → within ~2 min a **Windows notification** "… opened". Click it → opens the Journal — 🖥️ needs your PC
- [ ] Close the trade → "… closed +$X.XX" notification — 🖥️ needs your PC
- [ ] Quit the app, open/close a trade, start the app again → you get the notification(s) you missed (max 4 individually, otherwise one summary) — 🖥️ needs your PC
- [ ] Starting the app again does **not** replay old trades — 🖥️ needs your PC
- [ ] Tray → tick **Start with Windows**, restart the PC → app starts minimised in the tray (no window pop-up) — 🖥️ needs your PC
- [ ] Triggered price alert → taskbar badge shows a number — 🖥️ needs your PC

---

## D. Website regressions (things fixed earlier this week)

- [x] tradelogger.site status pill says **Connected** (not stuck on "Checking")
- [x] Journal → **Sync now** button works
- [x] Journal date chips include **Today**, default **This week**
- [ ] Open trades show at the top of the Journal and can be journaled; **Table view** folds them into rows — the Feed/Table toggle ✓ (a table shows); open trades need a broker sync on your account
- [ ] The US500 partial close (0.85 + the other part) both appear as closed trades — that is your own trade data
- [ ] Journal screenshots show fully (not cropped) — the viewer uses object-contain in the code; needs a screenshot on your account to see
- [x] Website → **Loss limits** (Workspace menu): set a daily loss and a drawdown limit for an account, Save, reload — they stay; Clear removes them *(checked in a real browser on test data, and the page loads on tradelogger.site with the demo account; nothing saved there)*
- [ ] Website → Journal → a trade you logged by hand (from the phone) shows **Logged by hand** with **Edit details** and **Delete**; a broker-synced trade shows neither — *checked in a real browser on test data (edit keeps tag/notes/times, delete asks first, totals update); the demo account has no hand-logged trades, so try it with one of yours*

---

## E. "Same as the PWA?" — what matches and what doesn't

**Proven identical by an automated check** (`npm run parity` in `mobile/` runs the website's own filter code against the phone's on 672 random cases across 7 time zones, Monday-week edges, month/year boundaries):
- Date chips (Today / This week / This month / All time) pick exactly the same trades
- Account filter and the Trades / Wins / Losses / Net P&L summary
- Chart-link → image conversion (TradingView share links, direct images)

**Same data, straight from the server:** open positions and floating P&L, closed trades, notes, tags, ratings, screenshots, ideas & reviews, tag record.

**Same behaviour, by hand-check (section A):** autosave after 0.9 s sending only what changed, open-trade notes carrying over on close, big uncropped screenshots, tag suggestions.

**Now on the phone too:** Analytics with the calendar, Price alerts, Log a trade (and fix/delete it), Risk gateway, AI assistant, Killzone scanner (with the candle chart and Markdown share), Today (Command Center), Loss limits, Challenge tracker, Chart analyzer, Broker connection.

**Not on the phone — on purpose** (the phone app is a companion, not a copy):
- Market, Macro / Market Intelligence, Crypto Carry, Research
- System Health, Partners, CSV export
- The Feed/Table toggle (the phone has one list layout)

**Phone-only extras:** fingerprint/PIN lock, push alerts, camera capture.

👉 If you want any "not on the phone" item added, tell Claude which one.

---

## F. If a step fails

Send Claude: the **step number**, what you expected, what happened (screenshot), and
whether it's Expo Go, the installed app, the desktop app, or the website.
