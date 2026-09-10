# TradeLogger MT5 Sync

For traders on a **MetaTrader 5** broker (Exness, IC Markets, Pepperstone,
most prop firms). MetaTrader has no web API, so this small program runs on
**your** Windows PC, reads MT5, and sends your trade history to TradeLogger
over HTTPS.

- It **never** places, changes or closes a trade.
- It only ever writes **your** data.
- Your trades sync automatically every 15 minutes while your PC is on and
  MetaTrader is running.

---

## Setup (about 1 minute)

1. **Get the program** from whoever invited you: `tradelogger-mt5-sync.exe`.
2. Put it in its own folder (e.g. `Documents\TradeLogger`).
3. Open your **MetaTrader 5** terminal and log in to the account you want to track.
4. **Double-click `tradelogger-mt5-sync.exe`.**
5. Type your **TradeLogger email and password** (the login the owner invited).

That's it. It checks the connection, installs a background task, and does a
first sync. From then on it updates itself every 15 minutes.

> Windows may show a blue "Windows protected your PC" box the first time
> (the program isn't code-signed). Click **More info -> Run anyway**.

---

## Everyday use

Nothing. Leave your PC on with MetaTrader running and logged in. Check
TradeLogger — your journal, analytics and positions fill in on their own.

If you turn MetaTrader off, syncing pauses and catches up when it's back.

---

## Commands (optional)

Open a terminal in the folder:

| Command | Does |
|---|---|
| `tradelogger-mt5-sync --check` | Test your login + MetaTrader connection |
| `tradelogger-mt5-sync --once` | Sync one time right now |
| `tradelogger-mt5-sync --uninstall` | Remove the background task (your synced data stays) |
| `tradelogger-mt5-sync --daemon` | Keep syncing in this window (Mac/Linux, or if the task won't install) |

---

## Running from source instead of the .exe

Needs Python 3.9+ and the MetaTrader 5 terminal.

```
pip install MetaTrader5 requests
python mt5_push_agent.py            # runs the same wizard
```

`--config path\to\file.json` points at a specific config. See
`mt5_agent_config.example.json` for every field — you normally don't need it,
the wizard writes `mt5_agent_config.json` for you.

---

## Notes

- **Incremental.** After the first run it only sends deals newer than what
  the server already has.
- **Account key.** Your data is filed under `MT5_<your login number>`.
- **Your password** is stored in `mt5_agent_config.json` in this folder, on
  your machine only. Keep the folder to yourself.
- **Symbols.** Broker suffixes (`XAUUSD.pro`, `EURUSD.m`) are normalised so
  your stats line up. Balance/deposit rows are ignored.
- The program contains no secrets — only the public TradeLogger URL.
