import os
import time
import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import market_data
import ml_trainer

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

def calculate_technical_indicators(candles):
    if not candles or len(candles) < 20:
        return None

    df = pd.DataFrame(candles)
    close = df['close']
    high = df['high']
    low = df['low']

    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(df) >= 50 else ema20
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(df) >= 200 else ema50

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = float(tr.rolling(window=14).mean().iloc[-1]) if len(df) >= 14 else float(tr.mean())

    recent_high = float(high.tail(50).max())
    recent_low = float(low.tail(50).min())
    pivot = (recent_high + recent_low + float(close.iloc[-1])) / 3.0
    r1 = (2 * pivot) - recent_low
    s1 = (2 * pivot) - recent_high

    curr_price = float(close.iloc[-1])
    open_price = float(df['open'].iloc[0])
    price_change_pct = ((curr_price - open_price) / open_price) * 100.0

    return {
        "current_price": round(curr_price, 5),
        "ema20": round(ema20, 5),
        "ema50": round(ema50, 5),
        "ema200": round(ema200, 5),
        "rsi": round(rsi, 2),
        "atr": round(atr, 5),
        "resistance_1": round(r1, 5),
        "support_1": round(s1, 5),
        "swing_high": round(recent_high, 5),
        "swing_low": round(recent_low, 5),
        "price_change_pct": round(price_change_pct, 2)
    }

def fallback_analyze_market_context(sym, timeframe, indicators, now_utc):
    """Deterministic fallback."""
    px = indicators["current_price"]
    ema20 = indicators["ema20"]
    ema50 = indicators["ema50"]
    rsi = indicators["rsi"]
    r1 = indicators["resistance_1"]
    s1 = indicators["support_1"]

    if px > ema20 and ema20 > ema50:
        trend_bias = "Bullish"
        trend_desc = "Price is trading above key EMA 20 & 50 with positive upward momentum."
    elif px < ema20 and ema20 < ema50:
        trend_bias = "Bearish"
        trend_desc = "Price is trading below key EMA 20 & 50 with sustained downward pressure."
    else:
        trend_bias = "Neutral / Ranging"
        trend_desc = "Price is oscillating around moving averages in a consolidation zone."

    if rsi > 70:
        momentum_state = "Overbought (RSI > 70) - Watch for potential pullback exhaustion."
    elif rsi < 30:
        momentum_state = "Oversold (RSI < 30) - Watch for potential mean reversion bounce."
    elif rsi >= 50:
        momentum_state = f"Bullish momentum (RSI {rsi:.1f}) holding above median."
    else:
        momentum_state = f"Bearish momentum (RSI {rsi:.1f}) below median 50."

    return {
        "symbol": sym,
        "timeframe": timeframe,
        "timestamp": now_utc,
        "factual_data": indicators,
        "market_summary": f"{sym} ({timeframe}) is currently trading at {px:,.2f} with a {trend_bias.lower()} bias.",
        "trend_bias": trend_bias,
        "technical_structure": trend_desc,
        "key_levels": {
            "resistance": r1,
            "support": s1,
            "swing_high": indicators["swing_high"],
            "swing_low": indicators["swing_low"]
        },
        "momentum": momentum_state,
        "volatility": f"ATR is {indicators['atr']:,.4f}, representing normal session volatility.",
        "bullish_factors": [
            f"Holding above key support at {s1:,.2f}",
            f"EMA 20 dynamic support at {ema20:,.2f}"
        ],
        "bearish_factors": [
            f"Encountering resistance near {r1:,.2f}",
            f"Overhead swing high liquidity at {indicators['swing_high']:,.2f}"
        ],
        "scenarios": {
            "bullish_case": f"Break and close above {r1:,.2f} targets next expansion toward {indicators['swing_high']:,.2f}.",
            "bearish_case": f"Break and close below {s1:,.2f} exposes liquidity lower toward {indicators['swing_low']:,.2f}.",
            "invalidation": f"A close beyond {indicators['swing_low']:,.2f} invalidates the bullish structure."
        },
        "confidence": "Moderate (Data-driven technical synthesis)",
        "disclaimer": "AI market analysis is purely informational. Not financial advice."
    }

def analyze_market_context(symbol="XAUUSD", timeframe="1h"):
    """
    Dual-AI Pipeline:
    1. Fetches factual data & indicators.
    2. Uses Local Ollama LLM for Generative Synthesis.
    3. Uses Scikit-Learn Custom Model for Win Probability Score.
    """
    sym = str(symbol).upper().replace(":", "").replace("/", "")
    candles = market_data.get_realtime_candles(symbol=sym, timeframe=timeframe, count=150)
    
    if not candles:
        return {
            "symbol": sym,
            "timeframe": timeframe,
            "status": "unavailable",
            "error": f"Real market data currently unavailable for {sym}."
        }

    indicators = calculate_technical_indicators(candles)
    if not indicators:
        return {
            "symbol": sym,
            "timeframe": timeframe,
            "status": "error",
            "error": "Insufficient historical candles to calculate technical analysis."
        }

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    ai_data = None
    
    # LAYER 1: Generative LLM Analysis (Ollama)
    if OLLAMA_AVAILABLE:
        try:
            prompt = f"""
You are an elite quantitative analyst. Analyze the following technical indicators for {sym}.
Return ONLY a raw JSON object strictly following this schema (NO markdown, NO comments, ONLY JSON):
{{
  "market_summary": "A concise overview.",
  "trend_bias": "Bullish",
  "technical_structure": "Explanation of structure.",
  "momentum": "Assessment of momentum.",
  "volatility": "Assessment of volatility.",
  "bullish_factors": ["Point 1"],
  "bearish_factors": ["Point 1"],
  "scenarios": {{
    "bullish_case": "...",
    "bearish_case": "...",
    "invalidation": "..."
  }},
  "confidence": "High"
}}

FACTUAL DATA:
{json.dumps(indicators, indent=2)}
"""
            response = ollama.chat(model='llama3', messages=[
                {'role': 'user', 'content': prompt}
            ])
            raw_text = response['message']['content'].strip()
            
            # Clean markdown
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1)
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```", "", 1)
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
                
            ai_data = json.loads(raw_text.strip())
            disclaimer = "⚡ AI analysis generated by Local Ollama (llama3)."
            
        except Exception as e:
            print(f"Ollama API Error: {e}")
            ai_data = None
            
    if not ai_data:
        # Fallback to deterministic logic
        fallback_data = fallback_analyze_market_context(sym, timeframe, indicators, now_utc)
        ai_data = fallback_data
        disclaimer = "⚡ Deterministic fallback logic used (Ollama unavailable or failed)."
        
    final_output = {
        "symbol": sym,
        "timeframe": timeframe,
        "timestamp": now_utc,
        "factual_data": indicators,
        "market_summary": ai_data.get("market_summary", ""),
        "trend_bias": ai_data.get("trend_bias", ""),
        "technical_structure": ai_data.get("technical_structure", ""),
        "key_levels": {
            "resistance": indicators["resistance_1"],
            "support": indicators["support_1"],
            "swing_high": indicators["swing_high"],
            "swing_low": indicators["swing_low"]
        },
        "momentum": ai_data.get("momentum", ""),
        "volatility": ai_data.get("volatility", ""),
        "bullish_factors": ai_data.get("bullish_factors", []),
        "bearish_factors": ai_data.get("bearish_factors", []),
        "scenarios": ai_data.get("scenarios", {}),
        "confidence": ai_data.get("confidence", ""),
        "disclaimer": disclaimer,
        "ml_prob_buy": 0.0,
        "ml_prob_sell": 0.0
    }
    
    # LAYER 2: Predictive Machine Learning Model (Personal Edge)
    # We predict the probability of success if the user Buys, and if the user Sells.
    try:
        buy_prob, msg1 = ml_trainer.predict_setup_probability(sym, "BUY", 0.1, datetime.utcnow())
        sell_prob, msg2 = ml_trainer.predict_setup_probability(sym, "SELL", 0.1, datetime.utcnow())
        
        if buy_prob is not None:
            final_output["ml_prob_buy"] = round(buy_prob * 100, 1)
        if sell_prob is not None:
            final_output["ml_prob_sell"] = round(sell_prob * 100, 1)
    except Exception as e:
        print(f"ML Model Prediction Error: {e}")

    return final_output
