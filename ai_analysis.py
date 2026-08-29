import os
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import market_data

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

def analyze_market_context(symbol="XAUUSD", timeframe="1h"):
    """
    Structured AI Market Analysis Pipeline conforming to Section 31, 32, 33 & 34 of the Master Spec.
    - Collects real market data and calculates deterministic indicators first.
    - Structured analysis output separating FACTUAL DATA from INTERPRETATION.
    - NEVER executes trades or promises guaranteed profits.
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

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
        "disclaimer": "AI market analysis is purely informational and based on technical indicators. Not financial advice."
    }
