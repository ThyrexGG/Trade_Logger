# TradeLogger MT5 Push Agent

For people on a **MetaTrader 5** broker (Exness, IC Markets, Pepperstone, most
prop firms). TradeLogger's hosted server runs on Linux and can't reach an MT5
terminal directly, so this small script runs on **your** Windows PC, reads MT5,
and sends your trade history to the server over HTTPS.

**What it does:** reads your closed deals, open positions and balance, POSTs
them to the server.
**What it does not do:** it never places, changes or closes a trade. There is
no order path. It only ever writes your own data.

---

## 1. Install

You need the MT5 **terminal** installed and Python 3.9+.

```powershell
pip install MetaTrader5 requests
```

## 2. Configure

```powershell
copy mt5_agent_config.example.json mt5_agent_config.json
notepad mt5_agent_config.json
```

Fill in:

| Field | Where it comes from |
|---|---|
| `server_url` | The TradeLogger URL the owner gave you (e.g. `https://tradelogger.onrender.com`) |
| `supabase_url`, `supabase_anon_key` | The owner sends these (they're public values) |
| `email`, `password` | The login **you** created on the TradeLogger sign-in page |
| `poll_minutes` | How often to sync (15 is fine) |

If the owner is still on the **single shared passphrase** (no sign-in page),
delete the four Supabase/email lines and set `"passphrase"` instead
(rename `"__passphrase"` to `"passphrase"`).

The `mt5` block is only needed if your terminal is **not** already open and
logged in. If MT5 is running with your account, leave `login` as `0`.

## 3. Test

Open your MT5 terminal and log in to the account you want to track, then:

```powershell
python mt5_push_agent.py --check      # config + login + MT5 connection
python mt5_push_agent.py --once       # one real sync
```

Your trades should appear in TradeLogger within a minute. The first run pulls
your full history (back to 2020) and can take a little longer.

## 4. Keep it running

```powershell
powershell -ExecutionPolicy Bypass -File .\register_task.ps1
```

This registers a Windows scheduled task that runs `--once` every 15 minutes
while you're logged in. Remove it with:

```powershell
Unregister-ScheduledTask -TaskName "TradeLogger MT5 Push Agent" -Confirm:$false
```

Or skip the task and just leave a terminal open with:

```powershell
python mt5_push_agent.py --daemon
```

---

## Notes

- **Incremental.** After the first run the agent asks the server for the
  timestamp of your newest stored deal and only sends newer ones.
- **Account key.** Your data is filed under `MT5_<your login number>`. Running
  the agent from two PCs for the same MT5 account is fine — it's idempotent.
- **Security.** `mt5_agent_config.json` holds your password. Keep it on your
  own machine; it is git-ignored in this repo and should never be shared.
- **Symbols.** Broker suffixes (`XAUUSD.pro`, `EURUSD.m`) are normalised
  server-side so your stats line up with everyone else's.
- **Balance/deposit rows** and non-trade deal types are ignored automatically.
