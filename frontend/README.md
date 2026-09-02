# TradeLogger Frontend

React 19 + TypeScript + Vite + Tailwind CSS terminal frontend for the TradeLogger
migration.

Stage 5 established the persistent application shell — sidebar navigation across
the four product zones, top bar with live status, breadcrumbs, a Ctrl/Cmd+K
command palette, page containers and a reusable placeholder page. Feature pages
are still being migrated from the authoritative backend; most routes render a
professional shell placeholder (no fabricated data). `/operations/system` is the
one route backed by live data (`GET /api/health`).

## Navigation model

`src/lib/navigation.ts` is the single source of truth for the sidebar,
breadcrumbs and command palette. Zones and routes:

- `/workspace` · `/workspace/{market,risk,positions}`
- `/research` · `/research/{intelligence,strategy,backtest}`
- `/evidence` · `/evidence/{forward,statistics,governance}`
- `/operations` · `/operations/{journal,audit,system}`

`/` redirects to `/workspace`.

## Architecture

```
Browser → React (this app) → Vite dev proxy → FastAPI adapter (api.main:app) → authoritative Python engines
```

React communicates only over HTTP. No trading logic, no engines, and no
execution capability live here.

## Develop

```bash
# 1. Start the FastAPI adapter (repo root)
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# 2. Start the React dev server (this folder)
npm install
npm run dev          # http://localhost:5173
```

`/api/*` requests are proxied to FastAPI, so no CORS setup is needed in dev.

Streamlit (`streamlit run app.py`, port 8501) is unaffected and remains the
golden reference.

## Scripts

| Command             | Purpose                              |
| ------------------- | ------------------------------------ |
| `npm run dev`       | Vite dev server with API proxy       |
| `npm run build`     | Type-check + production build (dist) |
| `npm run typecheck` | TypeScript only, no emit             |
| `npm run preview`   | Serve the production build           |

## Environment

Configure via `.env.local` (git-ignored). All `VITE_*` values are embedded in
the public bundle — never store secrets.

- `VITE_API_BASE_URL` — prefix for API paths. Empty in dev (proxy handles it).
- `VITE_DEV_API_PROXY_TARGET` — dev proxy target (default `http://127.0.0.1:8000`).
