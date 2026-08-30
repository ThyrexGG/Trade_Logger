import database
import market_data
import time

def evaluate_trade_risk(signal):
    """
    Evaluates risk for a proposed signal.
    Returns: {
        "approved": bool,
        "risk_score": float,
        "reasons": list,
        "warnings": list,
        "account_state": dict,
        "portfolio_state": dict,
        "trade_risk": dict
    }
    """
    symbol = str(signal.get("symbol", "")).upper()
    direction = str(signal.get("side", "")).upper()
    volume = float(signal.get("requested_quantity", 0.0))
    entry = float(signal.get("requested_entry", 0.0))
    sl = signal.get("stop_loss")
    
    sl = float(sl) if sl else None
    
    res = {
        "approved": False,
        "risk_score": 0.0,
        "reasons": [],
        "warnings": [],
        "account_state": {},
        "portfolio_state": {},
        "trade_risk": {}
    }

    # 1. Check Global Kill Switch
    kill_switch = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE")
    if kill_switch.upper() == "TRUE":
        res["reasons"].append("EMERGENCY HALT IS ACTIVE. Trade execution is globally blocked.")
        return res

    # 2. Basic Validation
    if not symbol or volume <= 0 or direction not in ["BUY", "SELL"]:
        res["reasons"].append("Invalid trade parameters (Symbol, Direction, or Volume).")
        return res

    # 3. Market Health Check
    health = market_data.get_market_health(symbol, "1m")
    if health["status"] in ["STALE", "DISCONNECTED"]:
        res["reasons"].append(f"Market data for {symbol} is {health['status']}. Price may be inaccurate.")
        return res

    # 4. Fetch Account State & Portfolio
    balances = database.get_account_balances()
    account = list(balances.values())[0] if balances else {"balance": 10000.0, "equity": 10000.0}
    res["account_state"] = account
    
    balance = account.get("balance", 10000.0)
    
    # Calculate SL logic
    if sl is not None and entry > 0:
        if direction == "BUY" and sl >= entry:
            res["reasons"].append("For BUY, Stop Loss must be below Entry.")
            return res
        if direction == "SELL" and sl <= entry:
            res["reasons"].append("For SELL, Stop Loss must be above Entry.")
            return res
            
        contract_size = 100000.0 if ("USD" in symbol or "EUR" in symbol) else 100.0
        dist = abs(entry - sl)
        trade_risk_usd = dist * volume * contract_size
        trade_risk_pct = (trade_risk_usd / balance) * 100.0
        
        res["trade_risk"] = {
            "risk_amount": trade_risk_usd,
            "risk_pct": trade_risk_pct
        }
        
        max_trade_risk_pct = float(database.get_setting("MAX_TRADE_RISK_PCT", "5.0"))
        if trade_risk_pct > max_trade_risk_pct:
            res["reasons"].append(f"Trade risk ({trade_risk_pct:.2f}%) exceeds maximum allowed ({max_trade_risk_pct:.2f}%).")
            return res

    # 5. Portfolio Risk Check
    open_positions = database.get_open_positions()
    total_open_risk = 0.0
    for _, pos in open_positions.iterrows():
        if pos['sl'] > 0 and pos['entry_price'] > 0:
            dist = abs(pos['entry_price'] - pos['sl'])
            c_size = 100000.0 if ("USD" in pos['symbol'] or "EUR" in pos['symbol']) else 100.0
            pos_risk = dist * pos['volume'] * c_size
            total_open_risk += pos_risk

    total_risk_pct = (total_open_risk / balance) * 100.0
    res["portfolio_state"] = {
        "open_positions_count": len(open_positions),
        "total_open_risk_pct": total_risk_pct
    }
    
    max_total_risk_pct = float(database.get_setting("MAX_TOTAL_RISK_PCT", "15.0"))
    trade_risk_pct = res["trade_risk"].get("risk_pct", 0.0)
    
    if (total_risk_pct + trade_risk_pct) > max_total_risk_pct:
        res["reasons"].append(f"Projected portfolio risk ({(total_risk_pct + trade_risk_pct):.2f}%) exceeds maximum total open risk ({max_total_risk_pct:.2f}%).")
        return res

    # 6. Daily Loss Check
    daily_realized = 0.0
    floating_pnl = open_positions['floating_pnl'].sum() if not open_positions.empty else 0.0
    total_daily_loss = daily_realized + floating_pnl
    
    max_daily_loss = float(database.get_setting("MAX_DAILY_LOSS", "-1000.0"))
    if total_daily_loss < max_daily_loss:
        res["reasons"].append(f"Daily loss protection breached: Current daily PnL ({total_daily_loss:.2f}) is below limit ({max_daily_loss:.2f}).")
        return res

    # If all checks pass
    res["approved"] = True
    return res
