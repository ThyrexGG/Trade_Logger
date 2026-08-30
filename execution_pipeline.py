import uuid
import time
from datetime import datetime, timezone
import database
import risk_gateway
import capital_sync
import mt5_sync

class ExecutionState:
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    MARKET_DATA_VALID = "MARKET_DATA_VALID"
    RISK_CHECKING = "RISK_CHECKING"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMITTING = "SUBMITTING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"
    RECONCILED = "RECONCILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED_SAFE = "FAILED_SAFE"

def persist_execution_state(state_data):
    """Saves the execution state to the execution_orders table."""
    conn = database.get_connection()
    cursor = conn.cursor()
    
    if database.is_postgres():
        query = """
            INSERT INTO execution_orders 
            (execution_id, signal_id, symbol, side, requested_quantity, requested_entry, stop_loss, take_profit, 
             broker, mode, state, broker_order_id, broker_position_id, created_at, submitted_at, resolved_at, last_error)
            VALUES 
            (%(execution_id)s, %(signal_id)s, %(symbol)s, %(side)s, %(requested_quantity)s, %(requested_entry)s, 
             %(stop_loss)s, %(take_profit)s, %(broker)s, %(mode)s, %(state)s, %(broker_order_id)s, 
             %(broker_position_id)s, %(created_at)s, %(submitted_at)s, %(resolved_at)s, %(last_error)s)
            ON CONFLICT (execution_id) DO UPDATE SET
                state = EXCLUDED.state,
                broker_order_id = EXCLUDED.broker_order_id,
                broker_position_id = EXCLUDED.broker_position_id,
                submitted_at = EXCLUDED.submitted_at,
                resolved_at = EXCLUDED.resolved_at,
                last_error = EXCLUDED.last_error
        """
        try:
            cursor.execute(query, state_data)
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e).lower() and "signal_id" in str(e).lower():
                raise ValueError("DUPLICATE_SIGNAL")
            print(f"Error persisting state to postgres: {e}")
    else:
        query = """
            INSERT INTO execution_orders 
            (execution_id, signal_id, symbol, side, requested_quantity, requested_entry, stop_loss, take_profit, 
             broker, mode, state, broker_order_id, broker_position_id, created_at, submitted_at, resolved_at, last_error)
            VALUES 
            (:execution_id, :signal_id, :symbol, :side, :requested_quantity, :requested_entry, :stop_loss, :take_profit, 
             :broker, :mode, :state, :broker_order_id, :broker_position_id, :created_at, :submitted_at, :resolved_at, :last_error)
            ON CONFLICT(execution_id) DO UPDATE SET
                state = excluded.state,
                broker_order_id = excluded.broker_order_id,
                broker_position_id = excluded.broker_position_id,
                submitted_at = excluded.submitted_at,
                resolved_at = excluded.resolved_at,
                last_error = excluded.last_error
        """
        try:
            cursor.execute(query, state_data)
        except Exception as e:
            if "UNIQUE constraint failed: execution_orders.signal_id" in str(e):
                raise ValueError("DUPLICATE_SIGNAL")
            print(f"Error persisting state to sqlite: {e}")
            
    conn.commit()
    conn.close()


def execute_signal(signal):
    """
    The canonical execution path.
    signal dictionary expected format:
    {
        "signal_id": str,
        "symbol": str,
        "side": "BUY" or "SELL",
        "requested_quantity": float,
        "requested_entry": float,
        "stop_loss": float,
        "take_profit": float,
        "broker": "CAPITAL" or "MT5",
        "mode": "LIVE", "PAPER", "SHADOW", "LIVE_MICRO"
    }
    """
    t0 = time.time()
    
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    state_data = {
        "execution_id": execution_id,
        "signal_id": signal.get("signal_id", f"sig_{uuid.uuid4().hex[:8]}"),
        "symbol": signal.get("symbol", ""),
        "side": signal.get("side", ""),
        "requested_quantity": float(signal.get("requested_quantity", 0.0)),
        "requested_entry": float(signal.get("requested_entry", 0.0)),
        "stop_loss": float(signal.get("stop_loss", 0.0)) if signal.get("stop_loss") else None,
        "take_profit": float(signal.get("take_profit", 0.0)) if signal.get("take_profit") else None,
        "broker": signal.get("broker", "CAPITAL"),
        "mode": signal.get("mode", "SHADOW"),
        "state": ExecutionState.RECEIVED,
        "broker_order_id": None,
        "broker_position_id": None,
        "created_at": now_iso,
        "submitted_at": None,
        "resolved_at": None,
        "last_error": None
    }
    
    try:
        persist_execution_state(state_data)
    except ValueError as e:
        if str(e) == "DUPLICATE_SIGNAL":
            return {"status": "error", "message": "Duplicate signal. Blocked by idempotency constraint."}
            
    # VALIDATING
    state_data["state"] = ExecutionState.VALIDATING
    persist_execution_state(state_data)
    
    # Check Kill Switch
    if database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper() == "TRUE":
        state_data["state"] = ExecutionState.REJECTED
        state_data["last_error"] = "EMERGENCY HALT ACTIVE"
        persist_execution_state(state_data)
        return {"status": "error", "message": state_data["last_error"]}

    # RISK_CHECKING
    state_data["state"] = ExecutionState.RISK_CHECKING
    persist_execution_state(state_data)
    
    risk_result = risk_gateway.evaluate_trade_risk(signal)
    
    if not risk_result["approved"]:
        state_data["state"] = ExecutionState.REJECTED
        state_data["last_error"] = " | ".join(risk_result["reasons"])
        persist_execution_state(state_data)
        return {"status": "rejected", "message": state_data["last_error"]}

    # RISK_APPROVED
    state_data["state"] = ExecutionState.RISK_APPROVED
    persist_execution_state(state_data)
    
    if state_data["mode"] in ["PAPER", "SHADOW"]:
        state_data["state"] = ExecutionState.FILLED
        state_data["broker_order_id"] = f"paper_{execution_id}"
        state_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
        persist_execution_state(state_data)
        return {"status": "success", "message": f"{state_data['mode']} execution simulated."}

    # SUBMITTING
    state_data["state"] = ExecutionState.SUBMITTING
    state_data["submitted_at"] = datetime.now(timezone.utc).isoformat()
    persist_execution_state(state_data)
    
    # We must treat broker responses critically.
    # If the broker adapter throws an exception during transmission, it becomes UNKNOWN.
    
    broker_result = None
    try:
        # Import dynamically to avoid circular dependencies if any
        import order_execution
        if state_data["broker"] == "MT5":
            broker_result = order_execution.execute_mt5_trade(
                symbol=state_data["symbol"], 
                direction=state_data["side"], 
                volume=state_data["requested_quantity"], 
                sl=state_data["stop_loss"], 
                tp=state_data["take_profit"]
            )
        else:
            broker_result = order_execution.execute_capital_trade(
                epic=state_data["symbol"], 
                direction=state_data["side"], 
                size=state_data["requested_quantity"], 
                stop_loss=state_data["stop_loss"], 
                take_profit=state_data["take_profit"]
            )
    except Exception as e:
        # A timeout or unhandled exception during submission MUST trigger UNKNOWN, not FAILED
        state_data["state"] = ExecutionState.UNKNOWN
        state_data["last_error"] = f"Connection/Timeout Error: {str(e)}"
        persist_execution_state(state_data)
        # We would immediately fire a background reconciliation task here.
        return {"status": "unknown", "message": "Broker response timed out. Order state is UNKNOWN. Freezing automation for this symbol."}
        
    if broker_result and broker_result.get("status") == "success":
        state_data["state"] = ExecutionState.FILLED
        state_data["broker_order_id"] = broker_result.get("order_id")
        state_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
        persist_execution_state(state_data)
        return {"status": "success", "message": "Order filled successfully", "order_id": state_data["broker_order_id"]}
    else:
        # Broker explicitly rejected it (we got a 4xx/5xx or MT5 retcode)
        state_data["state"] = ExecutionState.REJECTED
        state_data["last_error"] = broker_result.get("message", "Unknown broker error")
        persist_execution_state(state_data)
        return {"status": "error", "message": state_data["last_error"]}
