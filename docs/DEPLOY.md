# TradeLogger — Deploy Guide (free, no card)

Take TradeLogger from localhost to a private URL you can open on your phone,
over HTTPS, behind a passphrase — for **$0**, with **no credit card** anywhere.

**Prerequisites (all done):** W1 (AI tools), W2 (Streamlit retired — backend is
Linux-clean), W3 (auth), W6 (Alembic migrations), plus the *sync-on-open*
change so the backend does **not** need to be always-on.

---

## 0. The shape of it

```
  Phone / laptop browser
        │  https://<project>.pages.dev
        ▼
  Cloudflare Pages  ── static React build (frontend/dist), global CDN, no sleep
        │
        │  fetch  https://tradelogger-api.onrender.com/api/*   (credentials: include)
        ▼
  Render (free web service)  ── FastAPI (api.main:app)
        │                        sleeps after 15 min idle, wakes on request (~30-60 s)
        │                        broker sync runs on "app open if stale" + the manual button
        ▼
  Neon Postgres (free)  ── scale-to-zero after 5 min idle, ~0.5 s wake
```

> **DB note (2026-09-09):** the database moved from Supabase to **Neon**.
> Supabase's free tier meters egress at 5 GB/mo, which a polling backend blows
> through; Neon doesn't meter egress. Supabase is kept only for a future
> multi-user Auth phase (W8), not for data. The migration script is
> `migrate_to_neon.py` (gitignored). Neon free storage is 0.5 GB, so the
> `historical_candles` cache is **not** on Neon — backtests need a scoped
> re-ingest (`python -m market_data_ingest`).

Why this works without an always-on box: opening the app calls
`/api/system/sync/run-if-stale`, which runs one broker-sync cycle if the last
one is >15 min old (deduplicated server-side). The Positions page also has a
manual **Sync now** button. So a service that sleeps is fine — the only cost is
a ~30-60 s wait the first time you open the app after it has gone idle.

**Trade-off you accepted:** no push notification when a trade closes while the
app is fully closed. (Everything reconciles the next time you open it.)

---

## 1. Neon Postgres — the database

- [neon.tech](https://neon.tech) → sign in with GitHub (no card) → **New project**.
- Region: match your Render region (see step 5) so DB reads are fast.
- On the project page, **Connection string** panel → copy the **pooled** URI
  (host contains `-pooler`). It looks like
  `postgresql://neondb_owner:xxx@ep-name-pooler.<region>.aws.neon.tech/neondb?sslmode=require`
- The connection pool in `database.py` validates idle sockets with `SELECT 1`,
  so Neon's scale-to-zero is handled transparently (first query after idle
  waits ~0.5 s).

This URI is `DATABASE_URL` in step 3.

**Migrating from an existing DB:** set `DEST_DATABASE_URL` to the new URI and run
`python migrate_to_neon.py` (dry run), then `--run`. It copies the `public`
schema, skips `historical_candles`, and is safe to re-run.

---

## 2. First, generate your passphrase hash (locally)

On your PC, in the project folder:

```bash
python -m api.auth
```

It prompts for a passphrase (pick a strong one — this is your app login) and
prints a line like:

```
TL_AUTH_PASSWORD_HASH=scrypt$<salt>$<hash>
```

Copy that whole value (everything after the `=`). It's `TL_AUTH_PASSWORD_HASH`
in step 3. The plaintext passphrase is never stored anywhere.

---

## 3. Backend on Render (free)

Render free web services **do not require a credit card**.

1. Go to **render.com** → sign up / log in **with GitHub**.
2. **New +** → **Blueprint** → connect your GitHub → pick the **Trade_Logger**
   repo. Render reads `render.yaml` and proposes one service, `tradelogger-api`.
3. Click **Apply**. The first build takes ~5-10 min (installing pandas / scipy /
   scikit-learn). It will **fail to start** until you add the secrets — that's
   expected, do the next step.
4. Open the **tradelogger-api** service → **Environment** → add these
   (the non-secret ones came from `render.yaml` already):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon pooled URI from step 1 |
   | `TL_AUTH_PASSWORD_HASH` | the hash from step 2 |
   | `TL_ALLOWED_ORIGINS` | *leave blank for now — you fill it in step 5* |
   | `CAPITAL_API_KEY` | from your local `.env` |
   | `CAPITAL_EMAIL` | " |
   | `CAPITAL_PASSWORD` | " |
   | `CAPITAL_ACCOUNT_ID` | " |
   | `CAPITAL_IS_DEMO` | `true` or `false`, same as local |
   | `GEMINI_API_KEY` | from local `.env` (optional — AI page is off without it) |
   | `FRED_API_KEY` | from local `.env` |
   | `FMP_API_KEY` | from local `.env` (optional) |

5. **Settings** → set **Region** to match your Neon region (step 1), if it
   isn't already. Save (this triggers a redeploy).
6. Wait for **Live**. Test from your phone (wifi off, on cellular):
   ```
   https://tradelogger-api.onrender.com/api/health        → {"status": ...} 200
   https://tradelogger-api.onrender.com/api/watchlist      → 401
   ```
   (Your URL is shown at the top of the Render service page.)

### 3.1 Stamp the database for Alembic (one time)

Render's **Shell is a paid feature**, so migrations are run **from your PC**
against the same database (your local `.env` already has the `DATABASE_URL`):

```bash
# on your machine, in the project folder
alembic stamp 0001_baseline
alembic current          # -> 0001_baseline (head)
```

This writes one bookkeeping row. From now on, schema changes ride in
`alembic/versions/` and you run `alembic upgrade head` locally after pushing
them (see §6).

---

## 4. Frontend on Cloudflare Pages (free)

Cloudflare Pages **does not require a credit card**.

1. **dash.cloudflare.com** → sign up / log in → **Workers & Pages** → **Create**
   → **Pages** → **Connect to Git** → pick **Trade_Logger**.
2. Build settings:
   | Field | Value |
   |---|---|
   | Framework preset | **Vite** |
   | Build command | `npm run build` |
   | Build output directory | `dist` |
   | Root directory (Advanced) | `frontend` |
3. **Environment variables** → add:
   | Key | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://tradelogger-api.onrender.com` (your Render URL, no trailing slash) |
4. **Save and Deploy**. ~2 min. You get `https://<project>.pages.dev`.

---

## 5. Connect the two

1. Copy your Pages URL (e.g. `https://trade-logger-abc.pages.dev`).
2. Render → tradelogger-api → **Environment** → set
   `TL_ALLOWED_ORIGINS` = that URL (exactly, `https://`, no trailing slash).
   Save → wait for the redeploy to go **Live**.
3. Open the Pages URL. You should get the **passphrase screen** → enter your
   passphrase → you're in.

If login "succeeds" but bounces straight back to the passphrase screen, the
cross-site cookie isn't sticking — re-check `TL_ALLOWED_ORIGINS` is the exact
Pages origin and that `TL_AUTH_COOKIE_SAMESITE=none` is set on Render (it's in
`render.yaml`, so it should be).

---

## 6. Deploy / update routine

Both hosts auto-deploy on every push to `main`:

- **Cloudflare Pages** rebuilds the frontend automatically.
- **Render** rebuilds the backend automatically.

When a change includes a **schema migration**, run this **from your PC** (Render
free has no shell) right after pushing, before or just as the deploy goes Live:
```bash
git pull                 # get the new alembic/versions/ file
alembic upgrade head     # applies it to Neon
```
(There are no migrations after the baseline yet, so this is a no-op today.)

---

## 7. Go-live checklist

- [ ] `https://…onrender.com/api/health` → 200 from cellular (wifi off)
- [ ] `https://…onrender.com/api/watchlist` → **401**
- [ ] Pages URL shows the passphrase screen; the right passphrase logs you in and **stays** logged in on reload
- [ ] `TL_ALLOWED_ORIGINS` on Render == the exact Pages origin
- [ ] `DATABASE_URL` uses the Neon **pooled** host (`...-pooler...neon.tech`)
- [ ] Render region == Neon region
- [ ] `alembic current` (run locally) → `0001_baseline (head)`
- [ ] Open the app after ~20 min idle → it wakes (~30-60 s) and the "Syncing…" pill appears, then data is current
- [ ] Optional: a free uptime pinger (UptimeRobot, healthchecks.io) hitting `/api/health` every ~10 min keeps the backend warmer — it does not touch the DB, so it won't burn Neon compute hours

---

## 8. Recovery / break-glass

- **Locked out** (forgot passphrase): Render → Environment → set
  `TL_AUTH_PASSWORD` to a temporary plaintext value, save, wait for redeploy,
  log in, then regenerate a proper `TL_AUTH_PASSWORD_HASH` and remove the
  plaintext one.
- **Auth misbehaving**: set `TL_AUTH_DISABLED=1` on Render → redeploy turns auth
  off entirely. Only do this briefly.
- **Log out every device**: run from your PC (same `DATABASE_URL`) →
  `python -c "from api import auth; print(auth.revoke_all_sessions())"`
- **Bad backend deploy**: Render → the service → **Deploys** → find the last
  good one → **Redeploy**.
- **Bad frontend deploy**: Cloudflare Pages → **Deployments** → last good one →
  **Rollback**.

---

## 9. Known limits of the free tier

| Thing | Reality | If it bites |
|---|---|---|
| Cold start | ~30-60 s the first open after 15 min idle | An uptime pinger (§7) hides most of it |
| Backend RAM | Render free = 512 MB. The app + pandas/scipy/sklearn is close to that; a heavy backtest could OOM and restart | Move the backend to Render **Starter** ($7/mo, 512 MB→ more) or a small VPS. Nothing else changes. |
| Build minutes | Render free = 500 build-min/mo; a build is ~8 min | ~60 deploys/month — fine |
| Neon | Compute scales to zero after 5 min idle; ~192 compute-hrs/mo on free; 0.5 GB storage | Fine for normal use. Don't run a 24/7 loop that queries the DB every few minutes — it keeps the compute awake and burns the monthly hours. `historical_candles` stays off Neon (size). |

---

## 10. Multi-user — inviting friends (W10, optional)

The single-user passphrase deploy above is the default. To let a handful of
invited people each track their own trades on the one instance, switch auth to
**multiuser** — first-party email + password, no third party. Identity lives in
the same Neon database as everything else; sessions are the same opaque cookie
the passphrase gate already uses.

1. **Render** — add three env vars:
   - `TL_AUTH_MODE` = `multiuser`
   - `TL_OWNER_EMAIL` = your email (gets the `owner` role + the admin surface)
   - `TL_SIGNUP_ALLOWLIST` = comma-separated invited emails, **including yours**
   - (optional) `TL_CREDENTIAL_ENC_KEY` = output of `python -m api.broker_credentials`
     — only if friends will connect their own Capital.com account. Save a copy.

   Nothing else. No external service, no keys to rotate.
2. **Frontend** — `frontend/.env.production` already sets `VITE_AUTH_MODE=multiuser`.
   If it's still `passphrase` on your branch, set it, commit, push.
3. **Sign up as owner** — open the app, **Create account**, register with your
   `TL_OWNER_EMAIL`. You're in as owner.
4. **Re-own your history** — once, after step 3, locally with `.env`
   `DATABASE_URL` pointing at Neon: `python -m alembic upgrade head`. Migration
   `0003` moves the old `local` rows onto your account; `0004` adds the auth
   columns (a no-op if the app booted first).

Break-glass: set `TL_AUTH_MODE` back to `passphrase` on Render — instant return
to the single shared-passphrase app, all data intact.

Each user then adds their Capital.com connection under **Operations →
Connections** (encrypted at rest), or runs the MT5 agent (§11); sync-on-open
and the auto-sync toggle are per-user. The owner sees everyone at
`GET /api/admin/users` and can disable an account
(`POST /api/admin/users/<id>/disable`, effective within ~30 s).

Passwords are scrypt-hashed; sign-in and sign-up are per-IP rate-limited. A
disabled account is locked out on its next request.

**Before sharing the URL:** run `/code-review ultra` on the branch.

---

## 11. MetaTrader friends — the MT5 push agent (W9, optional)

Capital.com connects to the hosted server directly (§10). MetaTrader brokers
(**Exness**, IC Markets, Pepperstone, most prop firms) can't: the `MetaTrader5`
library only talks to a terminal on the *same Windows machine*, and Render is
Linux. So an MT5 friend runs a small agent on their own PC that reads MT5 and
POSTs the data to `POST /api/ingest/mt5`.

- **No server change is needed** — the `/api/ingest` router ships with the
  backend and is gated by the normal auth. It works in every auth mode. Data
  ingestion only, no order path.
- **Build the .exe** (once, on Windows): `agent/build_agent.ps1` →
  `agent/dist/tradelogger-mt5-sync.exe`. The public API URL is baked in
  (`CONFIG_DEFAULTS` in `agent/mt5_push_agent.py`) — update it and rebuild if
  the URL changes. Host the .exe wherever friends can download it (GitHub
  Releases, a drive); it contains no secrets.
- **The friend** double-clicks the .exe, types their TradeLogger email +
  password. The wizard writes `mt5_agent_config.json`, installs a
  Task-Scheduler job (`schtasks` + a hidden VBS launcher, every 15 min), and
  does a first sync. Full friend-facing steps: `agent/README.md`.
- Their trades land under account key `MT5_<their login>`. Ids from a friend's
  push are tenant-prefixed internally, so two friends with the same MT5 login
  number on different brokers never collide. The owner's local `mt5_sync.py` is
  unchanged (ids stay un-prefixed).

The owner can also run the agent (`--daemon`, or the wizard) instead of
`mt5_sync.py` — same endpoint. Advanced/manual setup and the single-user
passphrase path are in `agent/mt5_agent_config.example.json`.

---

## 12. Alternative: one small VPS instead of two free services

If the 512 MB / cold-start limits get annoying, the whole thing also runs on a
single ~€3.79/mo Hetzner VM (PayPal, no capacity lottery): `uvicorn` behind
Caddy for HTTPS, `frontend/dist` served as static files by the same Caddy, and
you can turn the **auto-sync toggle** on so sync is continuous again. Ask and
this guide gets a VPS section — the app doesn't change.
