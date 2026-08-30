import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

def map_symbol_to_yf(sym):
    sym = str(sym).upper()
    if "XAU" in sym or "GOLD" in sym: return "GC=F"
    if "BTC" in sym: return "BTC-USD"
    if "ETH" in sym: return "ETH-USD"
    if "SPX" in sym or "US500" in sym or "500" in sym: return "^GSPC"
    if "NAS" in sym or "US100" in sym or "100" in sym: return "^IXIC"
    if "US30" in sym or "DOW" in sym: return "^DJI"
    if "GER" in sym or "DAX" in sym: return "^GDAXI"
    if "USD" in sym or "EUR" in sym or "GBP" in sym or "JPY" in sym:
        return f"{sym}=X"
    return None

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def run_backtest(symbol, timeframe="1h", strategy="Trend Continuation", risk_pct=1.0, sl_atr=1.5, tp_atr=2.0, capital=10000.0):
    """
    Runs a mechanical backtest over historical data.
    """
    yf_sym = map_symbol_to_yf(symbol)
    if not yf_sym:
        return {"error": f"Symbol {symbol} not supported for backtesting."}

    # Map timeframe
    period = "1y"
    interval = "1h"
    if timeframe.lower() == "1d" or timeframe.lower() == "d":
        period = "5y"
        interval = "1d"
    elif timeframe.lower() == "15m":
        period = "60d"
        interval = "15m"

    try:
        df = yf.download(yf_sym, period=period, interval=interval, progress=False)
        if df.empty:
            return {"error": "Failed to fetch historical data from Yahoo Finance."}
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
    except Exception as e:
        return {"error": f"Data fetch error: {e}"}

    # Calculate indicators
    df['RSI'] = calc_rsi(df['Close'], 14)
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['ATR'] = calc_atr(df, 14)
    df = df.dropna()

    trades = []
    equity_curve = []
    current_capital = capital
    
    in_trade = False
    trade_dir = ""
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    entry_time = None
    
    # Simple mechanical simulation
    for idx, row in df.iterrows():
        equity_curve.append({"time": idx, "equity": current_capital})
        
        if in_trade:
            # Check exit
            close = float(row['Close'])
            high = float(row['High'])
            low = float(row['Low'])
            
            exit_hit = False
            exit_price = 0.0
            
            if trade_dir == "BUY":
                if low <= sl:
                    exit_hit = True
                    exit_price = sl
                elif high >= tp:
                    exit_hit = True
                    exit_price = tp
            else:
                if high >= sl:
                    exit_hit = True
                    exit_price = sl
                elif low <= tp:
                    exit_hit = True
                    exit_price = tp
                    
            if exit_hit:
                # Calculate PnL (Risk was strictly risk_pct of capital at entry)
                risk_amt = current_capital * (risk_pct / 100.0)
                risk_per_share = abs(entry_price - sl)
                shares = risk_amt / risk_per_share if risk_per_share > 0 else 0
                
                if trade_dir == "BUY":
                    pnl = shares * (exit_price - entry_price)
                else:
                    pnl = shares * (entry_price - exit_price)
                    
                current_capital += pnl
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": idx,
                    "direction": trade_dir,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "equity": current_capital
                })
                in_trade = False
                
        if not in_trade:
            # Check Entry
            rsi = row['RSI']
            ema20 = row['EMA_20']
            ema50 = row['EMA_50']
            close = float(row['Close'])
            atr = row['ATR']
            
            signal = None
            if strategy == "Trend Continuation":
                # Buy when fast EMA > slow EMA and price pulls back to fast EMA, RSI > 50
                if ema20 > ema50 and close <= ema20 and rsi > 50:
                    signal = "BUY"
                elif ema20 < ema50 and close >= ema20 and rsi < 50:
                    signal = "SELL"
            elif strategy == "Mean Reversion":
                # Buy when RSI < 30, Sell when RSI > 70
                if rsi < 30:
                    signal = "BUY"
                elif rsi > 70:
                    signal = "SELL"
                    
            if signal:
                in_trade = True
                trade_dir = signal
                entry_price = close
                entry_time = idx
                
                if signal == "BUY":
                    sl = entry_price - (atr * sl_atr)
                    tp = entry_price + (atr * tp_atr)
                else:
                    sl = entry_price + (atr * sl_atr)
                    tp = entry_price - (atr * tp_atr)
                    
    # Generate Metrics
    if not trades:
        return {"error": "No trades executed for this strategy."}
        
    df_trades = pd.DataFrame(trades)
    wins = df_trades[df_trades['pnl'] > 0]
    losses = df_trades[df_trades['pnl'] <= 0]
    
    win_rate = (len(wins) / len(df_trades)) * 100
    gross_profit = wins['pnl'].sum() if not wins.empty else 0
    gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1
    profit_factor = gross_profit / gross_loss
    
    # Calculate Max Drawdown
    eq_series = pd.DataFrame(equity_curve).set_index("time")['equity']
    roll_max = eq_series.cummax()
    drawdown = eq_series / roll_max - 1.0
    max_dd = drawdown.min() * 100
    
    return {
        "metrics": {
            "Total Trades": len(df_trades),
            "Win Rate": f"{win_rate:.1f}%",
            "Profit Factor": f"{profit_factor:.2f}",
            "Max Drawdown": f"{max_dd:.1f}%",
            "Final Capital": f"${current_capital:,.2f}"
        },
        "trades": df_trades.to_dict(orient="records"),
        "equity_curve": equity_curve
    }
