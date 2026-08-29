import os
import requests
import capital_sync
import mt5_sync

def calculate_order_risk(symbol, direction, entry_price, stop_loss=None, take_profit=None, volume=0.10, account_balance=10000.0):
    """
    Calculates deterministic risk management metrics before trade submission.
    Returns: {
        'is_valid': bool,
        'error': str or None,
        'stop_distance': float,
        'risk_amount': float,
        'risk_pct': float,
        'reward_amount': float,
        'reward_pct': float,
        'risk_reward_ratio': float,
        'recommended_lot': float
    }
    """
    sym = str(symbol).upper()
    dir_str = str(direction).upper()
    entry = float(entry_price) if entry_price else 0.0
    vol = float(volume) if volume else 0.01
    bal = float(account_balance) if account_balance and account_balance > 0 else 1000.0
    sl = float(stop_loss) if stop_loss and float(stop_loss) > 0 else None
    tp = float(take_profit) if take_profit and float(take_profit) > 0 else None

    # Contract Multiplier estimation (Forex: 100k, Gold: 100, Indices: 1, Crypto: 1)
    if "XAU" in sym or "GOLD" in sym:
        contract_size = 100.0
    elif "BTC" in sym or "ETH" in sym:
        contract_size = 1.0
    elif "NAS" in sym or "SPX" in sym or "US30" in sym or "GER" in sym or "100" in sym or "500" in sym:
        contract_size = 1.0
    else:
        # Standard Forex Pair
        contract_size = 100000.0 if ("USD" in sym or "EUR" in sym or "GBP" in sym or "JPY" in sym) else 100.0

    res = {
        "is_valid": True,
        "error": None,
        "stop_distance": 0.0,
        "risk_amount": 0.0,
        "risk_pct": 0.0,
        "reward_amount": 0.0,
        "reward_pct": 0.0,
        "risk_reward_ratio": 0.0,
        "recommended_lot": vol
    }

    if entry <= 0:
        return res

    # 1. SL Validation & Risk Calculation
    if sl is not None:
        if dir_str == "BUY" and sl >= entry:
            res["is_valid"] = False
            res["error"] = "For a BUY order, Stop Loss must be strictly below Entry Price."
            return res
        elif dir_str == "SELL" and sl <= entry:
            res["is_valid"] = False
            res["error"] = "For a SELL order, Stop Loss must be strictly above Entry Price."
            return res

        dist = abs(entry - sl)
        res["stop_distance"] = round(dist, 5)
        risk_usd = dist * vol * contract_size
        res["risk_amount"] = round(risk_usd, 2)
        res["risk_pct"] = round((risk_usd / bal) * 100.0, 2)

        # 1% Max Risk Recommended Lot Size
        max_1pct_risk = bal * 0.01
        if dist > 0:
            rec_lot = max_1pct_risk / (dist * contract_size)
            res["recommended_lot"] = max(0.01, round(rec_lot, 2))

    # 2. TP Validation & Reward Calculation
    if tp is not None:
        if dir_str == "BUY" and tp <= entry:
            res["is_valid"] = False
            res["error"] = "For a BUY order, Take Profit must be strictly above Entry Price."
            return res
        elif dir_str == "SELL" and tp >= entry:
            res["is_valid"] = False
            res["error"] = "For a SELL order, Take Profit must be strictly below Entry Price."
            return res

        reward_dist = abs(tp - entry)
        reward_usd = reward_dist * vol * contract_size
        res["reward_amount"] = round(reward_usd, 2)
        res["reward_pct"] = round((reward_usd / bal) * 100.0, 2)

        if res["risk_amount"] > 0:
            res["risk_reward_ratio"] = round(res["reward_amount"] / res["risk_amount"], 2)

    return res

def execute_capital_trade(epic, direction, size, stop_loss=None, take_profit=None):
    """Places a live trade on Capital.com real/demo account."""
    session = capital_sync.get_session()
    if not session:
        return False, "Failed to authenticate with Capital.com session."
        
    cst = session.get("cst")
    x_sec = session.get("x_security_token")
    api_key = session.get("api_key")
    base_url = session.get("base_url")
    
    headers = {
        "X-SECURITY-TOKEN": x_sec,
        "CST": cst,
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    body = {
        "epic": str(epic).upper(),
        "direction": str(direction).upper(),
        "size": float(size),
        "guaranteedStop": False
    }
    if stop_loss is not None and float(stop_loss) > 0:
        body["stopLevel"] = float(stop_loss)
    if take_profit is not None and float(take_profit) > 0:
        body["profitLevel"] = float(take_profit)
        
    url = f"{base_url}/positions"
    try:
        r = requests.post(url, headers=headers, json=body, timeout=12)
        res_data = r.json() if r.content else {}
        if r.status_code in [200, 201]:
            deal_ref = res_data.get("dealReference", "OK")
            return True, f"Capital.com Order Placed! Ref: {deal_ref}"
        else:
            err_msg = res_data.get("errorCode", r.text)
            return False, f"Capital.com Error ({r.status_code}): {err_msg}"
    except Exception as e:
        return False, f"Connection error: {e}"

def close_capital_position(deal_id):
    """Closes an open position on Capital.com."""
    session = capital_sync.get_session()
    if not session:
        return False, "Failed to authenticate with Capital.com session."
        
    headers = {
        "X-SECURITY-TOKEN": session.get("x_security_token"),
        "CST": session.get("cst"),
        "X-CAP-API-KEY": session.get("api_key"),
        "Content-Type": "application/json"
    }
    url = f"{session.get('base_url')}/positions/{deal_id}"
    try:
        r = requests.delete(url, headers=headers, timeout=12)
        if r.status_code in [200, 204]:
            return True, f"Capital.com Position #{deal_id} closed successfully."
        else:
            return False, f"Close failed ({r.status_code}): {r.text}"
    except Exception as e:
        return False, f"Close error: {e}"

def execute_mt5_trade(symbol, direction, volume, sl=None, tp=None):
    """Places a trade on MetaTrader 5 terminal running on local Windows PC."""
    if not mt5_sync.MT5_AVAILABLE:
        return False, "MetaTrader 5 library is not available on this environment."
        
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return False, f"MT5 initialize failed: {mt5.last_error()}"
            
        sym = str(symbol).upper()
        symbol_info = mt5.symbol_info(sym)
        if symbol_info is None:
            # Check common suffix aliases
            for alt in [f"{sym}.m", f"{sym}.raw", f"{sym}m", f"{sym}+"]:
                if mt5.symbol_info(alt) is not None:
                    sym = alt
                    symbol_info = mt5.symbol_info(sym)
                    break
                    
        if symbol_info is None:
            return False, f"Symbol '{sym}' not found in MT5 Market Watch."
            
        if not symbol_info.visible:
            if not mt5.symbol_select(sym, True):
                return False, f"Failed to select symbol '{sym}'."
                
        order_type = mt5.ORDER_TYPE_BUY if str(direction).upper() == "BUY" else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            return False, f"No live market tick received for {sym}."
            
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 100888,
            "comment": "TradeLogger Terminal Order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if sl is not None and float(sl) > 0:
            request["sl"] = float(sl)
        if tp is not None and float(tp) > 0:
            request["tp"] = float(tp)
            
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            comment = result.comment if result else mt5.last_error()
            return False, f"MT5 Order Rejected: {comment}"
            
        return True, f"MT5 Order Executed! Ticket #{result.order}"
    except Exception as e:
        return False, f"MT5 trade execution error: {e}"

def close_mt5_position(ticket_id):
    """Closes an open MT5 position by ticket ID."""
    if not mt5_sync.MT5_AVAILABLE:
        return False, "MT5 is only available on Windows."
        
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return False, f"MT5 initialize failed: {mt5.last_error()}"
            
        ticket = int(ticket_id)
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return False, f"Position #{ticket} not found in MT5."
            
        pos = positions[0]
        sym = pos.symbol
        vol = pos.volume
        pos_type = pos.type # 0 = BUY, 1 = SELL
        
        # Opposite order type to close
        close_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            return False, f"Could not get tick for {sym}."
            
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": sym,
            "volume": vol,
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": 100888,
            "comment": f"Close #{ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            comment = result.comment if result else mt5.last_error()
            return False, f"Close MT5 position failed: {comment}"
            
        return True, f"MT5 Position #{ticket} closed successfully."
    except Exception as e:
        return False, f"MT5 close error: {e}"
