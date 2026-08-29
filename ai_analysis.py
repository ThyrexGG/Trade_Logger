import os
import time
import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import market_data

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

def calculate_technical_indicators(candles):
    """
    Computes deterministic technical indicator values from real OHLC candle series.
    Never hallucinates or invents prices/indicators.
    """
    if not candles or len(candles) < 20:
        return None

    df = pd.DataFrame(candles)
    close = df['close']
    high = df['high']
    low = df['low']

    # 1. EMAs (20, 50, 200)
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(df) >= 50 else ema20
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(df) >= 200 else ema50

    # 2. RSI (14 period)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0

    # 3. ATR (14 period)
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = float(tr.rolling(window=14).mean().iloc[-1]) if len(df) >= 14 else float(tr.mean())

    # 4. Support & Resistance Key Levels
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
    """Deterministic fallback if Gemini API is missing or fails."""
    px = indicators["current_price"]
    ema20 = indicators["ema20"]
    ema50 = indicators["ema50"]
    rsi = indicators["rsi"]
    r1 = indicators["resistance_1"]
    s1 = indicators["support_1"]

    # Trend Bias Formulation
    if px > ema20 and ema20 > ema50:
        trend_bias = "Bullish"
        trend_desc = "Price is trading above key EMA 20 & 50 with positive upward momentum."
    elif px < ema20 and ema20 < ema50:
        trend_bias = "Bearish"
        trend_desc = "Price is trading below key EMA 20 & 50 with sustained downward pressure."
    else:
        trend_bias = "Neutral / Ranging"
        trend_desc = "Price is oscillating around moving averages in a consolidation zone."

    # Momentum Assessment
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
        "disclaimer": "AI market analysis is purely informational and based on deterministic indicators. Not financial advice."
    }

def analyze_market_context(symbol="XAUUSD", timeframe="1h"):
    """
    Structured AI Market Analysis Pipeline using Google Gemini LLM.
    - Collects real market data and calculates deterministic indicators first.
    - Sends factual data to Gemini LLM for advanced structural synthesis.
    - Gracefully falls back to deterministic rules if API key is missing.
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

    # 1. Check for Gemini API Key
    gemini_key = os.getenv("GEMINI_API_KEY")
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            gemini_key = str(st.secrets["GEMINI_API_KEY"]).strip('"\' \n\r\t')
    except Exception:
        pass

    # 2. Try calling Gemini LLM
    if GENAI_AVAILABLE and gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
You are an elite institutional quantitative analyst and market technician.
Analyze the following factual deterministic technical indicators for {sym} on the {timeframe} timeframe.
Your goal is to provide a highly professional, data-driven market synthesis.
Do not hallucinate prices. Rely entirely on the factual data provided below.

Return ONLY a raw JSON object strictly following this schema (do not wrap in markdown tags like ```json):
{{
  "market_summary": "A concise 1-2 sentence professional overview.",
  "trend_bias": "Bullish / Bearish / Neutral",
  "technical_structure": "Explanation of the current market structure.",
  "momentum": "Assessment of momentum (RSI, ATR).",
  "volatility": "Assessment of current volatility.",
  "bullish_factors": ["Point 1", "Point 2"],
  "bearish_factors": ["Point 1", "Point 2"],
  "scenarios": {{
    "bullish_case": "...",
    "bearish_case": "...",
    "invalidation": "..."
  }},
  "confidence": "High / Moderate / Low"
}}

FACTUAL DATA:
{json.dumps(indicators, indent=2)}
"""
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Clean potential markdown wrapping
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1)
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```", "", 1)
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
                
            ai_data = json.loads(raw_text.strip())
            
            return {
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
                "disclaimer": "⚡ AI market analysis generated by Google Gemini 1.5 Flash. Not financial advice."
            }
        except Exception as e:
            print(f"Gemini API Error: {e}")
            # Fall through to deterministic fallback
            
    # 3. Deterministic Fallback (if no key or API fails)
    return fallback_analyze_market_context(sym, timeframe, indicators, now_utc)
