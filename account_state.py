import os
import time
from datetime import datetime, timezone
import database
import pandas as pd

def get_realized_pnl_today():
    """Calculates realized PnL for today from the closed_trades table."""
    try:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        df = database.pd.read_sql_query(f"SELECT net_profit FROM closed_trades WHERE exit_time LIKE '{today_str}%'", database.get_connection())
        if not df.empty:
            return float(df['net_profit'].sum())
        return 0.0
    except Exception as e:
        print(f"Error calculating realized PnL today: {e}")
        return 0.0

def get_account_state(account_type="MT5"):
    """
    Returns canonical account state by querying the broker directly.
    account_type: "MT5" or "CAPITAL"
    Returns:
    {
        "status": "success" | "error",
        "message": str,
        "balance": float,
        "equity": float,
        "margin": float,
        "free_margin": float,
        "realized_pnl": float,
        "floating_pnl": float,
        "open_positions": list of dict,
        "total_open_risk": float
    }
    """
    state = {
        "status": "error",
        "message": "Unknown account type",
        "balance": 0.0,
        "equity": 0.0,
        "margin": 0.0,
        "free_margin": 0.0,
        "realized_pnl": get_realized_pnl_today(),
        "floating_pnl": 0.0,
        "open_positions": [],
        "total_open_risk": 0.0
    }

    if account_type.upper() == "MT5":
        try:
            import mt5_sync
            if not mt5_sync.MT5_AVAILABLE:
                state["message"] = "MT5 not available on this platform"
                return state

            import MetaTrader5 as mt5
            if not mt5.initialize():
                state["message"] = f"MT5 init failed: {mt5.last_error()}"
                return state
                
            acc_info = mt5.account_info()
            if not acc_info:
                state["message"] = "Could not get MT5 account info"
                return state
                
            state["balance"] = float(acc_info.balance)
            state["equity"] = float(acc_info.equity)
            state["margin"] = float(acc_info.margin)
            state["free_margin"] = float(acc_info.margin_free)
            
            positions_raw = mt5.positions_get()
            floating_pnl = 0.0
            open_risk = 0.0
            
            if positions_raw:
                for pos in positions_raw:
                    dir_str = "BUY" if pos.type == 0 else "SELL"
                    floating_pnl += float(pos.profit) + float(pos.swap)
                    
                    # Calculate open risk based on SL
                    risk = 0.0
                    if pos.sl > 0:
                        dist = abs(pos.price_open - pos.sl)
                        contract_size = 100000.0 if ("USD" in pos.symbol or "EUR" in pos.symbol) else 100.0
                        if "BTC" in pos.symbol or "ETH" in pos.symbol or "NAS" in pos.symbol: contract_size = 1.0
                        risk = dist * pos.volume * contract_size
                        
                    state["open_positions"].append({
                        "ticket": str(pos.ticket),
                        "symbol": mt5_sync.clean_symbol(pos.symbol),
                        "direction": dir_str,
                        "volume": float(pos.volume),
                        "entry": float(pos.price_open),
                        "current_price": float(pos.price_current),
                        "sl": float(pos.sl),
                        "tp": float(pos.tp),
                        "profit": float(pos.profit),
                        "risk": risk
                    })
                    open_risk += risk
                    
            state["floating_pnl"] = floating_pnl
            state["total_open_risk"] = open_risk
            state["status"] = "success"
            state["message"] = "MT5 state fetched successfully"
            
        except Exception as e:
            state["message"] = f"Error fetching MT5 state: {e}"
            
    elif account_type.upper() == "CAPITAL":
        try:
            import capital_sync
            session_data = capital_sync.get_session()
            if not session_data:
                state["message"] = "Capital.com authentication failed"
                return state
                
            base_url = session_data["base_url"]
            headers = {
                "X-CAP-API-KEY": session_data["api_key"],
                "CST": session_data["cst"],
                "X-SECURITY-TOKEN": session_data["x_security_token"]
            }
            
            import requests
            acc_resp = requests.get(f"{base_url}/accounts", headers=headers, timeout=5)
            if acc_resp.status_code == 200:
                acc_data = acc_resp.json().get("accounts", [])
                if acc_data:
                    pref = next((a for a in acc_data if a.get("preferred")), acc_data[0])
                    bal_info = pref.get("balance", {})
                    state["balance"] = float(bal_info.get("balance", 0.0))
                    state["floating_pnl"] = float(bal_info.get("profitLoss", 0.0))
                    state["equity"] = state["balance"] + state["floating_pnl"]
                    state["margin"] = float(bal_info.get("margin", 0.0))
                    state["free_margin"] = float(bal_info.get("available", 0.0))
                    
            pos_resp = requests.get(f"{base_url}/positions", headers=headers, timeout=5)
            if pos_resp.status_code == 200:
                positions = pos_resp.json().get("positions", [])
                open_risk = 0.0
                for pos in positions:
                    deal = pos.get("position", {})
                    market = pos.get("market", {})
                    dir_str = deal.get("direction", "")
                    symbol = capital_sync.clean_symbol(market.get("epic", ""))
                    sl = float(deal.get("guaranteedStopLevel") or deal.get("stopLevel") or 0.0)
                    entry = float(deal.get("level", 0.0))
                    vol = float(deal.get("size", 0.0))
                    
                    risk = 0.0
                    if sl > 0:
                        dist = abs(entry - sl)
                        contract_size = 100000.0 if ("USD" in symbol or "EUR" in symbol) else 100.0
                        if "BTC" in symbol or "ETH" in symbol or "NAS" in symbol: contract_size = 1.0
                        risk = dist * vol * contract_size
                        
                    state["open_positions"].append({
                        "ticket": deal.get("dealId"),
                        "symbol": symbol,
                        "direction": dir_str,
                        "volume": vol,
                        "entry": entry,
                        "sl": sl,
                        "tp": float(deal.get("profitLevel", 0.0)),
                        "profit": float(pos.get("upl", 0.0)),
                        "risk": risk
                    })
                    open_risk += risk
                    
                state["total_open_risk"] = open_risk
                
            state["status"] = "success"
            state["message"] = "Capital.com state fetched successfully"
            
        except Exception as e:
            state["message"] = f"Error fetching Capital state: {e}"

    return state
