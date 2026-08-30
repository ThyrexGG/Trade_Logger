import pandas as pd
import numpy as np

def calculate_performance_metrics(df_trades, initial_balance=10000.0):
    """
    Computes deterministic trading performance metrics according to the Master Specification.
    Formulas:
    - Win Rate: Winning Trades / Total Closed Trades
    - Profit Factor: Gross Profit / Absolute Gross Loss
    - Expectancy: (Avg Win * Win Rate) - (Avg Loss * Loss Rate)
    - Max Drawdown: Peak Balance - Trough Balance / Peak Balance
    - SQN: (Mean PnL / StdDev PnL) * sqrt(N)
    """
    init_bal = float(initial_balance) if initial_balance and initial_balance > 0 else 10000.0
    
    empty_result = {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "break_even_trades": 0,
        "win_rate": 0.0,
        "loss_rate": 0.0,
        "total_net_pnl": 0.0,
        "total_gross_profit": 0.0,
        "total_gross_loss": 0.0,
        "profit_factor": 1.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "win_loss_ratio": 1.0,
        "expectancy": 0.0,
        "max_drawdown_usd": 0.0,
        "max_drawdown_pct": 0.0,
        "sqn": 0.0,
        "gain_pct": 0.0,
        "final_balance": init_bal,
        "peak_balance": init_bal,
        "avg_duration_minutes": 0.0,
        "long_stats": {"trades": 0, "win_rate": 0.0, "pnl": 0.0},
        "short_stats": {"trades": 0, "win_rate": 0.0, "pnl": 0.0},
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "best_symbols": [],
        "worst_symbols": []
    }

    if df_trades is None or df_trades.empty:
        return empty_result

    df = df_trades.sort_values(by="exit_time", ascending=True).reset_index(drop=True).copy()
    
    # Core Counts
    total_trades = len(df)
    if total_trades == 0:
        return empty_result

    wins_df = df[df["net_profit"] > 0]
    losses_df = df[df["net_profit"] < 0]
    be_df = df[df["net_profit"] == 0]

    win_count = len(wins_df)
    loss_count = len(losses_df)
    be_count = len(be_df)

    win_rate = (win_count / total_trades) * 100.0
    loss_rate = (loss_count / total_trades) * 100.0

    # Profits
    gross_profit = float(wins_df["net_profit"].sum()) if not wins_df.empty else 0.0
    gross_loss = float(abs(losses_df["net_profit"].sum())) if not losses_df.empty else 0.0
    net_pnl = float(df["net_profit"].sum())

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    else:
        profit_factor = round(gross_profit, 2) if gross_profit > 0 else 1.0

    avg_win = float(wins_df["net_profit"].mean()) if not wins_df.empty else 0.0
    avg_loss = float(abs(losses_df["net_profit"].mean())) if not losses_df.empty else 0.0
    win_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else (round(avg_win, 2) if avg_win > 0 else 1.0)

    # Expectancy Formula: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
    expectancy = (win_rate / 100.0 * avg_win) - (loss_rate / 100.0 * avg_loss)

    # Balance Curve & Drawdown Analysis
    df["balance"] = init_bal + df["net_profit"].cumsum()
    peaks = df["balance"].cummax()
    drawdowns_usd = peaks - df["balance"]
    drawdowns_pct = (drawdowns_usd / peaks) * 100.0

    max_dd_usd = float(drawdowns_usd.max()) if not drawdowns_usd.empty else 0.0
    max_dd_pct = float(drawdowns_pct.max()) if not drawdowns_pct.empty else 0.0
    peak_balance = float(peaks.max()) if not peaks.empty else init_bal
    final_balance = float(df["balance"].iloc[-1])
    gain_pct = (net_pnl / init_bal) * 100.0

    # Van Tharp SQN Formula: (Mean PnL / StdDev PnL) * sqrt(N)
    pnl_array = df["net_profit"].values
    if len(pnl_array) > 1:
        std_pnl = np.std(pnl_array)
        sqn = float((np.mean(pnl_array) / std_pnl) * np.sqrt(len(pnl_array))) if std_pnl > 0 else 0.0
    else:
        sqn = 0.0

    # Duration
    avg_duration = float(df["duration_minutes"].mean()) if "duration_minutes" in df.columns else 0.0

    # Long vs Short
    longs = df[df["direction"].str.upper().str.contains("BUY|LONG", na=False)]
    shorts = df[df["direction"].str.upper().str.contains("SELL|SHORT", na=False)]

    long_stats = {
        "trades": len(longs),
        "win_rate": round((len(longs[longs["net_profit"] > 0]) / len(longs)) * 100.0, 1) if not longs.empty else 0.0,
        "pnl": round(float(longs["net_profit"].sum()), 2) if not longs.empty else 0.0
    }
    short_stats = {
        "trades": len(shorts),
        "win_rate": round((len(shorts[shorts["net_profit"] > 0]) / len(shorts)) * 100.0, 1) if not shorts.empty else 0.0,
        "pnl": round(float(shorts["net_profit"].sum()), 2) if not shorts.empty else 0.0
    }

    # Best & Worst Symbols
    sym_groups = df.groupby("symbol")["net_profit"].sum().reset_index()
    best_syms = sym_groups.sort_values(by="net_profit", ascending=False).head(3).to_dict(orient="records")
    worst_syms = sym_groups.sort_values(by="net_profit", ascending=True).head(3).to_dict(orient="records")

    return {
        "total_trades": total_trades,
        "winning_trades": win_count,
        "losing_trades": loss_count,
        "break_even_trades": be_count,
        "win_rate": round(win_rate, 2),
        "loss_rate": round(loss_rate, 2),
        "total_net_pnl": round(net_pnl, 2),
        "total_gross_profit": round(gross_profit, 2),
        "total_gross_loss": round(gross_loss, 2),
        "profit_factor": profit_factor,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "win_loss_ratio": win_loss_ratio,
        "expectancy": round(expectancy, 2),
        "max_drawdown_usd": round(max_dd_usd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "sqn": round(sqn, 2),
        "gain_pct": round(gain_pct, 2),
        "final_balance": round(final_balance, 2),
        "peak_balance": round(peak_balance, 2),
        "avg_duration_minutes": round(avg_duration, 1),
        "long_stats": long_stats,
        "short_stats": short_stats,
        "best_trade": round(float(df["net_profit"].max()), 2),
        "worst_trade": round(float(df["net_profit"].min()), 2),
        "best_symbols": best_syms,
        "worst_symbols": worst_syms
    }

def _calculate_subset_stats(subset_df):
    """Helper to calculate WR and Expectancy from a joined signals+trades dataframe."""
    if subset_df.empty:
        return {"count": 0, "win_rate": 0.0, "expectancy": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
    
    # Needs a net_profit column from closed_trades
    if "net_profit" not in subset_df.columns:
        return {"count": len(subset_df), "win_rate": 0.0, "expectancy": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
        
    trades = subset_df.dropna(subset=["net_profit"])
    total = len(trades)
    if total == 0:
        return {"count": len(subset_df), "win_rate": 0.0, "expectancy": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
        
    wins = trades[trades["net_profit"] > 0]
    losses = trades[trades["net_profit"] < 0]
    
    wr = len(wins) / total
    lr = len(losses) / total
    
    avg_win = float(wins["net_profit"].mean()) if not wins.empty else 0.0
    avg_loss = float(abs(losses["net_profit"].mean())) if not losses.empty else 0.0
    
    expectancy = (wr * avg_win) - (lr * avg_loss)
    
    return {
        "count": total,
        "win_rate": round(wr * 100.0, 2),
        "expectancy": round(expectancy, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2)
    }

def calculate_liquidity_performance(signals_df, trades_df):
    if signals_df.empty or trades_df.empty: return {}
    # Merge signals and trades based on broker_order_id or signal_id
    # Wait, received_signals has order_id which matches trades.trade_id or positions.position_id?
    # execution_audit_log has broker_order_id. closed_trades has trade_id = 'TRADE_' + pos_id.
    # We will assume signals_df has 'setup_type' and 'order_id'. 
    # Trades has 'trade_id' containing the order_id.
    
    # Strip prefixes to merge
    signals = signals_df.copy()
    trades = trades_df.copy()
    
    if "order_id" not in signals.columns or "trade_id" not in trades.columns:
        return {}
        
    # Standardize IDs for merging
    signals["clean_id"] = signals["order_id"].astype(str).str.replace(r'^(POS_|TRADE_)', '', regex=True)
    trades["clean_id"] = trades["trade_id"].astype(str).str.replace(r'^(POS_|TRADE_)', '', regex=True)
    
    merged = pd.merge(signals, trades, on="clean_id", how="inner")
    
    if "setup_type" not in merged.columns:
        return {}
        
    results = {}
    for setup, group in merged.groupby("setup_type"):
        results[str(setup)] = _calculate_subset_stats(group)
    return results

def calculate_killzone_performance(signals_df, trades_df):
    if signals_df.empty or trades_df.empty: return {}
    signals = signals_df.copy()
    trades = trades_df.copy()
    
    if "order_id" not in signals.columns or "trade_id" not in trades.columns:
        return {}
        
    signals["clean_id"] = signals["order_id"].astype(str).str.replace(r'^(POS_|TRADE_)', '', regex=True)
    trades["clean_id"] = trades["trade_id"].astype(str).str.replace(r'^(POS_|TRADE_)', '', regex=True)
    merged = pd.merge(signals, trades, on="clean_id", how="inner")
    
    if "session" not in merged.columns:
        return {}
        
    results = {}
    for session, group in merged.groupby("session"):
        results[str(session)] = _calculate_subset_stats(group)
    return results

def calculate_mtf_confluence(signals_df, trades_df):
    if signals_df.empty or trades_df.empty: return {}
    signals = signals_df.copy()
    trades = trades_df.copy()
    
    if "order_id" not in signals.columns or "trade_id" not in trades.columns:
        return {}
        
    signals["clean_id"] = signals["order_id"].astype(str).str.replace(r'^(POS_|TRADE_)', '', regex=True)
    trades["clean_id"] = trades["trade_id"].astype(str).str.replace(r'^(POS_|TRADE_)', '', regex=True)
    merged = pd.merge(signals, trades, on="clean_id", how="inner")
    
    if "confluence_score" not in merged.columns:
        return {}
        
    results = {}
    for score, group in merged.groupby("confluence_score"):
        results[f"Score {score}"] = _calculate_subset_stats(group)
    return results
