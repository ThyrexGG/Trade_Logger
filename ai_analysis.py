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

def analyze_market_context(symbol="XAUUSD", timeframe="1h", model_name="llama3"):
    """
    Dual-AI Pipeline:
    1. Fetches factual data & indicators.
    2. Uses Local Ollama LLM for Generative Synthesis.
    3. Uses Scikit-Learn Custom Model for Win Probability Score.
    """
    sym = str(symbol).upper().replace(":", "").replace("/", "")
    
    # Get MTF Data
    mtf_data_raw = market_data.get_mtf_data(symbol=sym, base_timeframe=timeframe)
    if not mtf_data_raw or timeframe not in mtf_data_raw or not mtf_data_raw[timeframe]:
         return {"symbol": sym, "status": "unavailable", "error": f"Real market data currently unavailable for {sym}."}
         
    mtf_indicators = {}
    for tf, candles in mtf_data_raw.items():
        if candles:
            indics = calculate_technical_indicators(candles)
            if indics:
                mtf_indicators[tf] = indics
                
    if timeframe not in mtf_indicators:
        return {"symbol": sym, "status": "error", "error": "Insufficient historical candles to calculate technical analysis."}

    primary_indicators = mtf_indicators[timeframe]
    
    # Get Liquidity Zones & FVGs & Killzones & Order Blocks
    df_primary = pd.DataFrame(mtf_data_raw[timeframe])
    liquidity_zones = market_data.calculate_liquidity_zones(df_primary)
    fvg_data = market_data.detect_fvgs(df_primary)
    ob_data = market_data.detect_order_blocks(df_primary)
    asian_range = market_data.calculate_asian_range(df_primary)
    active_killzone = market_data.detect_active_killzone()
    
    # Phase 12, 13, 14: Macro, COT, Cross-Asset
    macro_data = market_data.fetch_macro_news(sym)
    cot_data = market_data.fetch_cot_data(sym)
    cross_asset = market_data.fetch_cross_asset(sym)
    
    # Phase 4, 5, 6, 7 Deterministic Logic
    mtf_alignment = market_data.calculate_mtf_alignment(sym, timeframe)
    market_regime = market_data.calculate_market_regime(df_primary)
    volume_profile = market_data.calculate_volume_profile(df_primary)
    market_structure = market_data.calculate_market_structure(df_primary)

    # Get ML Edge Score (3-class)
    ml_data = {"buy_prob": 0.0, "sell_prob": 0.0, "neutral_prob": 0.0, "confidence": "Low", "error": "Not calculated"}
    try:
        ml_data = ml_trainer.predict_directional_probabilities(sym, datetime.utcnow())
    except Exception as e:
        ml_data["error"] = str(e)
        
    buy_prob_val = ml_data.get("buy_prob", 0.0)
    sell_prob_val = ml_data.get("sell_prob", 0.0)
    neutral_prob_val = ml_data.get("neutral_prob", 0.0)
        
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    ai_data = None
    
    if OLLAMA_AVAILABLE:
        try:
            prompt = f"""
You are an elite ICT (Inner Circle Trader) and Smart Money Concepts (SMC) intraday trader. 
Analyze the following technical indicators and liquidity data for {sym}.
Return ONLY a raw JSON object strictly following this schema (NO markdown, NO comments, ONLY JSON):
{{
  "killzone_context": "Write 1 sentence summarizing the current active killzone and its implication for volatility.",
  "liquidity_matrix": "Write 2 sentences analyzing the Buy-Side (BSL) and Sell-Side Liquidity (SSL) targets. Do NOT output raw arrays.",
  "fvg_imbalances": "Write 2 sentences analyzing current Fair Value Gaps and premium/discount arrays. Do NOT output raw arrays.",
  "confidence": "High / Medium / Low"
}}

FACTUAL DATA:
1. Multi-Timeframe (MTF) Technicals:
{json.dumps(mtf_indicators, indent=2)}

2. Liquidity Zones (BSL / SSL):
{json.dumps(liquidity_zones, indent=2)}

3. Fair Value Gaps (FVG):
{json.dumps(fvg_data, indent=2)}

4. Institutional Order Blocks (Valid & Unmitigated):
{json.dumps(ob_data, indent=2)}

5. Current Active Killzone & Session Data:
Active Killzone: {active_killzone}
Asian Range Geometry: {json.dumps(asian_range, indent=2)}

6. Macro, COT, & Cross-Asset Context:
- News/Macro: {macro_data['risk_level']} Risk ({macro_data['event']})
- Institutional Positioning (COT): {cot_data['sentiment']}
- Cross-Asset Flow ({cross_asset['asset']}): {cross_asset['signal_filter']}

7. Predictive ML Edge Score (Historical Win Probability):
- BUY Edge: {buy_prob_val}%
- SELL Edge: {sell_prob_val}%
- NEUTRAL Edge: {neutral_prob_val}%
- Model Confidence: {ml_data.get('confidence', 'Unknown')}

6. Multi-Timeframe Trend Alignment (Macro vs Micro):
{mtf_alignment}

7. Deterministic Market Regime (ADX / Volatility):
{market_regime}

8. Volume Profile & VWAP (Anchored):
{json.dumps(volume_profile, indent=2)}

9. Deterministic Market Structure (BOS / MSS):
{json.dumps(market_structure, indent=2)}
"""
            response = ollama.chat(model=model_name, messages=[
                {'role': 'user', 'content': prompt}
            ])
            raw_text = response['message']['content'].strip()
            
            # Robustly extract JSON block using regex
            import re
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group(0)
                
            ai_data = json.loads(raw_text.strip())
            disclaimer = f"[AI] Analysis generated by Local Ollama ({model_name})."
            
        except Exception as e:
            print(f"Ollama API Error: {e}")
            ai_data = None
            
    if not ai_data:
        # Fallback to deterministic logic
        fallback_data = fallback_analyze_market_context(sym, timeframe, primary_indicators, now_utc)
        ai_data = fallback_data
        disclaimer = "[!] Deterministic fallback logic used (Ollama unavailable or failed)."
        ai_data["killzone_context"] = active_killzone
        ai_data["liquidity_matrix"] = "Unavailable in fallback mode."
        ai_data["fvg_imbalances"] = "Unavailable in fallback mode."
        ai_data["ict_execution_model"] = f"ML Edge -> BUY: {buy_prob_val}% | SELL: {sell_prob_val}%"
        ai_data["bias"] = "Neutral"
        
    data_quality = {
        "price_data": "LIVE",
        "historical_candles": "COMPLETE",
        "news": "NOT APPLICABLE (Missing Integration)",
        "economic_calendar": "NOT APPLICABLE (Missing Integration)",
        "cot_positioning": "NOT APPLICABLE",
        "volume": "TICK VOLUME"
    }

    final_output = {
        "symbol": sym,
        "timeframe": timeframe,
        "timestamp": now_utc,
        "data_quality": data_quality,
        "factual_data": primary_indicators,
        "mtf_alignment": mtf_alignment,
        "market_regime": market_regime,
        "volume_profile": volume_profile,
        "market_structure": market_structure,
        "liquidity_zones": liquidity_zones,
        "fvg_data": fvg_data,
        "ob_data": ob_data,
        "asian_range": asian_range,
        "macro_data": macro_data,
        "cot_data": cot_data,
        "cross_asset": cross_asset,
        "killzone": active_killzone,
        "killzone_context": ai_data.get("killzone_context", ""),
        "liquidity_matrix": ai_data.get("liquidity_matrix", ""),
        "fvg_imbalances": ai_data.get("fvg_imbalances", ""),
        "confidence": ai_data.get("confidence", ""),
        "disclaimer": disclaimer,
        "ml_prob_buy": buy_prob_val,
        "ml_prob_sell": sell_prob_val,
        "ml_prob_neutral": neutral_prob_val,
        "ml_confidence": ml_data.get("confidence", "Unknown"),
        "ml_training_date": ml_data.get("training_date", "Unknown")
    }
    # Phase 15-17 Engines
    confluence = market_data.calculate_confluence(final_output)
    final_output["confluence_bias"] = confluence
    final_output["deterministic_scenario"] = market_data.build_trade_scenarios(final_output, confluence['bias'])
    final_output["validation"] = market_data.validate_trade_model(final_output, confluence)

    return final_output
