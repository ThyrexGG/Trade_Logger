# The Dual-AI Engine Architecture

TradeLogger employs a unique "Dual-AI" approach, splitting analytical responsibilities between two completely offline, privacy-first AI models. This avoids the latency, cost, and hallucination risks of sending raw market data to cloud LLMs.

## Layer 1: Predictive Machine Learning (Scikit-Learn)
**File:** `ml_trainer.py`

This layer is purely mathematical. It does not read text; it reads numbers.
- **Algorithm:** `RandomForestClassifier`
- **Data Source:** It automatically queries the `closed_trades` table in `trades.db`.
- **Features Used:** 
  - Trade Entry Hour (Time of Day)
  - Trade Entry Day of Week
  - Volume (Position Size)
  - Asset Volatility (Simulated ATR)
- **Output:** A percentage probability (e.g., `BUY Probability: 59.1%`).
- **Mechanism:** Every time a new trade is closed, the system can be re-trained. When the user requests an analysis on a new asset, `ml_trainer.py` looks at the current hour and day, looks at the user's historical success rate in those exact conditions, and calculates a statistical edge.

## Layer 2: Generative Market Context (Ollama / Llama3)
**File:** `ai_analysis.py`

This layer is responsible for translating cold technical data into a human-readable trading scenario.
- **Algorithm:** Local Large Language Model (e.g., `llama3:latest`) via the Ollama engine.
- **Data Source:** `market_data.py` (which fetches real-time OHLC candles).
- **Process:**
  1. `ai_analysis.py` calculates deterministic technical indicators (RSI, EMA 20, EMA 50, ATR, and Pivot Support/Resistance levels).
  2. The script builds a strict "Factual Prompt" containing *only* these calculated numbers. The LLM is **not** allowed to guess the price.
  3. The prompt is sent to the local Ollama API (`http://localhost:11434`).
  4. Ollama processes the prompt and returns a JSON object containing a `trend_bias`, `technical_structure` summary, and Bullish/Bearish invalidation `scenarios`.
- **Output:** The structured JSON is parsed by `app.py` and rendered as the detailed AI Dashboard text.
