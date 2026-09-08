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
  Supabase Postgres (free)
```

Why this works without an always-on box: opening the app calls
`/api/system/sync/run-if-stale`, which runs one broker-sync cycle if the last
one is >15 min old (deduplicated server-side). The Positions page also has a
manual **Sync now** button. So a service that sleeps is fine — the only cost is
a ~30-60 s wait the first time you open the app after it has gone idle.

**Trade-off you accepted:** no push notification when a trade closes while the
app is fully closed. (Everything reconciles the next time you open it.)

---

## 1. Supabase — already done

You are already on Supabase Postgres. You need one string:

- Supabase dashboard → your project → **Connect** (top bar) → **Connection
  pooling** → **Transaction** mode → copy the URI. It looks like
  `postgresql://postgres.abcd:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:6543/postgres`
- Replace `[YOUR-PASSWORD]` with your database password.
- Note the **region** in that hostname (e.g. `aws-0-eu-central-1`) — you'll put
  Render in the same region so DB reads are fast.

This URI is `DATABASE_URL` in step 3.

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
   | `DATABASE_URL` | the Supabase pooler URI from step 1 |
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

5. **Settings** → set **Region** to match your Supabase region (step 1), if it
   isn't already. Save (this triggers a redeploy).
6. Wait for **Live**. Test from your phone (wifi off, on cellular):
   ```
   https://tradelogger-api.onrender.com/api/health        → {"status": ...} 200
   https://tradelogger-api.onrender.com/api/watchlist      → 401
   ```
   (Your URL is shown at the top of the Render service page.)

### 3.1 Stamp the database for Alembic (one time)

Render service → **Shell** tab:
```bash
alembic stamp 0001_baseline
alembic current          # -> 0001_baseline (head)
```
From now on, schema changes ride in `alembic/versions/` and the deploy runs
`alembic upgrade head` (see §6).

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

When a change includes a **schema migration**, run this in the Render **Shell**
after the deploy goes Live:
```bash
alembic upgrade head
```
(There are no migrations after the baseline yet, so this is a no-op today.)

---

## 7. Go-live checklist

- [ ] `https://…onrender.com/api/health` → 200 from cellular (wifi off)
- [ ] `https://…onrender.com/api/watchlist` → **401**
- [ ] Pages URL shows the passphrase screen; the right passphrase logs you in and **stays** logged in on reload
- [ ] `TL_ALLOWED_ORIGINS` on Render == the exact Pages origin
- [ ] `DATABASE_URL` uses the Supabase **pooler** host (`...pooler.supabase.com:6543`)
- [ ] Render region == Supabase region
- [ ] `alembic current` → `0001_baseline (head)` in the Render shell
- [ ] Open the app after ~20 min idle → it wakes (~30-60 s) and the "Syncing…" pill appears, then data is current
- [ ] Optional: a free uptime pinger (UptimeRobot, healthchecks.io) hitting `/api/health` every ~10 min keeps the backend warmer and keeps Supabase from idling out

---

## 8. Recovery / break-glass

- **Locked out** (forgot passphrase): Render → Environment → set
  `TL_AUTH_PASSWORD` to a temporary plaintext value, save, wait for redeploy,
  log in, then regenerate a proper `TL_AUTH_PASSWORD_HASH` and remove the
  plaintext one.
- **Auth misbehaving**: set `TL_AUTH_DISABLED=1` on Render → redeploy turns auth
  off entirely. Only do this briefly.
- **Log out every device**: Render **Shell** →
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
| Supabase | Free project pauses after 7 days with **zero** activity | The uptime pinger's DB-touching routes, or just opening the app, keeps it alive |

---

## 10. Alternative: one small VPS instead of two free services

If the 512 MB / cold-start limits get annoying, the whole thing also runs on a
single ~€3.79/mo Hetzner VM (PayPal, no capacity lottery): `uvicorn` behind
Caddy for HTTPS, `frontend/dist` served as static files by the same Caddy, and
you can turn the **auto-sync toggle** on so sync is continuous again. Ask and
this guide gets a VPS section — the app doesn't change.
