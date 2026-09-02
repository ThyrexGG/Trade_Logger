# TradeLogger Frontend (Stage 4 Foundation)

React 19 + TypeScript + Vite + Tailwind CSS foundation for the TradeLogger
migration. This stage establishes the frontend shell and a single connectivity
proof screen — it does **not** migrate any terminal features.

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
