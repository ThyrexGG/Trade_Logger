# TradeLogger Desktop

A thin native shell around the live site — not a rewrite of the app. It
gives you:

- A real windowed app (Start Menu shortcut, taskbar icon) instead of a
  browser tab.
- A system tray icon. Closing the window minimizes to tray instead of
  quitting, so it keeps running in the background.
- A native Windows notification if the backend (`tradelogger-api.onrender.com`)
  stops responding to its health check, and another when it recovers.

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

The installer lands in `desktop/release/`. It's unsigned (no code-signing
certificate — those cost money), so Windows SmartScreen will show an "unknown
publisher" warning on first run. Click "More info" → "Run anyway". This is
expected for a personal/small-scale app and doesn't mean anything is wrong.
