# TradeLogger Desktop

A thin native shell around the live site — not a rewrite of the app. It
gives you:

- A real windowed app (Start Menu shortcut, taskbar icon) instead of a
  browser tab.
- A system tray icon. Closing the window minimizes to tray instead of
  quitting, so it keeps running in the background.
- A native Windows notification if the backend (`tradelogger-api-sg.onrender.com`)
  stops responding to its health check, and another when it recovers.
- **Trade notifications**: a native Windows notification when a trade opens or
  closes ("US500 closed +$32.10"). Click it to open the Journal. The server records
  each event once (`/api/push/events`) and the app polls it every 30 s using your
  logged-in session, so a restart never replays old trades and events that happened
  while the app was closed are caught up on the next launch.
- **Send test notification** (tray menu): pops a sample trade alert right away, to check Windows is showing notifications (Focus assist / Do not disturb). Does not test the server feed.
- **Start with Windows** (tray menu → checkbox, installed app only): launches
  minimised to the tray at login, so trade notifications are always on.
- A global hotkey, **Ctrl+Shift+L**, that brings the window to front from
  anywhere — even minimized to tray — without touching the mouse.
- A taskbar overlay badge showing how many price alerts have triggered since you
  last had the window in front of you, read via `preload.js` using the page's own
  logged-in session (polled every 60s). Opening or focusing the window clears it;
  the next alert that fires brings it back. (Triggered alerts stay in the list until
  you delete them, so the badge deliberately doesn't count those.)

It always loads whatever is live at `https://tradelogger.site` — there is no
separate frontend build to keep in sync. Update the app itself only if the
wrapper (icon, health-check behavior, window chrome) needs to change.

Trade notifications need the server's **auto-sync** switched on (Positions page → Auto, or the
phone app's Account screen) — the server only records a trade event when it syncs.

## Run it during development

> Launching from VS Code's terminal? That editor sets `ELECTRON_RUN_AS_NODE=1`, which makes Electron
> apps behave like plain Node and exit instantly ("bad option: …"). Clear it first:
> PowerShell `Remove-Item Env:ELECTRON_RUN_AS_NODE`, Git Bash `env -u ELECTRON_RUN_AS_NODE npm start`.

```
cd desktop
npm install
npm start
```

## Build a Windows installer

```
cd desktop
npm install
npm run dist
```

The installer lands in `desktop/release/` (`TradeLogger Setup <version>.exe`). If the
app is running it locks that folder — build elsewhere with
`npx electron-builder --win nsis --x64 --config.directories.output=release-vNEXT`. It's unsigned (no code-signing
certificate — those cost money), so Windows SmartScreen will show an "unknown
publisher" warning on first run. Click "More info" → "Run anyway". This is
expected for a personal/small-scale app and doesn't mean anything is wrong.

## "Sync now" says "Python was not found"

The desktop app runs the MT5 push agent (and the local fallback server) with Python on this PC.
Plain `python` on Windows can be the Microsoft Store stub, which only prints "Python was not found;
run without arguments to install from the Microsoft Store" — that text then shows on the Analytics
page. Since v1.1.7 `main.js` (`pythonCommand()`) looks for a per-user install
(`%LOCALAPPDATA%\Python\pythoncore-*\python.exe`), then the `py -3` launcher, and only then `python`.
The 15-minute scheduled task was never affected: it is registered with the full interpreter path.

## It never switched to local mode when the cloud was down

How it works: the app pings the cloud API's `/api/health/db` every minute; after two failures in a row it
starts `run_local_fallback.py` (this PC's own copy of the data, port 8010) and loads it in the window, then
switches back when the cloud answers. Every step is written to `%APPDATA%\TradeLogger\fallback.log` (look
for `spawning local fallback server` and `waitForFallbackHealthy -> true/false`).

2026-10-27 the log showed 120 failed switches: the local server took ~94 s to answer `/api/health` and the app
kills it at its start timeout (then retries 5 minutes later, forever). Cause: `api/main.py`'s start-up warm-up
(seven page requests plus macro / news / calendar fetches) runs before uvicorn accepts a connection, and
`--sync-now` ran one more blocking Capital.com + MT5 sync first. Fix: the fallback sets `TL_SKIP_WARMUP=1`,
syncs in the background (the auto-sync loop starts the moment the server is up, so a missing internet
connection can no longer block it), and the app waits up to 180 s. Start-up is now ~3 s.
`tests/test_local_fallback_startup.py` fails if the warm-up or a blocking sync comes back.

The script change takes effect at once (the app runs it from the repo). The longer wait in `main.js` only
applies after the installer is rebuilt. The fallback serves `frontend/dist`, which is not rebuilt for you:
run `npm run build` in `frontend/` after UI changes, or local mode shows the old screens.
