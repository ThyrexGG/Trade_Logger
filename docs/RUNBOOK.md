# RUNBOOK — running TradeLogger locally & operating the live deploy

Every command runs from the project root `C:\Users\Asus\Desktop\Trade_Logger`
in **PowerShell**, unless it says otherwise. `python` = your Python 3.14.

---

## 0. One-time PowerShell fix (for `npm`)

If `npm` says *"running scripts is disabled on this system"*:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 1. Run it locally

You need **two terminals**. The frontend dev server proxies `/api/*` to the
backend on port **8010**.

### Terminal A — backend

**Multi-user mode** (email + password, what production uses):

```powershell
$env:TL_AUTH_MODE          = "multiuser"
$env:TL_OWNER_EMAIL        = "tesbonnathyrak@gmail.com"
$env:TL_SIGNUP_ALLOWLIST   = "tesbonnathyrak@gmail.com,tesbonnathyrak+friend@gmail.com"
$env:TL_AUTH_COOKIE_SECURE = "0"        # localhost is http, not https
$env:TL_AUTH_MAX_ATTEMPTS  = "1000"     # don't lock yourself out while testing
python -m uvicorn api.main:app --port 8010
```

**Single-user / passphrase mode** (the old behaviour):

```powershell
$env:TL_AUTH_MODE = "passphrase"
$env:TL_AUTH_PASSWORD = "whatever-you-want"
python -m uvicorn api.main:app --port 8010
```

**No auth at all** (fastest for pure feature work): don't set any `TL_AUTH_*`.

`$env:` vars last only for that terminal. Paste the whole block each time, or
put them in `.env` (see §5).

### Terminal B — frontend

```powershell
cd frontend
npm run dev
```

Opens `http://localhost:5173`. For multi-user mode the file
`frontend/.env.local` must contain `VITE_AUTH_MODE=multiuser` (already there;
delete the file to go back to the passphrase screen).

Stop either server with **Ctrl+C**.

---

## 2. Database (Neon)

`DATABASE_URL` in `.env` points the app at Neon. Check what migration state
the DB is in:

```powershell
python -m alembic current          # should print 0004_native_auth_columns (head)
python -m alembic upgrade head      # apply anything pending
python -m alembic history           # list all migrations
```

Per-table row counts / DB size:

```powershell
python check_db_size.py
```

---

## 3. User accounts (multi-user mode)

Accounts live in the `users` table on Neon. Invites are the
`TL_SIGNUP_ALLOWLIST` env (comma-separated emails) — an email not on it gets a
"not invited" screen.

**Wipe all accounts** (pre-launch reset, so you can sign up fresh):

```powershell
python tools/reset_users.py
```

**Hand the old single-user `local` rows to the owner** (run once, after the
owner has signed up — Alembic 0003 does this too but only if it hadn't already
run):

```powershell
python tools/reown_local_rows.py tesbonnathyrak@gmail.com
```

---

## 4. Broker sync

**MT5 (local, your own terminal):**

```powershell
python mt5_sync.py
```

**Capital.com (env creds):**

```powershell
python capital_sync.py
```

**The friend push-agent** (also works for you): see `agent/README.md`. Build
the distributable `.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File agent\build_agent.ps1
# -> agent\dist\tradelogger-mt5-sync.exe
```

---

## 5. `.env` — what matters

`.env` is git-ignored. Keys the app reads (there are more; these are the ones
that bite):

| Key | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** URI (`...-pooler...neon.tech/neondb?sslmode=require`) |
| `TL_AUTH_MODE` | `multiuser` (or `passphrase`, or unset) |
| `TL_OWNER_EMAIL` | `tesbonnathyrak@gmail.com` |
| `TL_SIGNUP_ALLOWLIST` | invited emails, comma-separated |
| `TL_CREDENTIAL_ENC_KEY` | Fernet key — `python -m api.broker_credentials` to generate |
| `FMP_API_KEY`, `FRED_API_KEY`, `GEMINI_API_KEY` | market data / AI |

Setting them in `.env` means Terminal A is just `python -m uvicorn api.main:app --port 8010`.

---

## 6. Tests

```powershell
python -m pytest tests/ -q                       # full suite (~7-10 min)
python -m pytest tests/test_stage28_native_auth.py -q   # just W10 auth
python -m pytest tests/ -q -k "auth or tenant or ingest"
```

Known pre-existing failures (not regressions): `test_phase56_data_quality`,
`test_phase68_invariants[as_of2-*]` (×4), `test_phase73_intraday`.

---

## 7. Live deploy

- **Frontend:** Cloudflare Workers — `https://trade-logger.tesbonnathyrak.workers.dev`.
  Auto-builds on `git push` (build = `cd frontend && npm ci && npm run build`).
- **Backend:** Render — `https://tradelogger-api.onrender.com`. Auto-deploys on
  `git push`. Env vars set in the Render dashboard (**not** in git). Sleeps
  after 15 min idle → ~50 s cold start.
- **DB:** Neon. Migrations are run **from your laptop** against the live
  `DATABASE_URL` (`python -m alembic upgrade head`) — Render free has no shell.

**Deploy a change:**

```powershell
git push                     # both services rebuild
python -m alembic upgrade head   # only if you added a migration
```

**Turn multi-user on/off on Render:** set `TL_AUTH_MODE` to `multiuser` or
`passphrase`. Break-glass is always `passphrase` — the app keeps working, data
intact.

**Invite a friend:** add their email to `TL_SIGNUP_ALLOWLIST` on Render, save,
wait for redeploy. Send them the URL (Capital.com) or the `.exe` (MT5).

Full first-time deploy walkthrough: `docs/DEPLOY.md`.
