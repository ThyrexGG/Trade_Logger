import os
import uuid
import time
from datetime import datetime, timezone
import database
import order_execution
import account_state
import portfolio_risk
import paper_simulator

CANONICAL_SYMBOL_MAP = {
    "EURUSD": {"mt5": "EURUSD", "capital": "EURUSD"},
    "GBPUSD": {"mt5": "GBPUSD", "capital": "GBPUSD"},
    "USDJPY": {"mt5": "USDJPY", "capital": "USDJPY"},
    "GBPJPY": {"mt5": "GBPJPY", "capital": "GBPJPY"},
    "XAUUSD": {"mt5": "XAUUSD", "capital": "GOLD"},
    "US500": {"mt5": "US500", "capital": "US500"},
    "NAS100": {"mt5": "USTEC", "capital": "US100"},
    "BTCUSD": {"mt5": "BTCUSD", "capital": "BTCUSD"},
}

MAX_DATA_AGE_SECONDS = 300  # 5 minutes stale limit

# In-memory cache for replay protection
_signal_cache = set()

def submit_order(
    signal_id: str,
    symbol: str,
    direction: str,
    volume: float,
    account_type: str = "MT5",
    stop_loss: float = None,
    take_profit: float = None,
    strategy: str = "Manual",
    timeframe: str = "Unknown",
    timestamp: float = None,
    current_price: float = None
):
    """
    Canonical Execution Pipeline.
    Every live/paper order MUST pass through this function.
    """
    # 1. Validation Setup
    signal_received_at = time.time()
    
    log_data = {
        "signal_id": signal_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "strategy": strategy,
        "timeframe": timeframe,
        "direction": direction,
        "entry_price": current_price,
        "sl": stop_loss,
        "tp": take_profit,
        "requested_risk": volume, # For logging
        "broker": account_type,
        "validation_result": "PENDING",
        "risk_result": "PENDING",
        "execution_result": "PENDING",
        "signal_received_at": signal_received_at,
        "validation_started_at": 0.0,
        "risk_completed_at": 0.0,
        "order_submitted_at": 0.0,
        "broker_response_at": 0.0,
        "journal_written_at": 0.0,
        "signal_to_execution_latency": 0.0
    }
    
    log_data["validation_started_at"] = time.time()
    
    # 1.1 Replay Protection & Idempotency
    try:
        if database.has_signal(log_data["signal_id"]):
            return _reject(log_data, "DUPLICATE SIGNAL: This signal ID was already processed.")
    except Exception as e:
        return _reject(log_data, f"DATABASE ERROR: Failed to check idempotency. Fail closed. {str(e)}")
    
    # 1.2 Staleness Check
    if timestamp:
        age = time.time() - float(timestamp)
        if age > MAX_DATA_AGE_SECONDS:
            return _reject(log_data, f"STALE DATA: Signal timestamp is {age:.1f} seconds old (Max {MAX_DATA_AGE_SECONDS}s).")
        if age < -5.0:
            return _reject(log_data, f"FUTURE TIMESTAMP: Signal is {abs(age):.1f}s in the future, outside 5s tolerance.")
            
    # 1.3 Symbol Validation
    if symbol not in CANONICAL_SYMBOL_MAP:
        return _reject(log_data, f"SYMBOL NOT WHITELISTED: {symbol} is not a verified safe symbol.")
        
    mapped_symbol = CANONICAL_SYMBOL_MAP[symbol]["capital" if account_type == "CAPITAL" else "mt5"]
    
    # 1.4 Global Kill Switch Check
    state = database.get_setting("SYSTEM_STATE", "PAPER")
    if state == "EMERGENCY HALT":
        return _reject(log_data, "EMERGENCY HALT: All new orders are globally disabled.")
    
    log_data["validation_result"] = "PASSED"
    
    # 2. Risk Engine Validation
    # Use order_execution helper to validate SL/TP mathematics
    risk_metrics = order_execution.calculate_order_risk(
        symbol=symbol,
        direction=direction,
        entry_price=current_price or 1.0, # Mock 1.0 if None just for basic SL/TP >/< validation
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=volume
    )
    
    if not risk_metrics["is_valid"]:
        return _reject(log_data, f"INVALID RISK PARAMS: {risk_metrics['error']}")
        
    # 2. Broker-Reconciled Risk Check
    acc_state = account_state.get_account_state(account_type)
    if acc_state["status"] == "success":
        # Check max open positions (limit = 5)
        if len(acc_state["open_positions"]) >= 5:
            return _reject(log_data, "MAX OPEN POSITIONS: You have reached the maximum allowed open positions (5) on the broker.")
            
        # Check daily loss (limit = -$500)
        effective_pnl = acc_state["realized_pnl"] + acc_state["floating_pnl"]
        if effective_pnl < -500.0:
            return _reject(log_data, f"MAX DAILY LOSS: Today's combined PnL is ${effective_pnl:.2f} (Realized: ${acc_state['realized_pnl']:.2f}, Floating: ${acc_state['floating_pnl']:.2f}), exceeding the -$500 limit.")
            
        # Check aggregate open risk limit (e.g. max 10% of equity)
        equity = acc_state["equity"]
        max_risk_allowed = equity * 0.10
        new_risk = risk_metrics.get("risk_amount", 0.0)
        if (acc_state["total_open_risk"] + new_risk) > max_risk_allowed:
            return _reject(log_data, f"AGGREGATE RISK LIMIT: Current open risk (${acc_state['total_open_risk']:.2f}) + new risk (${new_risk:.2f}) exceeds 10% of equity (${max_risk_allowed:.2f}).")
            
        # Check duplicate positions from broker state
        for pos in acc_state["open_positions"]:
            if pos["symbol"] == mapped_symbol:
                return _reject(log_data, "DUPLICATE POSITION: A position for this symbol is already open on the broker.")
                
    else:
        return _reject(log_data, f"BROKER STATE UNAVAILABLE: Failed to verify authoritative risk constraints. Fail closed. {acc_state['message']}")
        
    # 2.5 Portfolio Risk Check
    port_risk = portfolio_risk.get_portfolio_risk_status(account_type, symbol, direction, risk_metrics.get("risk_amount", 0.0))
    if not port_risk["is_valid"]:
        return _reject(log_data, port_risk["error"])

    log_data["actual_risk"] = risk_metrics["risk_pct"]
    log_data["calculated_size"] = volume
    log_data["final_size"] = volume # Broker step rounding would go here
    log_data["risk_result"] = "APPROVED"
    log_data["risk_completed_at"] = time.time()
        
    # 4. Broker Execution
    log_data["order_submitted_at"] = time.time()
    
    if state == "SHADOW":
        log_data["broker_response_at"] = time.time()
        log_data["execution_result"] = "WOULD_EXECUTE"
        log_data["broker_order_id"] = f"SHADOW_{uuid.uuid4().hex[:8]}"
        log_data["execution_price"] = current_price
        
        log_data["journal_written_at"] = time.time()
        log_data["signal_to_execution_latency"] = log_data["journal_written_at"] - log_data["signal_received_at"]
        database.log_execution(log_data)
        database.record_signal(log_data["signal_id"], "WOULD_EXECUTE", symbol, direction, account_type, log_data["broker_order_id"])
        return {"status": "success", "message": "Shadow order would be executed", "ticket": log_data["broker_order_id"]}
        
    if state == "PAPER":
        # Simulate realistic paper execution
        sim_res = paper_simulator.execute_paper_order(symbol, direction, volume, current_price, stop_loss, take_profit)
        
        log_data["broker_response_at"] = time.time()
        
        if sim_res.get("status") == "success":
            log_data["execution_result"] = "PAPER_FILLED"
            log_data["broker_order_id"] = sim_res.get("order_id")
            log_data["execution_price"] = sim_res.get("execution_price")
            
            log_data["journal_written_at"] = time.time()
            log_data["signal_to_execution_latency"] = log_data["journal_written_at"] - log_data["signal_received_at"]
            database.log_execution(log_data)
            database.record_signal(log_data["signal_id"], "PAPER_FILLED", symbol, direction, account_type, log_data["broker_order_id"])
            return sim_res
        else:
            return _reject(log_data, f"PAPER EXECUTION FAILED: {sim_res.get('message')}")
        
    # Live Execution
    if account_type == "CAPITAL":
        res = order_execution.execute_capital_trade(
            epic=mapped_symbol,
            direction=direction,
            size=volume,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    else:
        res = order_execution.execute_mt5_trade(
            symbol=mapped_symbol,
            direction=direction,
            volume=volume,
            sl=stop_loss,
            tp=take_profit
        )
        
    log_data["broker_response_at"] = time.time()
        
    if res["status"] == "success":
        log_data["execution_result"] = "FILLED"
        log_data["broker_order_id"] = res.get("order_id")
        log_data["execution_price"] = res.get("execution_price")
        
        log_data["journal_written_at"] = time.time()
        log_data["signal_to_execution_latency"] = log_data["journal_written_at"] - log_data["signal_received_at"]
        database.log_execution(log_data)
        database.record_signal(log_data["signal_id"], "FILLED", symbol, direction, account_type, log_data["broker_order_id"])
        return {"status": "success", "message": res["message"], "ticket": log_data["broker_order_id"]}
    else:
        # Check if it was a connection error / timeout which leaves order state unknown
        if "Connection error" in res["message"] or "timeout" in res["message"].lower():
            log_data["execution_result"] = "UNKNOWN"
            log_data["error_msg"] = res["message"]
            log_data["reject_reason"] = "BROKER TIMEOUT/UNKNOWN STATE"
            
            log_data["journal_written_at"] = time.time()
            log_data["signal_to_execution_latency"] = log_data["journal_written_at"] - log_data["signal_received_at"]
            database.log_execution(log_data)
            database.record_signal(log_data["signal_id"], "UNKNOWN", symbol, direction, account_type, None)
            return {"status": "error", "message": f"Broker state unknown. Order may have executed. DO NOT RETRY without verification. Detail: {res['message']}"}
        else:
            log_data["execution_result"] = "REJECTED"
            log_data["error_msg"] = res["message"]
            log_data["reject_reason"] = "BROKER REJECTION"
            
            log_data["journal_written_at"] = time.time()
            log_data["signal_to_execution_latency"] = log_data["journal_written_at"] - log_data["signal_received_at"]
            database.log_execution(log_data)
            database.record_signal(log_data["signal_id"], "REJECTED", symbol, direction, account_type, None)
            return {"status": "error", "message": res["message"]}

def _reject(log_data: dict, reason: str):
    log_data["execution_result"] = "REJECTED"
    log_data["reject_reason"] = reason
    
    # State handling for SHADOW mode rejection overrides
    state = database.get_setting("SYSTEM_STATE", "PAPER")
    if state == "SHADOW" and log_data["reject_reason"] != "DUPLICATE SIGNAL" and "EMERGENCY HALT" not in log_data["reject_reason"]:
        # In shadow mode, if it fails validation/risk, it's still WOULD_REJECT
        log_data["execution_result"] = "WOULD_REJECT"
        
    log_data["journal_written_at"] = time.time()
    log_data["signal_to_execution_latency"] = log_data["journal_written_at"] - log_data["signal_received_at"]
    database.log_execution(log_data)
    database.record_signal(log_data["signal_id"], log_data["execution_result"], log_data.get("symbol"), log_data.get("direction"), log_data.get("broker"))
    return {"status": "error", "message": reason}
