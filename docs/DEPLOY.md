# TradeLogger — Deploy Guide (free stack)

Take TradeLogger from localhost to a private URL you can open on your phone,
over HTTPS, behind a passphrase. Supersedes the old `deployment_guide.md`
(`streamlit run app.py`), which no longer applies.

**Prerequisites done:** W1 (AI tools), W2 (Streamlit retired — backend is
Linux-clean), W3 (auth). This guide is W6 (migrations) + W7 (hosting).

---

## 0. The shape of it

```
  Phone / laptop browser
          │  https://app.<you>
          ▼
  Cloudflare  ──(proxied DNS, free TLS)──►  Oracle Cloud "Always Free" VM
  Pages (static React build)                 ├─ Caddy   :443  → uvicorn :8010
                                             ├─ FastAPI (api.main:app)
          │  https://api.<you>               └─ sync loop (thread in the API)
          └───────────────────────────────────────────┘
                                                       │
                                                       ▼
                                               Supabase Postgres (free)
```

Cost: **$0/mo** (a domain is ~$10/yr and optional — you can use the Pages
subdomain and the VM's IP + a free hostname).

Two hosts, on purpose:
- **Cloudflare Pages** serves the built React files (`frontend/dist`). Global CDN, instant.
- **Oracle Cloud VM** runs the Python backend *and* the always-on data-collection
  loop (the reason a sleeping free tier like Render won't do).

---

## 1. Supabase — already done

You're already on Supabase Postgres. Just make sure:
- The VM will reach it: Supabase → Project Settings → Database → "Connection
  pooling" string. Use the **pooler** URI (port 6543).
- Copy that URI — it goes in the VM's `.env` as whatever var `database.py` reads
  (check your current local `.env`).

Backups: Supabase's free tier keeps automated daily backups for 7 days. Good
enough to start. (Optional later: a weekly `pg_dump` to object storage.)

---

## 2. Oracle Cloud — the free VM

### 2.1 Create the account
1. https://www.oracle.com/cloud/free/ → "Start for free".
2. It asks for a card for identity verification — **Always Free** resources are
   never charged; you can also set the account to stay on the free tier only.
3. Pick a home region close to you (this can't be changed later).

### 2.2 Create the instance
1. Console → **Compute → Instances → Create instance**.
2. Name: `tradelogger`.
3. Image & shape → **Change shape** → **Ampere** → `VM.Standard.A1.Flex`.
   Set **1 OCPU / 6 GB RAM** (well within the Always Free 4 OCPU / 24 GB pool).
   - If Ampere capacity is unavailable in your region, fall back to
     `VM.Standard.E2.1.Micro` (AMD, 1 GB) — enough for the backend, tight for
     builds. Ampere is strongly preferred.
4. Image: **Canonical Ubuntu 22.04** (or 24.04).
5. **Add SSH keys** → "Generate a key pair for me" → **download both** the
   private and public key. Keep the private key safe.
6. Networking: leave "Create new VCN" — it makes a public subnet.
7. **Create.** Wait ~1 min; note the **public IP**.

### 2.3 Open the firewall (do BOTH — Oracle has two layers)
1. **Security list** (cloud firewall): VCN → your subnet → default security list
   → Add Ingress Rules:
   - Source `0.0.0.0/0`, TCP, dest port **443** (and **80** for the TLS challenge).
   - Leave 22 as it is (SSH).
   - Do **not** open 8010 — only Caddy is public.
2. **OS firewall** (on the box, later in step 3.5).

### 2.4 First SSH in
```bash
chmod 600 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<PUBLIC_IP>
```

---

## 3. Provision the VM

All commands run **on the VM** as `ubuntu`.

### 3.1 System packages
```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install python3-venv python3-pip git curl ufw
```

### 3.2 Get the code
```bash
cd ~
git clone https://github.com/ThyrexGG/Trade_Logger.git
cd Trade_Logger
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt        # NOT the -streamlit-legacy one
```

### 3.3 The `.env`
```bash
cp .env.example .env
nano .env
```
Set:
- The Supabase pooler URI (whatever var your local `.env` uses).
- `CAPITAL_*` — your Capital.com credentials (for the sync loop).
- `GEMINI_API_KEY` — for the assistant.
- `MACRO_DATA_PROVIDER=fred`, `FRED_API_KEY=...`, `MACRO_COT_PROVIDER=cftc`,
  `MACRO_CALENDAR_PROVIDER=forexfactory`, `FMP_API_KEY=...` (as you run locally).
- **Auth (required before it's public):**
  ```bash
  .venv/bin/python -m api.auth      # prompts for a passphrase, prints the hash
  ```
  Paste the printed `TL_AUTH_PASSWORD_HASH=...` line into `.env`.
- `TL_ALLOWED_ORIGINS=https://<your Pages URL>` (fill in after step 4).
- `TL_AUTH_COOKIE_SECURE=1` (you'll be on HTTPS).

Lock it down: `chmod 600 .env`

### 3.4 Smoke test
```bash
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8010
# in another SSH session:
curl -s localhost:8010/api/health
curl -s -o /dev/null -w '%{http_code}\n' localhost:8010/api/watchlist   # expect 401
```
Ctrl-C when happy.

### 3.5 OS firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw --force enable
```

### 3.6 systemd service

The data-collection loop (`api/sync_service.py`) runs **inside the API process**
as a background thread — it comes up automatically on boot when the "auto-sync"
toggle in the Positions header has been left on (the setting is stored in the DB,
`sync_auto_enabled`). So there is just **one** service to run:

`/etc/systemd/system/tradelogger-api.service`:
```ini
[Unit]
Description=TradeLogger API + sync loop
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Trade_Logger
EnvironmentFile=/home/ubuntu/Trade_Logger/.env
ExecStart=/home/ubuntu/Trade_Logger/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8010
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tradelogger-api
systemctl status tradelogger-api --no-pager
journalctl -u tradelogger-api -f          # watch logs
```

After first login to the deployed app, flip **auto-sync on** in the Positions
header once; it then persists and restarts with the service.

### 3.7 Caddy (HTTPS reverse proxy)
```bash
sudo apt -y install debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudflare.com/...'   # or use the official Caddy repo:
# https://caddyserver.com/docs/install#debian-ubuntu-raspbian
sudo apt -y install caddy
```
`/etc/caddy/Caddyfile`:
```
api.<yourdomain> {
    reverse_proxy 127.0.0.1:8010
}
```
```bash
sudo systemctl reload caddy
```
Caddy gets a Let's Encrypt cert automatically once DNS points here (step 5).
No domain yet? Use `https://<PUBLIC_IP>.nip.io` as the host in the Caddyfile —
works for a quick start, but a real domain + Cloudflare is the better path.

---

## 4. Frontend on Cloudflare Pages

1. Push is already on GitHub. Cloudflare dashboard → **Workers & Pages → Create →
   Pages → Connect to Git** → pick `Trade_Logger`.
2. Build settings:
   - Framework preset: **Vite**
   - Build command: `npm run build`
   - Build output directory: `frontend/dist`
   - Root directory: `frontend`
   - Environment variable: `VITE_API_BASE_URL = https://api.<yourdomain>`
3. Deploy. You get `https://trade-logger-xxx.pages.dev`.
4. Go back to the VM `.env`: set
   `TL_ALLOWED_ORIGINS=https://trade-logger-xxx.pages.dev` (and your custom
   domain if you add one), then `sudo systemctl restart tradelogger-api`.

---

## 5. Domain + Cloudflare (recommended, optional)

1. Buy a domain (Cloudflare Registrar is at-cost, ~$10/yr) or move an existing
   one's nameservers to Cloudflare (free plan).
2. DNS records (both **Proxied**, orange cloud):
   - `A   api   <VM PUBLIC IP>`
   - `CNAME app  trade-logger-xxx.pages.dev`  (or use Pages' custom-domain UI)
3. SSL/TLS mode: **Full (strict)**.
4. Update `Caddyfile` host to `api.<yourdomain>`, reload Caddy.
5. Update Pages env var + `TL_ALLOWED_ORIGINS` to `https://app.<yourdomain>`.

### 5.1 Cloudflare Access (second lock — do this)
Zero Trust → Access → Applications → Add:
- Self-hosted, domain `api.<yourdomain>` **and** `app.<yourdomain>`.
- Policy: Allow, rule = **Emails** → `tesbonnathyrak@gmail.com`.
Now only your email (one-time PIN or Google login) can reach the origin at all —
on top of the app's own passphrase. Belt and braces.

---

## 6. Migrations (W6) — before/around first deploy

Today the schema is built by `CREATE TABLE IF NOT EXISTS` at boot, which is fine
for a fresh DB but can't do renames/constraint changes safely. Introduce Alembic:

1. `pip install alembic` (add to `requirements.txt`).
2. `alembic init alembic`; point `sqlalchemy.url` at the Supabase URI (env).
3. `alembic revision --autogenerate -m "0001 baseline"` against the **live**
   Supabase schema, then `alembic stamp head` (mark it applied without running).
4. From then on: schema changes = a new revision; deploy step runs
   `alembic upgrade head`.
5. Keep the boot-time `CREATE TABLE IF NOT EXISTS` as the fresh-SQLite path only.

*(This section is a stub — W6 is not built yet. Do it before the schema needs
its first real change post-deploy.)*

---

## 7. Deploy / update routine

```bash
ssh ubuntu@api.<yourdomain>
cd ~/Trade_Logger
git pull
.venv/bin/pip install -r requirements.txt
# alembic upgrade head        # once W6 exists
sudo systemctl restart tradelogger-api
journalctl -u tradelogger-api -n 50 --no-pager
```
Frontend redeploys automatically on push (Cloudflare Pages watches the repo).

---

## 8. Checklist before you call it live

- [ ] `curl https://api.<you>/api/health` → 200 from your phone's cellular (wifi off)
- [ ] `curl https://api.<you>/api/watchlist` → **401**
- [ ] The app URL shows the passphrase screen, and the right passphrase gets you in
- [ ] `TL_AUTH_COOKIE_SECURE=1`, `TL_ALLOWED_ORIGINS` set to the real origin
- [ ] `.env` is `chmod 600`, not in git (`git status` clean)
- [ ] Cloudflare Access policy active on both hostnames
- [ ] `systemctl is-enabled tradelogger-api` → `enabled`
- [ ] Reboot the VM once; confirm the service comes back and the sync loop ticks
- [ ] UptimeRobot / healthchecks.io pinging `/api/health` every 5 min

---

## 9. Recovery / break-glass

- **Locked out of the app** (forgot passphrase): SSH in, `nano .env`, set a new
  `TL_AUTH_PASSWORD=temporary-thing`, `sudo systemctl restart tradelogger-api`,
  log in, then regenerate a proper hash.
- **Auth misbehaving**: `TL_AUTH_DISABLED=1` in `.env` + restart turns it off
  entirely (do this only behind Cloudflare Access).
- **Log out every device**: `.venv/bin/python -c "from api import auth; print(auth.revoke_all_sessions())"`
- **Bad deploy**: `git reset --hard <last good sha>` + restart. Frontend: roll
  back the deployment in the Cloudflare Pages UI.
