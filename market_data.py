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
