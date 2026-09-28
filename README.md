# TradeLogger

TradeLogger is a personal trading journal, analytics, and research platform for tracking trades executed on MetaTrader 5 and Capital.com. It syncs closed trades and open positions from those brokers into its own database, then provides performance analytics, risk sizing, price alerts, a backtesting and strategy-discovery research lab, market/macro intelligence, and a read-only AI assistant (Gemini) for querying your own trading history. The application is intentionally read-only with respect to brokers: it never places, modifies, or cancels an order, and live trade automation is permanently disabled in code.

## Tech stack

**Backend**
- Python (3.14), FastAPI (`api/main.py`) as the primary HTTP API
- PostgreSQL (Neon, via `DATABASE_URL`) with automatic SQLite fallback (`trades.db`) for local/test use
- Alembic for database migrations
- Pandas, NumPy, SciPy, scikit-learn for analytics, backtesting, and the ML win/loss model
- Google Gemini (`google-genai`) for the read-only AI assistant; Ollama supported for local LLM use in the legacy terminal
- MetaTrader5 and Capital.com REST APIs for broker sync (`mt5_sync.py`, `capital_sync.py`)

**Frontend**
- React 19 + TypeScript, built with Vite 6, styled with Tailwind CSS v4, routed with React Router v7 (`frontend/`) — this is the current, actively developed web client

**Other clients**
- `desktop/` — an Electron shell that opens the deployed web app in a native window with system-tray and offline alerts
- `mobile/` — a React Native (Expo) mobile app
- `trade_logger_app/` — an earlier Flutter client, kept for reference
- `legacy/server.py` — an older FastAPI service ("Trade Logger Pro Engine API") retained because a handful of execution/paper-trading tests and the legacy Flutter web build still depend on it; not part of the current product
- A Streamlit terminal (`app.py`) previously served as the primary UI; it has since been fully retired and removed from the codebase

## Project structure

```
api/                 FastAPI routers, schemas, and the AI/evidence-fusion adapters
frontend/            React + Vite web client (the current product)
desktop/             Electron desktop wrapper
mobile/              Expo/React Native mobile app
trade_logger_app/    Legacy Flutter client
legacy/              Retired modules kept for reference or test compatibility
strategies/          Strategy definitions used by the backtester/research engine
tools/, scripts/     One-off and maintenance scripts (DB tools, seeding, migrations)
tests/               Pytest suite
alembic/             Database migrations
docs/                Architecture notes, phase/stage reports, deployment guide
database.py, market_data.py, analytics.py, backtester.py, ...
                      Core engine modules (data access, analytics, research,
                      risk, macro/market intelligence) called by api/
```

## Setup

Prerequisites: Python 3.14, Node.js (for the frontend), and a PostgreSQL database (or rely on the SQLite fallback for local use).

1. Clone the repository and install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in the values you need (database URL, broker credentials, optional API keys for Gemini/FRED/FMP, auth settings). All integrations degrade gracefully when unconfigured.
3. Apply database migrations:
   ```bash
   python -m alembic upgrade head
   ```
4. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

## Running locally

Run the backend and frontend in separate terminals.

**Backend** (from the repository root):
```bash
python -m uvicorn api.main:app --port 8010
```

**Frontend**:
```bash
cd frontend
npm run dev
```

This opens the app at `http://localhost:5173`; the Vite dev server proxies `/api/*` requests to the backend on port 8010.

Broker sync can be run on demand:
```bash
python mt5_sync.py       # MetaTrader 5 (requires the MT5 terminal on Windows)
python capital_sync.py   # Capital.com (uses CAPITAL_* env vars)
```

## Testing

```bash
python -m pytest tests/ -q
```

## Deployment

The production setup deploys the frontend to Cloudflare Pages, the FastAPI backend to Render, and the database to Neon Postgres. See `docs/DEPLOY.md` for the full walkthrough and `render.yaml` / `wrangler.jsonc` for the platform configuration.
