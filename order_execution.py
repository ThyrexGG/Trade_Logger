import os
import requests
import capital_sync
import mt5_sync

def execute_capital_trade(epic, direction, size, stop_loss=None, take_profit=None):
    """
    Places a live trade on Capital.com real account.
    direction: 'BUY' or 'SELL'
    size: float (lot size / units)
    """
    session = capital_sync.get_session()
    if not session:
        return False, "Failed to authenticate with Capital.com session."
        
    cst = session.get("cst")
    x_sec = session.get("x_security_token")
    api_key = capital_sync.CAPITAL_API_KEY
    
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
        
    url = f"{capital_sync.BASE_URL}/api/v1/positions"
    try:
        r = requests.post(url, headers=headers, json=body, timeout=12)
        res_data = r.json() if r.content else {}
        if r.status_code in [200, 201]:
            deal_ref = res_data.get("dealReference", "OK")
            return True, f"Order placed successfully! Deal Ref: {deal_ref}"
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
        "X-CAP-API-KEY": capital_sync.CAPITAL_API_KEY,
        "Content-Type": "application/json"
    }
    url = f"{capital_sync.BASE_URL}/api/v1/positions/{deal_id}"
    try:
        r = requests.delete(url, headers=headers, timeout=12)
        if r.status_code in [200, 204]:
            return True, "Position closed successfully on Capital.com."
        else:
            return False, f"Close position failed ({r.status_code}): {r.text}"
    except Exception as e:
        return False, f"Close error: {e}"

def execute_mt5_trade(symbol, direction, volume, stop_loss=None, take_profit=None):
    """Places a trade on MetaTrader 5 terminal if running on PC."""
    if not mt5_sync.MT5_AVAILABLE:
        return False, "MetaTrader 5 Python library is not available on this environment."
        
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return False, f"MT5 initialize failed: {mt5.last_error()}"
            
        sym = str(symbol).upper()
        symbol_info = mt5.symbol_info(sym)
        if symbol_info is None:
            return False, f"Symbol '{sym}' not found in MT5 Market Watch."
            
        if not symbol_info.visible:
            if not mt5.symbol_select(sym, True):
                return False, f"Failed to select symbol '{sym}'."
                
        order_type = mt5.ORDER_TYPE_BUY if str(direction).upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(sym).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(sym).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 100888,
            "comment": "TradeLogger Quick Order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if stop_loss is not None and float(stop_loss) > 0:
            request["sl"] = float(stop_loss)
        if take_profit is not None and float(take_profit) > 0:
            request["tp"] = float(take_profit)
            
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"MT5 order failed (retcode {result.retcode}): {result.comment}"
            
        return True, f"MT5 Trade executed! Order Ticket: #{result.order}"
    except Exception as e:
        return False, f"MT5 trade execution error: {e}"
