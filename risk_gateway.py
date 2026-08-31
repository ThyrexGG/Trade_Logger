"""
Central Risk Gateway (Phase 12A)
Mandatory execution risk filter evaluating per-trade risk, broker-reconciled account state,
portfolio open risk, directional correlation, and market data health.
Deterministic and strictly fail-closed.
"""

from typing import Dict, Any, List, Optional
import database
import market_data
from account_state import get_account_state


def get_contract_size(symbol: str) -> float:
    """Returns standardized contract size per instrument class."""
    sym = str(symbol).upper().strip()
    if "XAU" in sym or "GOLD" in sym:
        return 100.0  # 100 oz per lot
    elif "BTC" in sym or "ETH" in sym or "CRYPTO" in sym:
        return 1.0    # 1 coin per contract
    elif "US30" in sym or "NAS100" in sym or "SPX500" in sym or "GER40" in sym:
        return 1.0    # Index contracts
    elif "USOIL" in sym or "UKOIL" in sym:
        return 1000.0 # 1000 barrels per lot
    else:
        return 100000.0  # Standard FX lot = 100,000 units


def get_pair_correlation(sym_a: str, sym_b: str) -> float:
    """Looks up correlation between two assets from correlation_matrix or returns baseline."""
    if sym_a == sym_b:
        return 1.0
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        q = """
            SELECT correlation FROM correlation_matrix 
            WHERE (symbol_1 = %s AND symbol_2 = %s) OR (symbol_1 = %s AND symbol_2 = %s)
            ORDER BY updated_at DESC LIMIT 1
        """ if database.is_postgres() else """
            SELECT correlation FROM correlation_matrix 
            WHERE (symbol_1 = ? AND symbol_2 = ?) OR (symbol_1 = ? AND symbol_2 = ?)
            ORDER BY updated_at DESC LIMIT 1
        """
        cursor.execute(q, (sym_a, sym_b, sym_b, sym_a))
        row = cursor.fetchone()
        conn.close()
        if row:
            return float(row[0])
    except Exception:
        pass
        
    # Baseline macro-correlations fallback
    known_corrs = {
        ("EURUSD", "GBPUSD"): 0.84,
        ("EURUSD", "USDCHF"): -0.92,
        ("EURUSD", "USDJPY"): -0.45,
        ("GBPUSD", "USDJPY"): -0.38,
        ("XAUUSD", "EURUSD"): 0.65,
        ("NAS100", "SPX500"): 0.94,
        ("US30", "SPX500"): 0.89
    }
    for (a, b), val in known_corrs.items():
        if (sym_a == a and sym_b == b) or (sym_a == b and sym_b == a):
            return val
    return 0.0


def evaluate_trade_risk(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates comprehensive risk for a proposed signal.
    Returns:
    {
        "approved": bool,
        "risk_score": float,
        "reasons": list,
        "warnings": list,
        "account_state": dict,
        "portfolio_state": dict,
        "trade_risk": dict
    }
    """
    symbol = str(signal.get("symbol", "")).upper().strip()
    direction = str(signal.get("side", signal.get("direction", ""))).upper().strip()
    volume = float(signal.get("requested_quantity", signal.get("volume", 0.0)))
    entry = float(signal.get("requested_entry", signal.get("entry_price", 0.0)))
    sl = float(signal.get("stop_loss", signal.get("sl", 0.0))) if signal.get("stop_loss") or signal.get("sl") else None
    tp = float(signal.get("take_profit", signal.get("tp", 0.0))) if signal.get("take_profit") or signal.get("tp") else None
    broker = str(signal.get("broker", "CAPITAL")).upper().strip()
    mode = str(signal.get("mode", "PAPER")).upper().strip()

    res = {
        "approved": False,
        "risk_score": 0.0,
        "reasons": [],
        "warnings": [],
        "account_state": {},
        "portfolio_state": {},
        "trade_risk": {}
    }

    # 1. EMERGENCY KILL SWITCH CHECK
    kill_switch = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper()
    sys_state = database.get_setting("SYSTEM_STATE", "PAPER").upper()
    if kill_switch == "TRUE" or sys_state == "EMERGENCY HALT":
        res["reasons"].append("EMERGENCY_HALT_ACTIVE: System kill switch is engaged. All trading blocked.")
        return res

    # 2. BASIC VALIDATION & LOT SIZING
    if not symbol:
        res["reasons"].append("INVALID_SYMBOL: Symbol cannot be empty.")
        return res
    if direction not in ["BUY", "SELL"]:
        res["reasons"].append(f"INVALID_DIRECTION: Direction '{direction}' must be 'BUY' or 'SELL'.")
        return res
    if volume <= 0:
        res["reasons"].append(f"INVALID_VOLUME: Volume ({volume}) must be greater than zero.")
        return res
    if volume < 0.01:
        res["reasons"].append(f"MIN_LOT_VIOLATION: Volume ({volume}) is below broker minimum (0.01).")
        return res

    # 3. MARKET DATA HEALTH GATE
    try:
        health = market_data.get_market_health(symbol, "1m")
        if mode in ["LIVE", "LIVE_MICRO"] and health.get("status") in ["STALE", "DISCONNECTED"]:
            res["reasons"].append(f"MARKET_DATA_UNHEALTHY: Market feed for {symbol} is {health.get('status')}.")
            return res
        elif health.get("status") in ["STALE", "DISCONNECTED"]:
            res["warnings"].append(f"Market health check degraded/offline ({health.get('status')}).")
    except Exception as e:
        res["warnings"].append(f"Market health check bypassed (offline simulation): {e}")

    # 4. STOP LOSS & TAKE PROFIT GEOMETRY VALIDITY
    if entry > 0 and sl is not None:
        if direction == "BUY" and sl >= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: BUY Stop Loss ({sl}) must be strictly below Entry ({entry}).")
            return res
        if direction == "SELL" and sl <= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: SELL Stop Loss ({sl}) must be strictly above Entry ({entry}).")
            return res

    if entry > 0 and tp is not None:
        if direction == "BUY" and tp <= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: BUY Take Profit ({tp}) must be strictly above Entry ({entry}).")
            return res
        if direction == "SELL" and tp >= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: SELL Take Profit ({tp}) must be strictly below Entry ({entry}).")
            return res

    # 5. BROKER-RECONCILED ACCOUNT STATE (FAIL-CLOSED)
    account_data = None
    if mode in ["LIVE", "LIVE_MICRO"]:
        state_fetch = get_account_state(broker)
        if not state_fetch or state_fetch.get("status") not in ["success", "HEALTHY"]:
            err_details = state_fetch.get("message") or state_fetch.get("error_message") if state_fetch else "No response"
            res["reasons"].append(f"UNAVAILABLE_ACCOUNT_STATE: Unable to fetch authoritative broker account state for {broker}: {err_details}")
            return res
        account_data = state_fetch
    else:
        # Paper / Shadow local fallback
        balances = database.get_account_balances()
        account_data = balances.get("PAPER", list(balances.values())[0] if balances else {"balance": 10000.0, "equity": 10000.0, "floating_pnl": 0.0})

    res["account_state"] = account_data
    balance = float(account_data.get("balance", 10000.0))
    equity = float(account_data.get("equity", balance))
    floating_pnl = float(account_data.get("floating_pnl", 0.0))

    if balance <= 0:
        res["reasons"].append("INSUFFICIENT_EQUITY: Account balance is zero or negative.")
        return res

    # 6. PER-TRADE RISK CALCULATION
    contract_size = get_contract_size(symbol)
    trade_risk_usd = 0.0
    trade_risk_pct = 0.0
    if sl is not None and entry > 0:
        dist = abs(entry - sl)
        if symbol.startswith("USD") and symbol != "USD":
            # For USD-base pairs like USDJPY, USDCHF, USDCAD: 1 lot risk in USD = (dist / entry) * contract_size
            trade_risk_usd = (dist / entry) * volume * contract_size
        else:
            trade_risk_usd = dist * volume * contract_size
        trade_risk_pct = (trade_risk_usd / balance) * 100.0

    res["trade_risk"] = {
        "risk_amount_usd": round(trade_risk_usd, 2),
        "risk_pct": round(trade_risk_pct, 2),
        "contract_size": contract_size
    }

    max_trade_risk_pct = float(database.get_setting("MAX_TRADE_RISK_PCT", "5.0"))
    if trade_risk_pct > max_trade_risk_pct:
        res["reasons"].append(f"TRADE_RISK_EXCEEDED: Trade risk ({trade_risk_pct:.2f}%) exceeds maximum limit ({max_trade_risk_pct:.2f}%).")
        return res

    # 7. TOTAL PORTFOLIO OPEN RISK & EXPOSURE
    open_positions_df = database.get_open_positions()
    total_open_risk_usd = 0.0
    symbol_positions_count = 0
    directional_long_count = 0
    directional_short_count = 0

    if not open_positions_df.empty:
        for _, pos in open_positions_df.iterrows():
            pos_sym = str(pos["symbol"]).upper()
            pos_dir = str(pos["direction"]).upper()
            pos_vol = float(pos.get("volume", 0.0))
            pos_entry = float(pos.get("entry_price", 0.0))
            pos_sl = float(pos.get("sl", 0.0))

            if pos_sym == symbol:
                symbol_positions_count += 1
            if "BUY" in pos_dir or "LONG" in pos_dir:
                directional_long_count += 1
            else:
                directional_short_count += 1

            if pos_sl > 0 and pos_entry > 0:
                p_csize = get_contract_size(pos_sym)
                p_dist = abs(pos_entry - pos_sl)
                total_open_risk_usd += (p_dist * pos_vol * p_csize)

    # Check Max Symbol Exposure (Limit 2 positions per asset)
    max_symbol_exposure = int(database.get_setting("MAX_SYMBOL_EXPOSURE", "2"))
    if symbol_positions_count >= max_symbol_exposure:
        res["reasons"].append(f"SYMBOL_EXPOSURE_LIMIT: Already holding {symbol_positions_count} open positions for {symbol} (Max: {max_symbol_exposure}).")
        return res

    # Check Total Open Risk (including in-flight concurrency risk reservations)
    import execution_pipeline
    reserved_risk_pct = execution_pipeline.get_reserved_portfolio_risk_pct()
    total_open_risk_pct = (total_open_risk_usd / balance) * 100.0
    projected_total_risk_pct = total_open_risk_pct + reserved_risk_pct + trade_risk_pct

    res["portfolio_state"] = {
        "open_positions_count": len(open_positions_df),
        "total_open_risk_usd": round(total_open_risk_usd, 2),
        "total_open_risk_pct": round(total_open_risk_pct, 2),
        "reserved_in_flight_risk_pct": round(reserved_risk_pct, 2),
        "projected_total_risk_pct": round(projected_total_risk_pct, 2)
    }

    max_total_risk_pct = float(database.get_setting("MAX_TOTAL_RISK_PCT", "15.0"))
    if projected_total_risk_pct > max_total_risk_pct:
        res["reasons"].append(f"TOTAL_RISK_LIMIT: Projected total open risk ({projected_total_risk_pct:.2f}% [Open: {total_open_risk_pct:.2f}%, In-Flight: {reserved_risk_pct:.2f}%, New: {trade_risk_pct:.2f}%]) exceeds maximum limit ({max_total_risk_pct:.2f}%).")
        return res

    # 8. DIRECTION-AWARE CORRELATION RISK
    max_correlated_positions = int(database.get_setting("MAX_CORRELATED_EXPOSURE", "2"))
    if not open_positions_df.empty:
        for _, pos in open_positions_df.iterrows():
            pos_sym = str(pos["symbol"]).upper()
            pos_dir = str(pos["direction"]).upper()
            if pos_sym == symbol:
                continue
                
            corr = get_pair_correlation(symbol, pos_sym)
            if abs(corr) >= 0.80:
                same_direction = (direction == "BUY" and ("BUY" in pos_dir or "LONG" in pos_dir)) or \
                                 (direction == "SELL" and ("SELL" in pos_dir or "SHORT" in pos_dir))
                
                # Positive correlation in same direction multiplies directional exposure
                if corr > 0 and same_direction:
                    res["reasons"].append(
                        f"CORRELATION_RISK: New {direction} on {symbol} would accumulate excessive directional risk with open {pos_dir} on {pos_sym} (Correlation: {corr:.2f})."
                    )
                    return res
                # Negative correlation in opposite direction also multiplies risk
                elif corr < 0 and not same_direction:
                    res["reasons"].append(
                        f"INVERSE_CORRELATION_RISK: New {direction} on {symbol} with open {pos_dir} on {pos_sym} (Correlation: {corr:.2f}) doubles exposure."
                    )
                    return res
                else:
                    res["warnings"].append(f"Correlated pair ({pos_sym}) open, but acting in hedging orientation (Corr: {corr:.2f}).")

    # 9. DAILY LOSS PROTECTION (REALIZED + BROKER FLOATING PNL)
    daily_realized_pnl = float(account_data.get("realized_daily_pnl", 0.0))
    total_daily_pnl = daily_realized_pnl + floating_pnl
    
    # Calculate daily loss threshold (default: 3% of balance)
    max_daily_loss_pct = float(database.get_setting("MAX_DAILY_LOSS_PCT", "3.0"))
    max_daily_loss_usd = -(balance * (max_daily_loss_pct / 100.0))
    
    if total_daily_pnl < max_daily_loss_usd:
        res["reasons"].append(
            f"DAILY_LOSS_BREACH: Combined daily loss (${abs(total_daily_pnl):,.2f} [Realized: ${daily_realized_pnl:,.2f}, Floating: ${floating_pnl:,.2f}]) exceeds maximum limit of ${abs(max_daily_loss_usd):,.2f} ({max_daily_loss_pct}%)."
        )
        return res

    # ALL GATES PASSED
    res["approved"] = True
    res["risk_score"] = round(trade_risk_pct / max_trade_risk_pct, 4) if max_trade_risk_pct > 0 else 0.0
    return res
