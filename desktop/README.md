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
- **Start with Windows** (tray menu → checkbox, installed app only): launches
  minimised to the tray at login, so trade notifications are always on.
- A global hotkey, **Ctrl+Shift+L**, that brings the window to front from
  anywhere — even minimized to tray — without touching the mouse.
- A taskbar overlay badge showing how many price alerts have triggered,
  read via `preload.js` using the page's own logged-in session (polled every
  60s), so you can tell something needs attention without opening the window.

It always loads whatever is live at `https://tradelogger.site` — there is no
separate frontend build to keep in sync. Update the app itself only if the
wrapper (icon, health-check behavior, window chrome) needs to change.

## Run it during development

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
