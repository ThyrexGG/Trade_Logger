# TradeLogger File & Component Breakdown

A high-level directory of what each Python file is responsible for in the TradeLogger architecture.

### UI & Presentation
- **`app.py`:** The main entry point. Runs the Streamlit server (`python -m streamlit run app.py`). Contains all HTML/CSS layout, routing for tabs (Dashboard, Workspace, AI Context, Journal, Alerts), and button event handling.
- **`tradingview_widget.py`:** A custom wrapper that injects a lightweight Javascript/HTML payload into Streamlit. It fetches data from `market_data.py` and `database.py`, formats it into JSON, and renders an interactive, native-feeling TradingView chart with a full drawing toolbar and automatic PnL markers.

### Core Logic & AI
- **`ai_analysis.py`:** Connects to the local Ollama instance. Calculates technicals, builds the LLM prompt, and returns structured JSON market contexts.
- **`ml_trainer.py`:** Houses the Scikit-Learn Random Forest logic. Reads from SQLite to build a Pandas dataframe, trains a model on historical trade context, and provides realtime probability predictions.
- **`alerts.py`:** A background watcher script. Periodically compares current market prices to the `price_alerts` table in the database. If a threshold is crossed, it triggers a desktop notification via OneSignal or console output, and marks the alert as triggered.

### Data & Execution Integrations
- **`database.py`:** The SQLite ORM layer. Contains all `INSERT`, `SELECT`, `UPDATE`, and `DELETE` queries. Also handles schema creation if the `.db` file is missing.
- **`market_data.py`:** Connects to Capital.com's REST API or MT5 to pull live ticker prices and historical OHLC (Open, High, Low, Close) candles used for charting and AI analysis.
- **`capital_sync.py`:** Specialized script to authenticate with Capital.com using `.env` credentials, loop through historical trade history (handling pagination), and sync those trades down into the local SQLite database.
- **`mt5_sync.py`:** Connects directly to a locally running MetaTrader 5 Windows Terminal. Pulls live open positions, account equity, and trade history from MT5 and syncs it to SQLite.
- **`order_execution.py`:** Handles outbound POST requests to Capital.com (and potentially MT5) to actually execute live trades (Market/Limit orders) from the Streamlit UI's Quick Terminal.

### Configuration
- **`.env`:** Stores sensitive credentials, such as Capital.com API Keys, MT5 credentials, and API identifiers. Never checked into source control.
- **`requirements.txt`:** Python dependencies (`streamlit`, `pandas`, `scikit-learn`, `ollama`, `MetaTrader5`, `requests`, `plotly`).
