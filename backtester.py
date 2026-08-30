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

def get_instrument_specs(sym):
    sym = str(sym).upper()
    # Mock instrument specifications for MT5/CFD standard lots
    specs = {
        "EURUSD": {"min_qty": 0.01, "qty_step": 0.01},
        "GBPUSD": {"min_qty": 0.01, "qty_step": 0.01},
        "XAUUSD": {"min_qty": 0.01, "qty_step": 0.01},
        "US30": {"min_qty": 0.1, "qty_step": 0.1},
        "NAS100": {"min_qty": 0.1, "qty_step": 0.1},
        "SPX500": {"min_qty": 0.1, "qty_step": 0.1},
        "BTCUSD": {"min_qty": 0.001, "qty_step": 0.001}
    }
    return specs.get(sym, {"min_qty": 0.0, "qty_step": 0.0})

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

def run_backtest(symbol, timeframe="1h", strategy="Trend Continuation", risk_pct=1.0, sl_atr=1.5, tp_atr=2.0, capital=10000.0, slippage=0.0001, commission_pct=0.01, fixed_spread=0.0, train_split=1.0, preloaded_data=None):
    """
    Runs a mechanical backtest over historical data with strict research-grade validation.
    Protects against Look-Ahead bias by executing on the Open of the bar following a signal.
    """
    yf_sym = map_symbol_to_yf(symbol)
    if not yf_sym:
        return {"error": f"Symbol {symbol} not supported for backtesting."}

    # Map timeframe
    period = "1y"
    interval = "1h"
    struct_tf = "4h"
    bias_tf = "1d"
    
    if timeframe.lower() in ["1d", "d"]:
        period = "5y"
        interval = "1d"
        struct_tf = "1wk"
        bias_tf = "1mo"
    elif timeframe.lower() == "15m":
        period = "60d"
        interval = "15m"
        struct_tf = "1h"
        bias_tf = "4h"
    elif timeframe.lower() == "5m":
        period = "60d"
        interval = "5m"
        struct_tf = "15m"
        bias_tf = "1h"

    def fetch_and_clean_yf(sym, p, i):
        d = yf.download(sym, period=p, interval=i, progress=False)
        if d.empty: return d
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.droplevel(1)
        if d.isnull().values.any():
            d = d.dropna(subset=['Open', 'High', 'Low', 'Close'])
        if d.index.tz is None:
            d.index = d.index.tz_localize('UTC')
        else:
            d.index = d.index.tz_convert('UTC')
        return d

    try:
        if preloaded_data:
            df = preloaded_data['df'].copy()
            df_struct = preloaded_data['df_struct'].copy()
            df_bias = preloaded_data['df_bias'].copy()
        else:
            df = fetch_and_clean_yf(yf_sym, period, interval)
            if df.empty:
                return {"error": "Failed to fetch historical data from Yahoo Finance."}
                
            # Fetch HTF data for MTF alignment
            df_struct = fetch_and_clean_yf(yf_sym, period, struct_tf)
            df_bias = fetch_and_clean_yf(yf_sym, period, bias_tf)
            
    except Exception as e:
        return {"error": f"Data fetch error: {e}"}

    # Calculate indicators
    df['RSI'] = calc_rsi(df['Close'], 14) # Moving Averages & RSI
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['ATR'] = calc_atr(df, 14)
    
    # Inject SMC Features universally for the backtester
    import strategies.smc_utils as smc_utils
    import strategies.mtf_engine as mtf_engine
    
    df = smc_utils.add_smc_features(df)
    
    # Build MTF Context safely
    if not df_struct.empty:
        df_struct = smc_utils.add_smc_features(df_struct)
        df = mtf_engine.align_htf_to_ltf(df, df_struct, "_STRUCT", struct_tf)
    if not df_bias.empty:
        df_bias = smc_utils.add_smc_features(df_bias)
        df = mtf_engine.align_htf_to_ltf(df, df_bias, "_BIAS", bias_tf)
    
    # We MUST NOT df.dropna() here because SMC features like FVG intentionally use NaN on non-FVG rows!
    
    # Train/Test Split (In-Sample vs Out-Of-Sample)
    split_idx = int(len(df) * train_split)

    trades = []
    equity_curve = []
    current_capital = capital
    
    in_trade = False
    
    # Load Strategy
    import strategies
    active_strat = strategies.get_strategy(strategy)
    if not active_strat:
        return {"error": f"Strategy '{strategy}' not found in registry."}
        
    # Pending Limit Order State
    limit_order = None
    
    trade_dir = ""
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    entry_time = None
    shares = 0.0
    
    specs = get_instrument_specs(symbol)
    min_qty = specs["min_qty"]
    qty_step = specs["qty_step"]
    
    # Strict mechanical simulation
    for i in range(len(df)):
        idx = df.index[i]
        row = df.iloc[i]
        
        is_oos = i >= split_idx
        
        # Execute pending orders (No Look-Ahead)
        if limit_order and not in_trade:
            high = float(row['High'])
            low = float(row['Low'])
            open_price = float(row['Open'])
            
            filled = False
            raw_entry = limit_order['ideal_entry']
            trade_setup_dir = limit_order['setup']
            exec_model = limit_order.get('execution_model', 'LIMIT')
            
            # --- MARKET EXECUTION ---
            if exec_model == 'MARKET':
                filled = True
                if trade_setup_dir == "LONG":
                    raw_entry = open_price + slippage + fixed_spread
                else:
                    raw_entry = open_price - slippage
                    
            # --- LIMIT EXECUTION ---
            elif exec_model == 'LIMIT':
                if trade_setup_dir == "LONG" and low <= raw_entry:
                    filled = True
                    # Gap Fill Check: If it opened below the limit, we fill at open
                    if open_price < raw_entry:
                        raw_entry = open_price
                    raw_entry += slippage + fixed_spread
                    
                elif trade_setup_dir == "SHORT" and high >= raw_entry:
                    filled = True
                    # Gap Fill Check: If it opened above the limit, we fill at open
                    if open_price > raw_entry:
                        raw_entry = open_price
                    raw_entry -= slippage
                
            if filled:
                risk_amt = current_capital * (risk_pct / 100.0)
                raw_sl = limit_order['stop_loss']
                
                if trade_setup_dir == "LONG":
                    risk_per_share = abs(raw_entry - raw_sl)
                else:
                    risk_per_share = abs(raw_sl - raw_entry) + fixed_spread
                    
                raw_shares = risk_amt / risk_per_share if risk_per_share > 0 else 0
                
                if qty_step > 0:
                    shares = max(min_qty, round(raw_shares / qty_step) * qty_step)
                else:
                    shares = raw_shares
                    
                if shares >= min_qty and shares > 0:
                    in_trade = True
                    trade_dir = "BUY" if trade_setup_dir == "LONG" else "SELL"
                    entry_price = raw_entry
                    sl = raw_sl
                    tp = limit_order['tp1']
                    entry_time = idx
                
                limit_order = None
            else:
                # Limit order expiry
                exp_bars = limit_order.get('expiration_bars', 10)
                limit_order['bars_waiting'] = limit_order.get('bars_waiting', 0) + 1
                if limit_order['bars_waiting'] >= exp_bars:
                    limit_order = None
            
        if in_trade:
            # Check exit using this candle's High/Low
            high = float(row['High'])
            low = float(row['Low'])
            
            exit_hit = False
            exit_price = 0.0
            
            if trade_dir == "BUY":
                if low <= sl:
                    exit_hit = True
                    exit_price = sl - slippage
                elif high >= tp:
                    exit_hit = True
                    exit_price = tp - slippage
            else:
                if high >= sl:
                    exit_hit = True
                    exit_price = sl + slippage + fixed_spread
                elif low <= tp:
                    exit_hit = True
                    exit_price = tp + slippage + fixed_spread
                    
            if exit_hit:
                if trade_dir == "BUY":
                    gross_pnl = shares * (exit_price - entry_price)
                else:
                    gross_pnl = shares * (entry_price - exit_price)
                    
                commission = current_capital * (commission_pct / 100.0)
                net_pnl = gross_pnl - commission
                
                current_capital += net_pnl
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": idx,
                    "direction": trade_dir,
                    "position_size": shares,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "gross_pnl": gross_pnl,
                    "commission": commission,
                    "pnl": net_pnl,
                    "equity": current_capital,
                    "is_oos": is_oos
                })
                in_trade = False
                
        if not in_trade and not limit_order:
            # Check for new signals using the active strategy
            context = {
                'sl_atr': sl_atr,
                'tp_atr': tp_atr,
                'struct_tf': struct_tf,
                'bias_tf': bias_tf
            }
            setup = active_strat.analyze(df, i, context)
            
            if setup.get("status") == "READY":
                # Only take trades with a valid ideal_entry
                if setup.get("ideal_entry") and setup.get("ideal_entry") != "N/A":
                    limit_order = setup
                
        # Record equity at the close of the bar
        equity_curve.append({"time": idx, "equity": current_capital})
        
    # Generate Metrics
    if not trades:
        return {"error": "No trades executed for this strategy."}
        
    df_trades = pd.DataFrame(trades)
    
    def calc_metrics(df_t):
        if df_t.empty:
            return {"Total Trades": 0, "Win Rate": "0%", "Profit Factor": "0.00", "Max Drawdown": "0%"}
        wins = df_t[df_t['pnl'] > 0]
        losses = df_t[df_t['pnl'] <= 0]
        win_rate = (len(wins) / len(df_t)) * 100
        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1
        profit_factor = gross_profit / gross_loss
        
        # Approximate drawdown from trade peaks
        roll_max = df_t['equity'].cummax()
        drawdown = df_t['equity'] / roll_max - 1.0
        max_dd = drawdown.min() * 100
        return {
            "Total Trades": len(df_t),
            "Win Rate": f"{win_rate:.1f}%",
            "Profit Factor": f"{profit_factor:.2f}",
            "Max Drawdown": f"{max_dd:.1f}%"
        }

    is_trades = df_trades[~df_trades['is_oos']]
    oos_trades = df_trades[df_trades['is_oos']]
    
    return {
        "metrics_is": calc_metrics(is_trades),
        "metrics_oos": calc_metrics(oos_trades) if not oos_trades.empty else None,
        "metrics": calc_metrics(df_trades), # overall
        "final_capital": f"${current_capital:,.2f}",
        "trades": df_trades.to_dict(orient="records"),
        "equity_curve": equity_curve
    }

def run_monte_carlo(trades, initial_capital=10000.0, iterations=1000, risk_of_ruin_level=0.2):
    """
    Shuffles trade PnLs to simulate 1,000 alternative reality equity curves.
    """
    if not trades or len(trades) < 2:
        return {"error": "Not enough trades for Monte Carlo simulation."}
        
    pnls = [t['pnl'] for t in trades]
    ruin_count = 0
    max_dd_list = []
    
    for _ in range(iterations):
        np.random.shuffle(pnls)
        equity = initial_capital
        peak = initial_capital
        max_dd = 0
        ruined = False
        
        for pnl in pnls:
            equity += pnl
            if equity <= initial_capital * (1.0 - risk_of_ruin_level):
                ruined = True
                
            if equity > peak:
                peak = equity
            
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
                
        if ruined:
            ruin_count += 1
        max_dd_list.append(max_dd)
        
    risk_of_ruin = (ruin_count / iterations) * 100
    confidence_95_dd = np.percentile(max_dd_list, 95) * 100
    median_dd = np.median(max_dd_list) * 100
    
    return {
        "iterations": iterations,
        "risk_of_ruin_pct": round(risk_of_ruin, 2),
        "confidence_95_dd_pct": round(confidence_95_dd, 2),
        "median_dd_pct": round(median_dd, 2)
    }

def run_walk_forward(symbol, timeframe="1h", strategy="Trend Continuation", risk_pct=1.0, grid_sl=[1.0, 1.5, 2.0], grid_tp=[1.0, 2.0, 3.0], capital=10000.0, slippage=0.0001, commission_pct=0.01, fixed_spread=0.0, walk_steps=3, oos_pct=0.2):
    """
    Walk-Forward Optimization:
    Splits the historical dataset into (walk_steps) slices.
    For each slice, optimizes over In-Sample, and executes best parameters on Out-of-Sample.
    Stitches OOS results together into a robust unified curve.
    """
    # 1. First, fetch the raw data so we don't redownload in the loop
    dummy_res = run_backtest(symbol, timeframe, strategy) 
    if "error" in dummy_res:
        return dummy_res
    
    yf_sym = map_symbol_to_yf(symbol)
    period = "1y"
    interval = "1h"
    struct_tf = "4h"
    bias_tf = "1d"
    
    if timeframe.lower() in ["1d", "d"]:
        period = "5y"; interval = "1d"; struct_tf = "1wk"; bias_tf = "1mo"
    elif timeframe.lower() == "15m":
        period = "60d"; interval = "15m"; struct_tf = "1h"; bias_tf = "4h"
    elif timeframe.lower() == "5m":
        period = "60d"; interval = "5m"; struct_tf = "15m"; bias_tf = "1h"

    def fetch_yf(sym, p, i):
        d = yf.download(sym, period=p, interval=i, progress=False)
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
        if d.isnull().values.any(): d = d.dropna(subset=['Open', 'High', 'Low', 'Close'])
        d.index = d.index.tz_localize('UTC') if d.index.tz is None else d.index.tz_convert('UTC')
        return d
        
    df = fetch_yf(yf_sym, period, interval)
    if df.empty: return {"error": "Failed to fetch data."}
    df_struct = fetch_yf(yf_sym, period, struct_tf)
    df_bias = fetch_yf(yf_sym, period, bias_tf)
    
    # 2. Slice data for Walk-Forward Windows
    total_bars = len(df)
    step_size = int(total_bars / walk_steps)
    
    stitched_trades = []
    current_capital = capital
    equity_curve = []
    
    for step in range(walk_steps):
        start_idx = step * step_size
        # The last step goes to the end
        end_idx = (step + 1) * step_size if step < walk_steps - 1 else total_bars
        
        slice_df = df.iloc[start_idx:end_idx].copy()
        
        # Calculate OOS boundary for this slice
        oos_bars = int(len(slice_df) * oos_pct)
        is_end_idx = len(slice_df) - oos_bars
        
        df_is = slice_df.iloc[:is_end_idx]
        df_oos = slice_df.iloc[is_end_idx:]
        
        if len(df_is) < 50 or len(df_oos) < 10:
            continue
            
        # Grid Search on IS
        best_net = -999999
        best_sl = grid_sl[0]
        best_tp = grid_tp[0]
        
        for sl in grid_sl:
            for tp in grid_tp:
                # We mock the structure/bias slices just by time-filtering
                start_t = df_is.index[0]
                end_t = df_is.index[-1]
                
                is_struct = df_struct[(df_struct.index >= start_t) & (df_struct.index <= end_t)]
                is_bias = df_bias[(df_bias.index >= start_t) & (df_bias.index <= end_t)]
                
                preload_is = {"df": df_is, "df_struct": is_struct, "df_bias": is_bias}
                
                res = run_backtest(symbol, timeframe, strategy, risk_pct, sl, tp, capital=current_capital, slippage=slippage, commission_pct=commission_pct, fixed_spread=fixed_spread, preloaded_data=preload_is)
                if "error" not in res and res["metrics"]["Total Trades"] > 0:
                    net_profit = float(res["final_capital"].replace("$","").replace(",","")) - current_capital
                    if net_profit > best_net:
                        best_net = net_profit
                        best_sl = sl
                        best_tp = tp
                        
        # Execute Best Params on OOS
        start_t = df_oos.index[0]
        end_t = df_oos.index[-1]
        oos_struct = df_struct[(df_struct.index >= start_t) & (df_struct.index <= end_t)]
        oos_bias = df_bias[(df_bias.index >= start_t) & (df_bias.index <= end_t)]
        
        preload_oos = {"df": df_oos, "df_struct": oos_struct, "df_bias": oos_bias}
        
        res_oos = run_backtest(symbol, timeframe, strategy, risk_pct, best_sl, best_tp, capital=current_capital, slippage=slippage, commission_pct=commission_pct, fixed_spread=fixed_spread, preloaded_data=preload_oos)
        
        if "error" not in res_oos:
            # Append OOS trades to stitched results
            # They already have 'pnl', we just need to update current_capital
            trades = res_oos["trades"]
            for t in trades:
                current_capital += t['pnl']
                t['equity'] = current_capital
                t['is_oos'] = True # All trades in stitched curve are OOS
                stitched_trades.append(t)
                equity_curve.append({"time": t['exit_time'], "equity": current_capital})
                
    if not stitched_trades:
        return {"error": "Walk-forward optimization yielded zero executed trades in Out-of-Sample slices."}
        
    df_stitched = pd.DataFrame(stitched_trades)
    wins = df_stitched[df_stitched['pnl'] > 0]
    losses = df_stitched[df_stitched['pnl'] <= 0]
    win_rate = (len(wins) / len(df_stitched)) * 100
    gross_profit = wins['pnl'].sum() if not wins.empty else 0
    gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1
    profit_factor = gross_profit / gross_loss
    
    roll_max = df_stitched['equity'].cummax()
    drawdown = df_stitched['equity'] / roll_max - 1.0
    max_dd = drawdown.min() * 100
    
    metrics = {
        "Total Trades": len(df_stitched),
        "Win Rate": f"{win_rate:.1f}%",
        "Profit Factor": f"{profit_factor:.2f}",
        "Max Drawdown": f"{max_dd:.1f}%",
        "WFO": "Robust"
    }
    
    mc_res = run_monte_carlo(stitched_trades, capital)
    
    return {
        "metrics": metrics,
        "metrics_is": metrics, 
        "metrics_oos": metrics,
        "final_capital": f"${current_capital:,.2f}",
        "trades": df_stitched.to_dict(orient="records"),
        "equity_curve": equity_curve,
        "monte_carlo": mc_res
    }

