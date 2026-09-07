# TradeLogger — Web / Mobile / Online Platform Plan

*Planning document. No code yet. Written 2026-09-07.*

The goal: take TradeLogger from a **localhost research/journal terminal** to a
**private, online, mobile-usable** one — reachable from a phone, authenticated,
always-on for data collection — **without** changing what the system fundamentally
is or weakening any safety invariant.

This plan supersedes the ad-hoc "System Architecture & Web Gap Analysis" note:
several items in that note are already done (see Appendix A), and its framing as
an *institutional multi-user execution platform* is wrong for a solo operator.

---

## 0. Non-negotiable guardrails (these do not change)

| Invariant | Stays true |
|---|---|
| **Read-only** | No `POST /orders`, no order modify/cancel, no broker transmission. `LIVE_AUTOMATION_ENABLED = False`, `LIVE_BROKER_TRANSMISSION = "BLOCKED"`. Going online must not add an execution path. |
| **Frozen execution/research layer** | `PHASE_21_XAUUSD_STRATEGY_CONTRACT.md` + the sealed holdout stay byte-immutable and unread. No workstream here touches `execution_pipeline`, `risk_gateway`, `broker_adapter`, or the frozen contracts. |
| **Never fabricate** | Missing data stays `INSUFFICIENT_EVIDENCE` / `UNAVAILABLE`, never a made-up number. Applies to any new AI tool output too. |
| **Auth protects data, not trading** | There is nothing to "trade" through the API. Auth exists so private financial history isn't world-readable once the port is exposed. |

---

## 1. Current state (what this plan builds on)

Already shipped (recent sessions), so the plan starts here:

- **Interactive candlestick chart** — `PriceChart.tsx` (lightweight-charts 4.2.3) on the Market page. Binance real-time for crypto, Yahoo delayed for FX/metals, liveness-labelled.
- **Manual broker sync** — "Sync now" button + auto-sync toggle on the Positions header (`/api/system/sync`).
- **MT5 retired from the web** — env-only opt-in (`MT5_ENABLED=1`), dormant by default. The web no longer needs a running `terminal64.exe`. Capital.com is the live account link.
- **Macro data** — FRED coverage expanded (PPI, JOLTS, industrial production, durable goods, housing starts); ForexFactory calendar + upcoming consensus; cross-asset scorecard (DXY, US10Y, JP225, BTC, ETH); seasonality via a 10y daily candle backfill.
- **Journal** — DB-backed, screenshot upload (in-DB), star ratings, free-standing notes, per-setup-tag track record, calendar day-panel integration.
- **AI assistant** — read-only, context cached + background-warmed (~1–2s replies), usage meter, model configurable (`gemini-3.5-flash`).
- **DB** — Supabase Postgres (`is_postgres() == True`), pooled, SQLite fallback.

---

## 2. Workstreams

Seven workstreams. Each is independently shippable; §3 gives the recommended order.

Effort scale: **S** ≈ up to a day · **M** ≈ 2–4 days · **L** ≈ 1–2 weeks.

---

### W1 — AI Assistant: tool-calling (dynamic queries)

**Status: SHIPPED (2026-09-07).** SDK migrated to `google-genai`; 5 read-only
allowlisted tools live (`query_trades`, `analytics_period`, `tag_record`,
`macro_scorecard`, `journal_search`) via `api/ai_tools.py`; manual tool loop in
`api/gemini_client.generate()` (max 4 rounds, then a forced text answer);
per-call audit (`tool_calls: [{tool, args, ms, ok}]`) surfaced in the chat UI as
a "Looked up:" chip row. `run_backtest` deferred (D8). Tests:
`tests/test_stage16_ai_tools.py` + updated `test_stage15c`.

**Why.** Today the assistant answers only from a fixed context snapshot. It
cannot answer *"my average loss on GBPUSD during the London session"* or
*"run a 20-trade backtest on USDJPY"*. This is the single highest-value upgrade —
it turns the assistant from a summariser into something you actually reach for.

**Scope.**
- Enable Gemini function-calling (works on `gemini-3.5-flash`; needs a bump to the
  newer SDK — `google-genai`, since `google.generativeai` is deprecated).
- Define a small set of **read-only, allowlisted tools**, each a thin wrapper over
  code that already exists:
  1. `query_trades(symbol?, session?, direction?, tag?, date_from?, date_to?)` → filtered closed-trade stats (n, win%, expectancy, avg win/loss).
  2. `tag_record(tag)` → the per-tag track record (already an endpoint).
  3. `macro_scorecard(instrument)` → the EdgeFinder scorecard for an instrument.
  4. `run_backtest(strategy, symbol, timeframe, params?)` → the existing backtester, offline path only, capped runtime.
  5. `analytics_period(window)` → performance over day/week/month/quarter.
  6. `journal_search(query)` → full-text over notes / entries.
- Each tool: validates inputs, has a hard timeout, returns structured JSON, and
  **cannot write, execute, or reach the broker**. The tool registry is a
  hard allowlist — the model cannot call anything not on it.
- A short audit line per tool call (tool + args + duration) in the response meta
  so you can see what it did.

**Key decisions.**
- Migrate to `google-genai` SDK now (needed for clean function-calling + it's the
  only supported one). Contained change to `api/gemini_client.py`.
- Tool budget: start with the 6 above; add on demand.
- `run_backtest` is the risky one (slow, wide surface) — gate it behind a
  per-conversation call cap and a timeout, or ship W1 without it first.

**Effort.** M (SDK migration S + 6 tools M).
**Risk.** Low for read tools. Backtest tool needs guardrails. No safety-invariant risk.
**Depends on.** Nothing. Can start immediately.

---

### W2 — Decouple Streamlit from the backend

**Why.** `import api.main` transitively imports `streamlit` — confirmed. Module-level
`import streamlit as st` lives in `trading_workspace_cockpit.py`,
`user_preferences.py`, `market_intelligence_command_center.py` (and others). The
FastAPI server literally will not boot without `streamlit` installed. This blocks
a clean Linux/container deployment (W7) and bloats the runtime.

**Scope.**
- Trace the exact import chain from `api.main` to the first streamlit import
  (likely via one shared module pulled for a helper function).
- For each offending module, one of:
  - **Lazy-import** streamlit inside the functions that use it (fastest, lowest risk).
  - **Extract** the pure domain logic the API needs into a streamlit-free module,
    leaving the Streamlit view as a thin consumer.
- Add a CI check / test: `import api.main` in a venv **without** streamlit installed → must succeed.
- Move `streamlit` to an optional/`dev` dependency group.

**Key decisions.**
- Lazy-import vs extract — decide per module. Extract where the API needs
  non-trivial logic; lazy-import where it's a leaf.
- Do we keep the Streamlit terminal alive at all? (See §4 open decisions.) If it's
  being fully retired, this becomes "delete", not "decouple" — much simpler.

**Effort.** M (S if the answer is "retire Streamlit"; M if "keep it, just decouple").
**Risk.** Low — mechanical, well-tested surface. Regression risk on the Streamlit
side only, which matters only if Streamlit stays.
**Depends on.** Nothing. Should land before W7.

---

### W3 — Authentication, sessions & security hardening

**Why.** `APP_PIN` (a single env var) is fine for localhost. The moment the port
is reachable from the internet (the whole point of "going online"), anyone who
finds it can read every trade, P&L figure, journal note, and see which providers
are configured. This is now a **P0 blocker for going online**, not a P2.

**Scope.**
- **Auth model — single-user, token-based** (not multi-user; there is one of you):
  - A login endpoint that takes a strong passphrase (replaces the 4-digit PIN),
    returns a signed **JWT** (short-lived access token + refresh token, or a long
    opaque session token — decide in §4).
  - `Authorization: Bearer` middleware on every `/api/*` route except `/api/health`
    and the login route.
  - React: an auth context, a login screen, token in memory + refresh in an
    httpOnly cookie, 401 → bounce to login.
- **Transport** — HTTPS only once online (handled by the host / a reverse proxy;
  see W7). No plaintext auth over the internet, ever.
- **Rate limiting** — a simple in-process limiter on the login route (lockout after
  N failures) and a global soft cap. Full WAF is overkill.
- **Secrets** — audit that no endpoint ever returns an API key / token (the macro
  providers panel already redacts; re-verify after W1's tool outputs).
- **CORS** — lock `allow_origins` to the known frontend origin(s) once deployed.
- Optional: **2FA (TOTP)** on login — cheap to add, meaningful for a finance app
  on the public internet.

**Key decisions (see §4).** JWT vs opaque session token; token lifetime; 2FA yes/no;
where the passphrase hash lives (env var of a bcrypt/argon2 hash, or a `users` row).

**Effort.** M.
**Risk.** Medium — auth bugs lock you out or leave a hole. Mitigate with tests for
every route (401 without token, 200 with) and a documented recovery path
(env-var break-glass).
**Depends on.** Decide before W7. Independent of W1/W2.

---

### W4 — Real-time streaming (WebSocket / SSE)

**Why.** Watchlist / positions / prices refresh via 5–30s polling with
`AbortController`. For a *read-only research* tool this is genuinely fine — but on
mobile, many short polls are worse for battery and flaky networks than one held
connection, and multiple tabs multiply the traffic. This is a **nice-to-have that
becomes more attractive on mobile**, not a correctness fix.

**Scope.**
- A single **SSE** endpoint (`GET /api/stream`) that pushes: price ticks for
  watchlist symbols, position P&L updates, alert fires, sync-cycle completion.
  SSE over WebSocket because: one-directional (server→client is all we need),
  works through proxies trivially, auto-reconnects, far simpler.
- Server side: one background task fans out updates to connected clients; the
  existing polling endpoints stay as the fallback and for first paint.
- React: a `useEventStream` hook; pages subscribe to the slices they care about;
  falls back to polling if the stream drops or isn't available.
- Auth: the stream endpoint takes the same bearer token (query param or header).

**Key decisions.** SSE vs WebSocket (recommend SSE). Whether to also stream the
candle chart's last price (nice, small).

**Effort.** M.
**Risk.** Low. Purely additive; polling stays as the floor.
**Depends on.** W3 (the stream must be authed). Not a blocker for anything.

---

### W5 — Mobile / PWA

**Why.** "Go mobile" = usable on a phone browser and installable to the home
screen, working on cellular. The app is a React SPA already, so this is mostly a
responsiveness + PWA-shell pass, not a rewrite.

**Scope.**
- **Responsive audit** — every one of the ~26 pages at 375–430px width:
  tables → card/stack layouts or horizontal scroll containers; the calendar grid;
  the candle chart (touch pan/zoom, sensible default height); nav → a bottom bar
  or drawer on small screens; the AI chat composer.
- **PWA shell** — `manifest.webmanifest` (name, icons, theme colour, `display:
  standalone`), a service worker that caches the app shell for instant load and
  offline "last seen" rendering (data still needs the network — no offline
  writes).
- **Web Push (optional, later)** — a service-worker push subscription so alert
  fires reach you when the tab is backgrounded / phone is locked. Needs VAPID keys
  and a `POST /api/push/subscribe` endpoint storing the subscription per session.
  *In-window audio chimes are explicitly out of scope (your call).*
- **Touch/ergonomics** — larger tap targets, no hover-only affordances (the
  InfoTip tooltips already handle tap), pull-to-refresh where it makes sense.

**Key decisions.** Bottom-nav vs hamburger on mobile. Whether Web Push is in this
round or a follow-up. Icon/splash art.

**Effort.** L (responsive pass is the bulk; PWA shell is S; Web Push is M).
**Risk.** Low. Cosmetic/additive. The risk is scope creep in the responsive pass —
timebox it page-by-page.
**Depends on.** W3 for Web Push. The responsive pass depends on nothing.

---

### W6 — Alembic schema migrations

**Why.** Schema changes today are scattered `CREATE TABLE IF NOT EXISTS` /
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` blocks across many Python files, run at
boot. That works for additive changes but can't do renames, constraint changes,
data backfills, or rollbacks — and there's no record of what shape the DB is
*supposed* to be in.

**Scope.**
- Initialise Alembic against the current Supabase schema (autogenerate a
  baseline "0001_initial" from the live DB, mark it as applied).
- Move future schema changes into versioned migrations; keep the boot-time
  `CREATE TABLE IF NOT EXISTS` as a safety net for fresh local SQLite only, or
  retire it once migrations are the single source of truth.
- A `alembic upgrade head` step in the deploy process (W7).
- Document the baseline schema (supersedes hand-maintained `docs/02_Database_Schema.md`).

**Key decisions.** Do migrations run automatically on deploy or manually? (Recommend
manual for the first few, automatic once trusted.) SQLite-fallback support in
migrations (SQLite's ALTER is limited) — probably declare Postgres-only for
migrations and keep SQLite as best-effort local dev.

**Effort.** M.
**Risk.** Medium — a bad migration on the live DB is painful. Mitigate: always
`--sql` preview first, take a Supabase backup before each, test on a copy.
**Depends on.** Nothing, but most valuable *before* W7 so deploys have a clean
schema step.

---

### W7 — Deployment: online hosting + always-on sync gateway

**Why.** Two separate problems bundled:
1. **Serve the app online** — a URL you can open from your phone, over HTTPS, authed.
2. **Keep data collection running** when your PC is asleep — the auto-sync loop
   (Capital.com reconciliation, macro/calendar refresh, candle ingestion) needs a
   host that's always on.

**Scope.**
- **App hosting.** The backend is Linux-friendly *once W2 lands* (MT5 is already
  retired). Options, cheapest-first:
  - A small always-on Linux VPS (Hetzner / Fly.io / Railway / a $5–10 box):
    runs `uvicorn api.main:app` behind Caddy/nginx for HTTPS + a real domain,
    plus the `auto_sync` loop as a systemd service. Frontend served as static
    files by the same reverse proxy or a CDN (Cloudflare Pages / Netlify).
  - Managed (Render / Railway / Fly.io) — less ops, slightly more $, HTTPS + deploy
    hooks for free.
- **Database.** Already Supabase (cloud) — no change; just make sure the VPS can
  reach it and secrets are set as env vars, not committed.
- **The sync gateway.** After W2 this is a plain Linux process. Run it *on the same
  VPS* as the API (simplest) — one host, one deploy, `auto_sync` as a service.
  No Windows VPS needed anymore (that was an MT5 constraint).
- **Secrets & config.** A single `.env` on the host (never in git), or the host's
  secret manager. Rotate the Gemini / Capital / FRED / FMP keys as part of going
  live.
- **Backups.** Supabase has automated backups; confirm the retention and add a
  weekly `pg_dump` to object storage for belt-and-braces.
- **Observability.** A basic uptime check (UptimeRobot / healthchecks.io hitting
  `/api/health`) and log shipping or at least `journalctl` access.

**Key decisions (see §4).** VPS vs managed host; domain name; Cloudflare in front
(free HTTPS + basic DDoS + access rules) yes/no; does the local PC still run
anything, or is the VPS now the only home.

**Effort.** M–L (M if managed host, L if self-managed VPS + reverse proxy + systemd).
**Risk.** Medium — this is where "exposed to the internet" becomes real. W3 (auth)
**must** be done first. Cloudflare Access in front is a strong cheap extra layer
(only your Google/email can reach the origin at all).
**Depends on.** **W2** (Linux-clean backend) and **W3** (auth) are hard
prerequisites. W6 strongly recommended first.

---

## 3. Sequencing

```mermaid
flowchart TD
    W1["W1 · AI tool-calling<br/>(highest value, independent)"]
    W2["W2 · Decouple Streamlit<br/>(unblocks deploy)"]
    W3["W3 · Auth + security<br/>(P0 for online)"]
    W6["W6 · Alembic migrations"]
    W4["W4 · SSE streaming"]
    W5["W5 · Mobile / PWA"]
    W7["W7 · Online deploy + sync gateway"]

    W2 --> W7
    W3 --> W7
    W6 --> W7
    W3 --> W4
    W3 --> W5
    W7 --> W5

    subgraph P1["Phase 1 — value + unblock (parallelisable)"]
        W1
        W2
    end
    subgraph P2["Phase 2 — make online safe"]
        W3
        W6
    end
    subgraph P3["Phase 3 — go online"]
        W7
    end
    subgraph P4["Phase 4 — mobile-native feel"]
        W4
        W5
    end

    P1 --> P2 --> P3 --> P4
```

**Recommended order:**

1. **W1** (AI tool-calling) — biggest day-to-day value, blocks nothing, start now.
2. **W2** (decouple Streamlit) — do it while the coupling is only ~3 files; unblocks W7.
3. **W3** (auth) — the gate. Nothing goes online before this.
4. **W6** (Alembic) — so W7 has a clean schema step.
5. **W7** (deploy) — the actual "online" milestone.
6. **W4 + W5** (streaming + mobile polish) — once it's online and authed, make it feel native on a phone.

W1 and W2 can run in parallel. W4 and W5 can run in parallel after W7.

---

## 4. Open decisions (need your call before building)

| # | Decision | Options / notes |
|---|---|---|
| D1 | **Streamlit terminal — keep or retire?** | If retiring: W2 becomes "delete the Streamlit modules", much simpler, and `docs/STAGE_11_STREAMLIT_RETIREMENT_EVALUATION.md` gets finished. If keeping: W2 is lazy-import/extract. |
| D2 | **Hosting** | Self-managed VPS (cheapest, ~$5–10/mo, more ops) vs managed (Render/Railway/Fly, ~$7–20/mo, less ops). Recommendation: **managed** to start; move to a VPS later if cost/control matters. |
| D3 | **Domain** | Buy a domain (`something.app` / `.trade` / `.xyz`) or use the host's subdomain. A real domain is ~$10–15/yr and makes HTTPS + Cloudflare clean. |
| D4 | **Cloudflare in front?** | Free tier gives HTTPS, caching, basic DDoS, and **Cloudflare Access** (only your email can reach the origin — a second auth layer for near-zero effort). Recommendation: **yes**. |
| D5 | **Auth token style** | Short-lived JWT + refresh (stateless, standard) vs one long opaque session token in an httpOnly cookie (simpler, revocable). Recommendation: **opaque session cookie** for a single-user app — simpler and revocable. |
| D6 | **2FA (TOTP)** | Adds a phone-authenticator step to login. ~half a day. Recommendation: **yes**, given it's finance data on the public internet. |
| D7 | **Does the local PC still do anything?** | Once the VPS runs everything, the PC becomes just a dev box. Confirm nothing local is load-bearing (it isn't, after MT5 retirement). |
| D8 | **`run_backtest` AI tool in W1 v1?** | Include (powerful, needs a runtime cap) or defer to W1 v2. Recommendation: **defer** — ship the read tools first. |
| D9 | **Mobile nav pattern** | Bottom tab bar (app-like) vs hamburger drawer. Recommendation: **bottom bar** for the 4 zones + a "more" sheet. |
| D10 | **Web Push in W5 or later?** | Push needs VAPID keys + a subscription table + the SW. Recommendation: **later** — ship the responsive + installable PWA first, add push as a follow-up. |

---

## 5. Explicitly out of scope

- **In-window audio chimes / HTML5 `<audio>` alerts** — your call, descoped.
- **Live order submission / modification / cancellation** — permanent design block.
- **Multi-user / teams / role separation** — single operator; not building it.
- **Un-freezing or re-reading the sealed holdout / strategy contract.**
- **Reviving MT5 as a web dependency** — stays env-only opt-in.

---

## Appendix A — corrections to the prior "Gap Analysis" note

The earlier audit note is a useful map but stale/imprecise in places:

| Claim in that note | Correction |
|---|---|
| "#1 P0: Interactive candlestick charting — missing" | **Done** — `PriceChart.tsx`, lightweight-charts 4.2.3, on the Market page. |
| "Manual MT5/Capital sync buttons — missing" | **Done** — Positions header. |
| "Native MT5 dependency blocks Linux/containers" | **Largely resolved** — MT5 retired from the web (env-only). Remaining Linux blocker is the **Streamlit** import (W2), not MT5. |
| "1,043 passing tests" | ~2,268 collected now; the 1,043 figure is stale. There are also ~51 collection errors worth a triage pass (likely optional-dep / network test modules). |
| "Historical baseline: holdout N=82, E[R]=+0.637R, WR 58.6%" | These are a **pre-registered expectation**, not a validated track record. The sealed Phase-74 gold holdout was **never read**; the overall directional research verdict is **NO_VALIDATED_EDGE**. The only usable edge found is crypto funding carry (~2%/yr over cash). Do not present the holdout numbers as performance. |
| "Live execution — a gap" | Not a gap — a deliberate, repeatedly-reaffirmed safety block. |
| Institutional framing (JWT multi-user, RBAC, IP rate-limiting, WAF) | Over-scoped for a solo operator. This plan does single-user auth + a login rate-limit + optional 2FA + Cloudflare Access, which is proportionate. |

---

## Appendix B — effort summary

| Workstream | Effort | Prereqs | Phase |
|---|---|---|---|
| W1 · AI tool-calling | M | — | 1 |
| W2 · Decouple Streamlit | S–M | D1 | 1 |
| W3 · Auth + security | M | D4–D6 | 2 |
| W6 · Alembic | M | — | 2 |
| W7 · Online deploy + sync gateway | M–L | W2, W3, D2–D4 | 3 |
| W4 · SSE streaming | M | W3 | 4 |
| W5 · Mobile / PWA | L | W3 (push), W7 | 4 |

Rough total: **6–10 weeks of focused work**, front-loaded so the two highest-value
pieces (W1, W2) land first and "online + authed" (W3 → W7) is reachable in the
middle before the mobile polish.
