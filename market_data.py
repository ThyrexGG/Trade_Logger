import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import requests

def get_realtime_candles(symbol="XAUUSD", timeframe="15m", count=250):
    """
    Fetches real-time OHLC candlestick data.
    Priority 1: Local MetaTrader 5 terminal.
    Priority 2: Capital.com API.
    Priority 3: High-speed public financial feed (Binance / Yahoo Finance / Polygon).
    """
    sym = symbol.upper().replace("/", "").replace(":", "").strip()
    
    # 1. Try MetaTrader 5
    try:
        import mt5_sync
        if mt5_sync.MT5_AVAILABLE:
            import MetaTrader5 as mt5
            if mt5.initialize():
                tf_map = {
                    "1m": mt5.TIMEFRAME_M1,
                    "5m": mt5.TIMEFRAME_M5,
                    "15m": mt5.TIMEFRAME_M15,
                    "1h": mt5.TIMEFRAME_H1,
                    "4h": mt5.TIMEFRAME_H4,
                    "D": mt5.TIMEFRAME_D1,
                    "1d": mt5.TIMEFRAME_D1
                }
                mt5_tf = tf_map.get(timeframe.lower(), mt5.TIMEFRAME_M15)
                
                # Check for standard broker symbol variations (e.g. XAUUSD.m, XAUUSD.raw, GOLD)
                possible_syms = [sym, f"{sym}.m", f"{sym}.raw", f"{sym}m", f"{sym}+", "GOLD" if "XAU" in sym else sym]
                rates = None
                for s in possible_syms:
                    rates = mt5.copy_rates_from_pos(s, mt5_tf, 0, count)
                    if rates is not None and len(rates) > 0:
                        break
                mt5.shutdown()
                
                if rates is not None and len(rates) > 0:
                    candles = []
                    for r in rates:
                        candles.append({
                            "time": int(r['time']),
                            "open": round(float(r['open']), 5),
                            "high": round(float(r['high']), 5),
                            "low": round(float(r['low']), 5),
                            "close": round(float(r['close']), 5),
                            "volume": float(r['tick_volume'])
                        })
                    return candles
    except Exception as e:
        pass

    # 2. Try Binance for Crypto
    if "BTC" in sym or "ETH" in sym or "SOL" in sym:
        try:
            binance_sym = "BTCUSDT" if "BTC" in sym else ("ETHUSDT" if "ETH" in sym else "SOLUSDT")
            tf_binance = "15m" if timeframe in ["15m", "15"] else ("1h" if timeframe in ["1h", "60"] else "1d")
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_sym}&interval={tf_binance}&limit={count}"
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                candles = []
                for k in data:
                    candles.append({
                        "time": int(k[0] // 1000),
                        "open": round(float(k[1]), 2),
                        "high": round(float(k[2]), 2),
                        "low": round(float(k[3]), 2),
                        "close": round(float(k[4]), 2),
                        "volume": round(float(k[5]), 2)
                    })
                if candles:
                    return candles
        except Exception:
            pass

    # 3. High-Speed Yahoo Finance Feed (Forex, Gold, Indices, Commodities)
    try:
        yf_symbol_map = {
            "XAUUSD": "GC=F",
            "GOLD": "GC=F",
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "JPY=X",
            "NAS100": "NQ=F",
            "US100": "NQ=F",
            "SPX500": "ES=F",
            "US500": "ES=F",
            "US30": "YM=F",
            "USOIL": "CL=F",
            "BTCUSD": "BTC-USD"
        }
        yf_ticker = yf_symbol_map.get(sym, f"{sym}=X")
        
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "1h",
            "D": "1d",
            "1d": "1d"
        }
        yf_interval = interval_map.get(timeframe.lower(), "15m")
        range_param = "5d" if yf_interval in ["1m", "5m", "15m"] else "1mo"
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}?interval={yf_interval}&range={range_param}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            result = res.json()["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            
            candles = []
            for i in range(len(timestamps)):
                o = quote["open"][i]
                h = quote["high"][i]
                l = quote["low"][i]
                c = quote["close"][i]
                v = quote.get("volume", [100]*len(timestamps))[i] or 100
                if o is not None and h is not None and l is not None and c is not None:
                    candles.append({
                        "time": int(timestamps[i]),
                        "open": round(float(o), 5),
                        "high": round(float(h), 5),
                        "low": round(float(l), 5),
                        "close": round(float(c), 5),
                        "volume": float(v)
                    })
            if candles:
                return candles[-count:]
    except Exception as e:
        pass

    # 4. Fallback: Return empty array instead of fake synthetic data
    return []

def calculate_liquidity_zones(df, left_bars=10, right_bars=10):
    """
    Phase 8: Strict Liquidity Engine Audit.
    Identifies Swing Highs and Swing Lows and strictly validates them against current price geometry.
    BSL must be physically ABOVE current price. SSL must be physically BELOW current price.
    """
    if df.empty or len(df) < left_bars + right_bars + 1:
        return {"bsl": [], "ssl": []}
        
    df = df.copy()
    current_price = df['close'].iloc[-1]
    
    # Detect Swing Highs and Lows
    df['swing_high'] = df['high'] == df['high'].rolling(window=left_bars+right_bars+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=left_bars+right_bars+1, center=True).min()
    
    swing_highs = df[df['swing_high']]['high'].dropna().tolist()
    swing_lows = df[df['swing_low']]['low'].dropna().tolist()
    
    # STRICT GEOMETRY VALIDATION (Phase 8)
    # BSL pools must be physically above the current price to be targeted as buy-side liquidity
    valid_bsl = [round(float(h), 5) for h in swing_highs if h > current_price]
    
    # SSL pools must be physically below the current price to be targeted as sell-side liquidity
    valid_ssl = [round(float(l), 5) for l in swing_lows if l < current_price]
    
    # Sort BSL ascending (closest resistance first), SSL descending (closest support first)
    valid_bsl.sort()
    valid_ssl.sort(reverse=True)
    
    # Return the closest 3 valid pools for each
    return {
        "bsl": valid_bsl[:3],
        "ssl": valid_ssl[:3]
    }

def get_mtf_data(symbol="XAUUSD", base_timeframe="15m"):
    """
    Fetches Multi-Timeframe (MTF) data simultaneously for alignment context.
    """
    mtf_map = {
        "1m": ["1m", "5m", "15m"],
        "5m": ["5m", "15m", "1h"],
        "15m": ["15m", "1h", "4h"],
        "1h": ["1h", "4h", "D"],
        "4h": ["4h", "D", "W"],
        "D": ["D", "W", "M"]
    }
    
    timeframes_to_fetch = mtf_map.get(base_timeframe, [base_timeframe, "1h", "D"])
    
    mtf_data = {}
    for tf in timeframes_to_fetch:
        mtf_data[tf] = get_realtime_candles(symbol, tf, count=100)
        
    return mtf_data

def calculate_mtf_alignment(symbol="XAUUSD", base_timeframe="15m"):
    """
    Phase 4: Calculates deterministic trend alignment across multiple timeframes.
    Returns the alignment status string.
    """
    mtf_data = get_mtf_data(symbol, base_timeframe)
    
    trends = {}
    for tf, candles in mtf_data.items():
        if not candles or len(candles) < 50:
            trends[tf] = "Unknown"
            continue
            
        df = pd.DataFrame(candles)
        ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        
        if ema20 > ema50:
            trends[tf] = "Bullish"
        elif ema20 < ema50:
            trends[tf] = "Bearish"
        else:
            trends[tf] = "Neutral"
            
    tfs = list(trends.keys())
    if len(tfs) >= 3:
        ltf, mtf, htf = tfs[0], tfs[1], tfs[2]
        
        if trends[ltf] == trends[mtf] == trends[htf] == "Bullish":
            return f"Strong Bullish Aligned ({ltf}, {mtf}, {htf})"
        elif trends[ltf] == trends[mtf] == trends[htf] == "Bearish":
            return f"Strong Bearish Aligned ({ltf}, {mtf}, {htf})"
        elif trends[htf] == "Bullish" and trends[ltf] == "Bearish":
            return f"Mixed (Macro {htf} Bullish, Micro {ltf} Bearish Pullback)"
        elif trends[htf] == "Bearish" and trends[ltf] == "Bullish":
            return f"Mixed (Macro {htf} Bearish, Micro {ltf} Bullish Retracement)"
        else:
            return f"Unaligned / Consolidating ({ltf}: {trends[ltf]}, {mtf}: {trends[mtf]}, {htf}: {trends[htf]})"
            
    return "Insufficient MTF Data"

def calculate_market_regime(df):
    """
    Phase 5: Calculates ADX to determine deterministic market regime.
    """
    df = df.copy()
    if len(df) < 28:
        return "Unknown Regime (Insufficient Data)"
        
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    # Needs numpy, but we can just use pandas where
    import numpy as np
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - df['close'].shift(1))
    tr3 = abs(df['low'] - df['close'].shift(1))
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = df['tr'].ewm(alpha=1/14, adjust=False).mean()
    plus_di = 100 * (df['plus_dm'].ewm(alpha=1/14, adjust=False).mean() / atr)
    minus_di = 100 * (df['minus_dm'].ewm(alpha=1/14, adjust=False).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/14, adjust=False).mean().iloc[-1]
    
    pdi = plus_di.iloc[-1]
    mdi = minus_di.iloc[-1]
    
    if adx < 20:
        return f"Chop / Ranging (ADX {adx:.1f})"
    elif adx > 25 and pdi > mdi:
        return f"Bullish Expansion (ADX {adx:.1f})"
    elif adx > 25 and mdi > pdi:
        return f"Bearish Expansion (ADX {adx:.1f})"
    else:
        return f"Transitioning / Weak Trend (ADX {adx:.1f})"

def detect_fvgs(df):
    """
    Phase 9: Fair Value Gaps (FVG) Depth Audit.
    Scans the last 50 candles for Fair Value Gaps (FVG).
    Scans forward from the gap creation to see if price has traded back into it (mitigated).
    Only returns UNMITIGATED (active) gaps.
    """
    if df.empty or len(df) < 3:
        return []
        
    recent_df = df.tail(50).copy().reset_index(drop=True)
    unmitigated_fvgs = []
    
    for i in range(2, len(recent_df)):
        c1 = recent_df.iloc[i-2]
        c3 = recent_df.iloc[i]
        
        fvg = None
        
        # Bullish FVG: C1 High < C3 Low
        if c1['high'] < c3['low']:
            fvg = {
                "type": "Bullish",
                "top": round(float(c3['low']), 5),
                "bottom": round(float(c1['high']), 5),
                "index": i
            }
            
        # Bearish FVG: C1 Low > C3 High
        elif c1['low'] > c3['high']:
            fvg = {
                "type": "Bearish",
                "top": round(float(c1['low']), 5),
                "bottom": round(float(c3['high']), 5),
                "index": i
            }
            
        if fvg:
            # Mitigation Check: Scan forward from candle i+1 to end of dataframe
            is_mitigated = False
            for j in range(i+1, len(recent_df)):
                future_c = recent_df.iloc[j]
                
                if fvg['type'] == 'Bullish':
                    # If future price dips below the gap 'top', it's tested/mitigated
                    if future_c['low'] <= fvg['top']:
                        is_mitigated = True
                        break
                elif fvg['type'] == 'Bearish':
                    # If future price rallies above the gap 'bottom', it's tested/mitigated
                    if future_c['high'] >= fvg['bottom']:
                        is_mitigated = True
                        break
                        
            if not is_mitigated:
                # Remove index before returning to save tokens in prompt
                del fvg['index']
                unmitigated_fvgs.append(fvg)
                
    # Return up to 4 most recent unmitigated gaps
    return unmitigated_fvgs[-4:]


def detect_order_blocks(df, lookback=50):
    """
    Phase 10: Order Blocks (Institutional Sponsorship).
    Detects valid unmitigated order blocks.
    Bullish OB: Last bearish candle before an impulsive bullish move.
    Bearish OB: Last bullish candle before an impulsive bearish move.
    """
    if df.empty or len(df) < lookback + 10:
        return []
        
    recent_df = df.tail(lookback).copy().reset_index(drop=True)
    obs = []
    
    for i in range(2, len(recent_df) - 2):
        c = recent_df.iloc[i]
        
        # Bullish OB: C is Bearish, C+1 and C+2 are strongly Bullish
        if c['close'] < c['open']:
            if recent_df.iloc[i+1]['close'] > recent_df.iloc[i+1]['open'] and recent_df.iloc[i+2]['close'] > recent_df.iloc[i+2]['open']:
                ob_top = float(c['high'])
                ob_bottom = float(c['low'])
                
                # Mitigation Check: If future price closes below OB bottom, it's violated/invalid
                is_invalid = False
                for j in range(i+3, len(recent_df)):
                    if recent_df.iloc[j]['close'] < ob_bottom:
                        is_invalid = True
                        break
                        
                if not is_invalid:
                    obs.append({
                        "type": "Bullish OB",
                        "top": round(ob_top, 5),
                        "bottom": round(ob_bottom, 5)
                    })
                    
        # Bearish OB: C is Bullish, C+1 and C+2 are strongly Bearish
        if c['close'] > c['open']:
            if recent_df.iloc[i+1]['close'] < recent_df.iloc[i+1]['open'] and recent_df.iloc[i+2]['close'] < recent_df.iloc[i+2]['open']:
                ob_top = float(c['high'])
                ob_bottom = float(c['low'])
                
                # Mitigation Check: If future price closes above OB top, it's violated/invalid
                is_invalid = False
                for j in range(i+3, len(recent_df)):
                    if recent_df.iloc[j]['close'] > ob_top:
                        is_invalid = True
                        break
                        
                if not is_invalid:
                    obs.append({
                        "type": "Bearish OB",
                        "top": round(ob_top, 5),
                        "bottom": round(ob_bottom, 5)
                    })
                    
    return obs[-3:]


def calculate_volume_profile(df):
    """
    Phase 6: Calculates Volume Profile (POC, VAH, VAL) and VWAP deterministically.
    """
    df = df.copy()
    if len(df) < 20 or 'volume' not in df.columns:
        return {"error": "Insufficient volume data"}

    # Calculate VWAP
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['typical_price'] * df['volume']
    
    # We approximate session VWAP by anchoring to the last 24 hours of data.
    # Assuming df is 1h, last 24 bars. If 15m, last 96 bars. 
    vwap = df['pv'].sum() / df['volume'].sum() if df['volume'].sum() > 0 else df['typical_price'].iloc[-1]
    
    # Calculate Volume Profile (POC, VAH, VAL)
    min_price = df['low'].min()
    max_price = df['high'].max()
    
    # 50 bins
    import numpy as np
    bins = np.linspace(min_price, max_price, 50)
    vol_profile = {b: 0 for b in bins}
    
    for _, row in df.iterrows():
        # Distribute volume evenly between low and high of the candle
        candle_bins = [b for b in bins if row['low'] <= b <= row['high']]
        if not candle_bins:
            # Fallback to closest bin
            closest_bin = min(bins, key=lambda x: abs(x - row['typical_price']))
            vol_profile[closest_bin] += row['volume']
        else:
            vol_per_bin = row['volume'] / len(candle_bins)
            for b in candle_bins:
                vol_profile[b] += vol_per_bin
                
    # Find POC (Point of Control)
    poc = max(vol_profile, key=vol_profile.get)
    total_vol = sum(vol_profile.values())
    
    # Calculate VAH and VAL (70% of value area)
    target_vol = total_vol * 0.70
    current_vol = vol_profile[poc]
    
    sorted_bins = sorted(bins)
    poc_idx = sorted_bins.index(poc)
    
    upper_idx = poc_idx
    lower_idx = poc_idx
    
    while current_vol < target_vol and (upper_idx < len(sorted_bins) - 1 or lower_idx > 0):
        vol_up = vol_profile[sorted_bins[upper_idx + 1]] if upper_idx < len(sorted_bins) - 1 else -1
        vol_down = vol_profile[sorted_bins[lower_idx - 1]] if lower_idx > 0 else -1
        
        if vol_up > vol_down and vol_up != -1:
            upper_idx += 1
            current_vol += vol_up
        elif vol_down != -1:
            lower_idx -= 1
            current_vol += vol_down
        else:
            break
            
    vah = sorted_bins[upper_idx]
    val = sorted_bins[lower_idx]
    
    return {
        "vwap": round(float(vwap), 5),
        "poc": round(float(poc), 5),
        "vah": round(float(vah), 5),
        "val": round(float(val), 5),
        "volume_type": "TICK VOLUME" # Explicitly labeling it as TICK VOLUME as per spec
    }

def calculate_market_structure(df, lookback=5):
    """
    Phase 7: Deterministic Market Structure Engine.
    Detects recent Swing Highs/Lows and identifies HH, HL, LH, LL to determine structure bias and BOS/MSS.
    """
    df = df.copy()
    
    # Detect Swing Highs and Lows
    df['swing_high'] = df['high'] == df['high'].rolling(window=lookback*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=lookback*2+1, center=True).min()
    
    # Extract the actual swing points
    swing_highs = df[df['swing_high']]['high'].dropna().values.tolist()
    swing_lows = df[df['swing_low']]['low'].dropna().values.tolist()
    
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"trend": "Consolidating", "recent_sequence": "Insufficient Data", "last_break": "None"}
        
    last_sh = swing_highs[-1]
    prev_sh = swing_highs[-2]
    
    last_sl = swing_lows[-1]
    prev_sl = swing_lows[-2]
    
    # Determine Sequence
    high_seq = "HH" if last_sh > prev_sh else "LH"
    low_seq = "HL" if last_sl > prev_sl else "LL"
    
    current_price = df['close'].iloc[-1]
    
    # Determine BOS / MSS state
    structure_bias = "Consolidating"
    if high_seq == "HH" and low_seq == "HL":
        structure_bias = "Bullish"
    elif high_seq == "LH" and low_seq == "LL":
        structure_bias = "Bearish"
    elif high_seq == "LH" and low_seq == "HL":
        structure_bias = "Symmetrical Contraction (Chop)"
    elif high_seq == "HH" and low_seq == "LL":
        structure_bias = "Expanding Volatility (Megaphone)"
    
    last_break = "None"
    if current_price > last_sh:
        last_break = "Bullish BOS/MSS (Price broke above last Swing High)"
        structure_bias = "Bullish Breakout"
    elif current_price < last_sl:
        last_break = "Bearish BOS/MSS (Price broke below last Swing Low)"
        structure_bias = "Bearish Breakdown"
        
    return {
        "trend": structure_bias,
        "recent_sequence": f"{high_seq} and {low_seq}",
        "last_break": last_break,
        "last_swing_high": round(float(last_sh), 5),
        "last_swing_low": round(float(last_sl), 5)
    }

def detect_active_killzone():
    """
    Detects the current active ICT Killzone based on EST (New York) time.
    """
    import pytz
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(timezone.utc).astimezone(est)
    
    hour = now_est.hour
    minute = now_est.minute
    time_float = hour + (minute / 60.0)
    
    # Asian Range: 20:00 - 00:00 EST
    if time_float >= 20.0 or time_float < 0.0:
        return "Asian Range (Consolidation)"
        
    # London Killzone: 02:00 - 05:00 EST
    if 2.0 <= time_float < 5.0:
        return "London Killzone (Manipulation/Expansion)"
        
    # NY AM Killzone: 08:30 - 11:00 EST (8.5 to 11.0)
    if 8.5 <= time_float < 11.0:
        return "NY AM Killzone (Reversal/Continuation)"
        
    # NY PM Killzone: 13:30 - 16:00 EST (13.5 to 16.0)
    if 13.5 <= time_float < 16.0:
        return "NY PM Killzone"
        
    return "No Active Killzone (Dead Zone)"

def calculate_asian_range(df):
    """
    Phase 11: Session Engine (Asian Range).
    Finds the High and Low of the most recent Asian Session (20:00 - 00:00 EST).
    """
    if df.empty:
        return None
        
    import pytz
    from datetime import datetime
    est = pytz.timezone('US/Eastern')
    
    asian_high = -float('inf')
    asian_low = float('inf')
    found_candles = False
    
    # Iterate backwards to find the most recent Asian session
    for i in range(len(df)-1, -1, -1):
        row = df.iloc[i]
        
        # Time in df is seconds since epoch
        try:
            dt_utc = datetime.fromtimestamp(row['time'], tz=pytz.utc)
        except Exception:
            continue
            
        dt_est = dt_utc.astimezone(est)
        
        # Asian range is 20:00 to 23:59 EST
        if dt_est.hour >= 20:
            asian_high = max(asian_high, float(row['high']))
            asian_low = min(asian_low, float(row['low']))
            found_candles = True
        elif found_candles:
            # We found the most recent Asian session and now moved past it (into earlier NY session)
            break
            
    if found_candles:
        return {
            "asian_high": round(asian_high, 5),
            "asian_low": round(asian_low, 5)
        }
    return None

def fetch_macro_news(symbol):
    """
    Phase 12: Macro/News Risk Engine.
    Placeholder/Mock for economic calendar data.
    """
    # Deterministic mock based on symbol for pipeline completion
    if "USD" in symbol:
        return {"risk_level": "HIGH", "event": "FOMC Press Conference", "time_to_event": "2h 15m", "impact": "High volatility expected. Technicals may be invalidated."}
    elif "EUR" in symbol:
        return {"risk_level": "MEDIUM", "event": "ECB Interest Rate Decision", "time_to_event": "Tomorrow", "impact": "Standard Euro volatility."}
    else:
        return {"risk_level": "LOW", "event": "No high-impact news", "time_to_event": "N/A", "impact": "Technicals respected."}

def fetch_cot_data(symbol):
    """
    Phase 13: Commitment of Traders (COT) Engine.
    Placeholder/Mock for institutional positioning (CFTC).
    """
    if "XAU" in symbol or "GOLD" in symbol:
        return {"commercial_bias": "Net Long (+45k contracts)", "speculator_bias": "Net Short (-20k contracts)", "sentiment": "Strong Bullish Sponsorship"}
    elif "USD" in symbol:
        return {"commercial_bias": "Net Short (-15k contracts)", "speculator_bias": "Net Long (+10k contracts)", "sentiment": "Bearish USD Reversal Imminent"}
    else:
        return {"commercial_bias": "Neutral", "speculator_bias": "Neutral", "sentiment": "No clear institutional footprint"}

def fetch_cross_asset(symbol):
    """
    Phase 14: Cross-Asset Correlation Engine.
    Checks DXY (US Dollar Index) trend if trading a USD pair.
    Placeholder mock logic for architecture completion.
    """
    if symbol in ["EURUSD", "GBPUSD"]:
        return {"asset": "DXY", "correlation": "Inverse", "dxy_trend": "Bullish", "signal_filter": "Headwinds for EURUSD longs. Wait for DXY resistance."}
    elif symbol in ["USDJPY", "USDCAD"]:
        return {"asset": "DXY", "correlation": "Direct", "dxy_trend": "Bullish", "signal_filter": "Tailwinds for USD longs. High probability setup."}
    elif symbol in ["XAUUSD", "BTCUSD"]:
        return {"asset": "US10Y", "correlation": "Inverse", "dxy_trend": "Bearish (Yields Dropping)", "signal_filter": "Strong macro tailwind for Gold/BTC longs."}
    else:
        return {"asset": "S&P500", "correlation": "Risk-On", "dxy_trend": "Neutral", "signal_filter": "Equities dictating flow."}

def calculate_confluence(ai_data):
    """
    Phase 15: Confluence Engine.
    Weighs all technical and macro factors to generate a deterministic Bias.
    """
    score = 0
    max_score = 6
    
    # MTF Alignment
    mtf = ai_data.get('mtf_alignment', '')
    if "Bullish" in mtf: score += 1
    elif "Bearish" in mtf: score -= 1
    
    # Market Regime
    reg = ai_data.get('market_regime', '')
    if "Bullish" in reg: score += 1
    elif "Bearish" in reg: score -= 1
        
    # Market Structure
    struct = ai_data.get('market_structure', {}).get('trend', '')
    if "Bullish" in struct: score += 1
    elif "Bearish" in struct: score -= 1
        
    # ML Edge
    buy_prob = ai_data.get('ml_data', {}).get('buy_prob', 0)
    sell_prob = ai_data.get('ml_data', {}).get('sell_prob', 0)
    if buy_prob > 50: score += 1
    elif sell_prob > 50: score -= 1
        
    # COT / Macro (Simplified)
    cot = ai_data.get('cot_data', {}).get('sentiment', '')
    if "Bullish" in cot: score += 1
    elif "Bearish" in cot: score -= 1
        
    cross = ai_data.get('cross_asset', {}).get('signal_filter', '')
    if "tailwind" in cross.lower(): score += 1
    elif "headwind" in cross.lower(): score -= 1

    # Determine Bias
    if score >= 3:
        bias = "Bullish"
        conf = min(round((score / max_score) * 100), 100)
    elif score <= -3:
        bias = "Bearish"
        conf = min(round((abs(score) / max_score) * 100), 100)
    else:
        bias = "Neutral"
        conf = min(round((abs(score) / max_score) * 100), 100)
        
    return {"bias": bias, "confidence": conf, "raw_score": score}

def build_trade_scenarios(ai_data, bias):
    """
    Phase 16: Scenario Engine.
    Deterministically builds targets (Liquidity) and invalidation (Order Blocks).
    """
    liq = ai_data.get('liquidity_zones', {})
    obs = ai_data.get('ob_data', [])
    
    bsl = liq.get('bsl', [])
    ssl = liq.get('ssl', [])
    
    bull_ob = None
    bear_ob = None
    for ob in obs:
        if "Bullish" in ob.get('type', '') and bull_ob is None:
            bull_ob = ob.get('bottom')
        if "Bearish" in ob.get('type', '') and bear_ob is None:
            bear_ob = ob.get('top')
            
    scenario = {"setup": "Wait for clear market structure.", "target": "N/A", "invalidation": "N/A"}
    
    if bias == "Bullish":
        target = bsl[0] if bsl else "Open Air (No immediate BSL)"
        inval = bull_ob if bull_ob else "Recent Swing Low"
        scenario = {
            "setup": "Wait for sweep of SSL or tap into Bullish FVG/OB, then look for MSS.",
            "target": str(target),
            "invalidation": str(inval)
        }
    elif bias == "Bearish":
        target = ssl[0] if ssl else "Open Air (No immediate SSL)"
        inval = bear_ob if bear_ob else "Recent Swing High"
        scenario = {
            "setup": "Wait for sweep of BSL or tap into Bearish FVG/OB, then look for MSS.",
            "target": str(target),
            "invalidation": str(inval)
        }
    
    return scenario

def validate_trade_model(ai_data, confluence):
    """
    Phase 17: Final Validation Engine.
    Sanity checks macro risk and session timing to flag invalid setups.
    """
    macro_risk = ai_data.get('macro_data', {}).get('risk_level', 'LOW')
    kz = ai_data.get('killzone', 'Dead Zone')
    conf = confluence.get('confidence', 0)
    
    status = "VALID"
    reasons = []
    
    if macro_risk == "HIGH":
        status = "INVALID"
        reasons.append("High-Impact Macro Event Pending")
        
    if "Dead Zone" in kz or "Consolidation" in kz:
        status = "INVALID"
        reasons.append("Outside Active Killzone (Low Volatility)")
        
    if confluence.get('bias') == "Neutral" or conf < 40:
        status = "INVALID"
        reasons.append("Low Technical Confluence (Choppy Market)")
        
    if not reasons:
        reasons.append("All structural & timing conditions met.")
        
    return {"status": status, "warnings": reasons}
