import pandas as pd
try:
    import yfinance as yf
except ImportError:
    yf = None
import numpy as np
import time
from datetime import datetime, timezone
import database
import account_state

MAX_TOTAL_OPEN_RISK_PCT = 15.0 # Max 15% of equity at risk globally
MAX_SYMBOL_EXPOSURE = 2 # Max 2 open positions on the same symbol
MAX_DIRECTIONAL_EXPOSURE = 4 # Max 4 open positions in the same direction across the portfolio
HIGH_CORRELATION_THRESHOLD = 0.80 # 80% correlation is considered high

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

def generate_correlation_matrix(symbols, window=20):
    """
    Downloads daily data for the given symbols and calculates the rolling correlation matrix.
    Saves the correlations to the database.
    """
    valid_symbols = []
    yf_tickers = []
    for s in symbols:
        yfs = map_symbol_to_yf(s)
        if yfs:
            valid_symbols.append(s)
            yf_tickers.append(yfs)
            
    if len(yf_tickers) < 2:
        return
        
    try:
        # Download roughly enough days to cover the window (e.g. 60 days for 20 window)
        data = yf.download(yf_tickers, period="60d", interval="1d", progress=False)
        if data.empty or 'Close' not in data:
            return
            
        closes = data['Close']
        if isinstance(closes, pd.DataFrame):
            # Calculate log returns
            returns = np.log(closes / closes.shift(1)).dropna()
            # Calculate correlation matrix using the last `window` periods
            corr_matrix = returns.tail(window).corr()
            
            # Save to database
            for i in range(len(valid_symbols)):
                for j in range(i+1, len(valid_symbols)):
                    sym1 = valid_symbols[i]
                    sym2 = valid_symbols[j]
                    yf1 = yf_tickers[i]
                    yf2 = yf_tickers[j]
                    
                    if yf1 in corr_matrix.columns and yf2 in corr_matrix.columns:
                        corr_val = corr_matrix.loc[yf1, yf2]
                        if not pd.isna(corr_val):
                            database.save_correlation(sym1, sym2, window, float(corr_val))
    except Exception as e:
        print(f"Error generating correlation matrix: {e}")

def get_portfolio_risk_status(account_type="MT5", new_symbol=None, new_direction=None, new_risk_usd=0.0):
    """
    Evaluates whether a new trade breaches portfolio-level constraints.
    Returns: {"is_valid": bool, "error": str}
    """
    state = account_state.get_account_state(account_type)
    if state["status"] != "success":
        return {"is_valid": False, "error": f"Cannot evaluate portfolio risk. Broker state unavailable: {state.get('message')}"}
        
    equity = state["equity"]
    open_positions = state["open_positions"]
    total_open_risk = state["total_open_risk"]
    
    # 1. Total Open Risk Limit
    projected_risk = total_open_risk + new_risk_usd
    projected_risk_pct = (projected_risk / equity) * 100.0 if equity > 0 else 0
    if projected_risk_pct > MAX_TOTAL_OPEN_RISK_PCT:
        return {"is_valid": False, "error": f"PORTFOLIO RISK: Projected risk {projected_risk_pct:.1f}% exceeds max {MAX_TOTAL_OPEN_RISK_PCT}%."}
        
    # 2. Symbol Exposure Limit
    if new_symbol:
        sym_count = sum(1 for p in open_positions if p.get("symbol") == new_symbol)
        if sym_count >= MAX_SYMBOL_EXPOSURE:
            return {"is_valid": False, "error": f"PORTFOLIO EXPOSURE: Max {MAX_SYMBOL_EXPOSURE} positions allowed for {new_symbol}."}
            
    # 3. Directional Exposure Limit
    if new_direction:
        dir_count = sum(1 for p in open_positions if p.get("direction") == new_direction)
        if dir_count >= MAX_DIRECTIONAL_EXPOSURE:
            return {"is_valid": False, "error": f"PORTFOLIO EXPOSURE: Max {MAX_DIRECTIONAL_EXPOSURE} positions allowed in the {new_direction} direction overall."}
            
    # 4. Correlated Asset Exposure Limit
    if new_symbol and new_direction:
        correlations = database.get_correlations(window=20)
        for pos in open_positions:
            pos_sym = pos.get("symbol")
            pos_dir = pos.get("direction")
            
            # Check correlation if symbols differ
            if pos_sym != new_symbol:
                corr = correlations.get((new_symbol, pos_sym)) or correlations.get((pos_sym, new_symbol), 0.0)
                
                # If highly positively correlated and taking same direction
                if corr > HIGH_CORRELATION_THRESHOLD and new_direction == pos_dir:
                    return {"is_valid": False, "error": f"CORRELATION RISK: {new_symbol} is highly correlated ({corr:.2f}) to open position {pos_sym}. Avoid taking same-direction trades."}
                
                # If highly negatively correlated and taking opposite direction
                if corr < -HIGH_CORRELATION_THRESHOLD and new_direction != pos_dir:
                    return {"is_valid": False, "error": f"CORRELATION RISK: {new_symbol} is highly negatively correlated ({corr:.2f}) to open {pos_sym}. Avoid opposing direction trades."}

    return {"is_valid": True, "error": None}
