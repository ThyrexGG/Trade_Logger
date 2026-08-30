# TradeLogger Terminal - Architecture & Technology Stack

TradeLogger is an advanced, offline-first trading terminal built to consolidate execution, charting, tracking, and AI-driven analysis into a single application. 

## Core Technology Stack

### 1. Frontend & UI Engine
- **Streamlit (Python):** Serves as the core reactive UI framework (`app.py`). Handles all routing, state management, and layout generation.
- **Vanilla CSS / Streamlit Styling:** Custom injected CSS for dark-mode aesthetics, neon accents (glassmorphism), pulsing animations, and the custom spinning loaders.
- **Lightweight Charts (TradingView):** The `tradingview_widget.py` injects a custom HTML/JS payload containing TradingView's open-source Lightweight Charts engine. This powers the 2,000-candle technical charts and marker overlays.

### 2. Backend & Data Layer
- **Python (3.x):** The entire backend infrastructure is written in Python.
- **FastAPI:** Serves as the high-performance unified backend (`server.py`), providing REST endpoints and a highly concurrent WebSocket layer (`/ws/live_ticks`) that broadcasts live millisecond MT5 ticks to clients.
- **SQLite3:** A lightweight, serverless, file-based relational database (`trades.db`). It stores closed trades, open positions, active price alerts, UI settings, and serialized chart drawings.
- **Pandas:** Used heavily for data manipulation, formatting the database tables into readable DataFrames, and preparing datasets for the Machine Learning engine.

### 3. Broker Integrations (APIs)
- **MetaTrader 5 (MT5):** Using the official `MetaTrader5` python library, `mt5_sync.py` connects locally to the MT5 terminal running on the user's Windows machine. It pulls historical deal data and maps it to the SQLite database.
- **Capital.com API:** Using REST API calls, `capital_sync.py` and `order_execution.py` handle live session generation (via `X-SECURITY-TOKEN` and `CST`), retrieving account balances, open positions, historical trades, and executing live market/limit orders.

### 4. The Dual-AI Engine
- **Ollama (Generative AI):** Runs a local LLM (`llama3` by default) via the `ollama` Python package. It acts as the "Generative Analyst," reading technical indicators and returning structured text summaries.
- **Discord, Telegram & OneSignal:** `alerts.py` dispatches rich embedded webhooks directly to Telegram and Discord to alert on Big Wins and Max Loss limits. It also uses OneSignal for native push notifications to mobile.
- **Scikit-Learn (Predictive ML):** Uses a `RandomForestClassifier` trained purely on the local `trades.db` database. It analyzes the user's win/loss history based on Time of Day, Day of Week, and Volume to predict future trade probabilities.

## System Workflow
1. **User interacts with Streamlit UI.**
2. UI requests data from `database.py` (Local DB) or `market_data.py` (Live Quotes).
3. If syncing, `mt5_sync.py` or `capital_sync.py` fetch data from the broker and write it to SQLite.
4. If AI is triggered, `app.py` packages the chart data, sends it to `ai_analysis.py`, which routes numerical data to Scikit-Learn and contextual data to Ollama.
5. The result is returned and rendered instantly without ever leaving the local machine.
