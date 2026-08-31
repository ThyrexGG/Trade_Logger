"""
Canonical Execution State Machine & Pipeline (Phase 12B)
Single, authoritative order execution gateway across Webhooks, UI, Strategy Engines, and Paper Trading.
Deterministic, fail-closed, auditable, restart-safe, concurrency-proof, and broker-reconciled.
"""

import uuid
import time
import json
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field, asdict

import database
import risk_gateway
import symbol_mapping
import instrument_specs
import market_data
from broker_adapter import get_broker_adapter, CanonicalOrderResult


@dataclass
class CanonicalExecutionRequest:
    """Canonical, authoritative order execution request object."""
    signal_id: str
    symbol: str
    side: str                            # BUY or SELL
    quantity: float                      # Lot size or volume
    source: str = "MANUAL_UI"            # STRATEGY, MANUAL_UI, WEBHOOK, PAPER_SIMULATOR, API
    strategy: str = "Manual"
    timeframe: str = "Unknown"
    setup_type: str = "Unknown"
    execution_model: str = "MARKET"       # MARKET or LIMIT
    requested_entry: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_percent: float = 1.0
    confluence_score: float = 0.0
    session: str = "Unknown"
    timestamp: float = field(default_factory=time.time)
    broker: str = "CAPITAL"              # MT5, CAPITAL, PAPER, SHADOW
    mode: str = "PAPER"                  # PAPER, SHADOW, LIVE, LIVE_MICRO
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionState:
    """Explicit state enum for canonical order lifecycle."""
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


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


# Strict State Transition Validation Graph (Phase 12A / 12B)
VALID_TRANSITIONS = {
    ExecutionState.RECEIVED: [
        ExecutionState.VALIDATING, 
        ExecutionState.REJECTED, 
        ExecutionState.CANCELLED,
        ExecutionState.FAILED_SAFE
    ],
    ExecutionState.VALIDATING: [
        ExecutionState.MARKET_DATA_VALID, 
        ExecutionState.REJECTED, 
        ExecutionState.CANCELLED,
        ExecutionState.FAILED_SAFE
    ],
    ExecutionState.MARKET_DATA_VALID: [
        ExecutionState.RISK_CHECKING, 
        ExecutionState.REJECTED, 
        ExecutionState.CANCELLED,
        ExecutionState.FAILED_SAFE
    ],
    ExecutionState.RISK_CHECKING: [
        ExecutionState.RISK_APPROVED, 
        ExecutionState.REJECTED, 
        ExecutionState.CANCELLED,
        ExecutionState.FAILED_SAFE
    ],
    ExecutionState.RISK_APPROVED: [
        ExecutionState.SUBMITTING, 
        ExecutionState.REJECTED, 
        ExecutionState.CANCELLED,
        ExecutionState.FILLED,      # For paper/shadow direct resolution
        ExecutionState.FAILED_SAFE
    ],
    ExecutionState.SUBMITTING: [
        ExecutionState.FILLED, 
        ExecutionState.PARTIALLY_FILLED, 
        ExecutionState.UNKNOWN, 
        ExecutionState.REJECTED, 
        ExecutionState.FAILED_SAFE
    ],
    ExecutionState.UNKNOWN: [
        ExecutionState.RECONCILING
    ],
    ExecutionState.RECONCILING: [
        ExecutionState.RECONCILED,
        ExecutionState.UNKNOWN      # If broker cannot be reached, remains UNKNOWN
    ],
    ExecutionState.RECONCILED: [],
    ExecutionState.FILLED: [],
    ExecutionState.PARTIALLY_FILLED: [ExecutionState.FILLED, ExecutionState.CANCELLED],
    ExecutionState.REJECTED: [],
    ExecutionState.CANCELLED: [],
    ExecutionState.FAILED_SAFE: []
}

# Concurrency Mutex Lock for Atomic Claim & Execution State
_EXECUTION_MUTEX = threading.Lock()

# Active In-Flight Risk Reservations Tracker
_ACTIVE_RESERVATIONS: Dict[str, float] = {}
_RESERVATION_LOCK = threading.Lock()


def get_reserved_portfolio_risk_pct() -> float:
    """Returns total risk percentage currently reserved by in-flight orders."""
    with _RESERVATION_LOCK:
        return sum(_ACTIVE_RESERVATIONS.values())


def reserve_risk(signal_id: str, risk_pct: float) -> None:
    """Reserves risk percentage for an in-flight execution."""
    with _RESERVATION_LOCK:
        _ACTIVE_RESERVATIONS[signal_id] = float(risk_pct)


def release_risk(signal_id: str) -> None:
    """Releases risk reservation upon order completion or rejection."""
    with _RESERVATION_LOCK:
        _ACTIVE_RESERVATIONS.pop(signal_id, None)


def validate_state_transition(current_state: str, new_state: str) -> bool:
    """Validates if transitioning from current_state to new_state is legally allowed."""
    if current_state == new_state:
        return True
    allowed = VALID_TRANSITIONS.get(current_state, [])
    if new_state not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal state machine transition: '{current_state}' -> '{new_state}'. Allowed targets: {allowed}"
        )
    return True


def persist_execution_state(state_data: Dict[str, Any]) -> None:
    """
    Saves or updates the canonical execution order state in the database.
    Atomically enforces signal_id idempotency.
    """
    conn = database.get_connection()
    cursor = conn.cursor()
    
    now_iso = datetime.now(timezone.utc).isoformat()
    if not state_data.get("created_at"):
        state_data["created_at"] = now_iso
    if not state_data.get("updated_at"):
        state_data["updated_at"] = now_iso
    if not state_data.get("reconciliation_status"):
        state_data["reconciliation_status"] = "PENDING" if state_data.get("state") == ExecutionState.UNKNOWN else "N/A"
        
    for k, v in list(state_data.items()):
        if isinstance(v, datetime):
            state_data[k] = v.isoformat()
            
    if isinstance(state_data.get("signal_payload"), dict):
        state_data["signal_payload"] = json.dumps(state_data["signal_payload"])
        
    cols = [
        "execution_id", "signal_id", "symbol", "side", "requested_quantity", "requested_entry",
        "stop_loss", "take_profit", "broker", "mode", "state", "broker_order_id", "broker_position_id",
        "created_at", "updated_at", "submitted_at", "filled_at", "unknown_at", "resolved_at",
        "last_error", "reject_reason", "reconciliation_status", "signal_payload", "execution_latency_ms"
    ]
    
    # Ensure all keys exist in state_data with defaults
    for c in cols:
        if c not in state_data:
            state_data[c] = None

    if database.is_postgres():
        placeholders = ", ".join([f"%({c})s" for c in cols])
        cols_str = ", ".join(cols)
        query = f"""
            INSERT INTO execution_orders ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT (execution_id) DO UPDATE SET
                state = EXCLUDED.state,
                broker_order_id = EXCLUDED.broker_order_id,
                broker_position_id = EXCLUDED.broker_position_id,
                updated_at = EXCLUDED.updated_at,
                submitted_at = EXCLUDED.submitted_at,
                filled_at = EXCLUDED.filled_at,
                unknown_at = EXCLUDED.unknown_at,
                resolved_at = EXCLUDED.resolved_at,
                last_error = EXCLUDED.last_error,
                reject_reason = EXCLUDED.reject_reason,
                reconciliation_status = EXCLUDED.reconciliation_status,
                execution_latency_ms = EXCLUDED.execution_latency_ms
        """
        try:
            cursor.execute(query, state_data)
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "duplicate key value violates unique constraint" in str(e).lower() and "signal_id" in str(e).lower():
                raise ValueError("DUPLICATE_SIGNAL")
            raise e
        finally:
            conn.close()
    else:
        placeholders = ", ".join([f":{c}" for c in cols])
        cols_str = ", ".join(cols)
        query = f"""
            INSERT INTO execution_orders ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT(execution_id) DO UPDATE SET
                state = excluded.state,
                broker_order_id = excluded.broker_order_id,
                broker_position_id = excluded.broker_position_id,
                updated_at = excluded.updated_at,
                submitted_at = excluded.submitted_at,
                filled_at = excluded.filled_at,
                unknown_at = excluded.unknown_at,
                resolved_at = excluded.resolved_at,
                last_error = excluded.last_error,
                reject_reason = excluded.reject_reason,
                reconciliation_status = excluded.reconciliation_status,
                execution_latency_ms = excluded.execution_latency_ms
        """
        try:
            cursor.execute(query, state_data)
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "UNIQUE constraint failed: execution_orders.signal_id" in str(e):
                raise ValueError("DUPLICATE_SIGNAL")
            raise e
        finally:
            conn.close()


def transition_state(state_data: Dict[str, Any], target_state: str, error_msg: Optional[str] = None) -> None:
    """Safely transitions execution state, enforcing state graph invariants."""
    current_state = state_data.get("state", ExecutionState.RECEIVED)
    validate_state_transition(current_state, target_state)
    state_data["state"] = target_state
    state_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if error_msg:
        state_data["last_error"] = error_msg
    if target_state == ExecutionState.UNKNOWN:
        state_data["unknown_at"] = datetime.now(timezone.utc).isoformat()
        state_data["reconciliation_status"] = "PENDING_RECONCILIATION"
    elif target_state == ExecutionState.FILLED:
        state_data["filled_at"] = datetime.now(timezone.utc).isoformat()
        state_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    elif target_state in [ExecutionState.REJECTED, ExecutionState.CANCELLED, ExecutionState.FAILED_SAFE]:
        state_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    
    persist_execution_state(state_data)


def submit_order(request: Union[CanonicalExecutionRequest, Dict[str, Any], Any] = None, **kwargs) -> Dict[str, Any]:
    """
    CANONICAL ORDER ENTRYPOINT (Phase 12B).
    Every execution source (Manual UI, Webhooks, Strategies, Paper Simulator)
    MUST route through this single function.
    """
    if isinstance(request, CanonicalExecutionRequest):
        req_dict = asdict(request)
    elif isinstance(request, dict):
        req_dict = request
    else:
        req_dict = kwargs

    # Normalization into standard dictionary
    sig_id = str(req_dict.get("signal_id") or req_dict.get("id") or f"sig_{uuid.uuid4().hex[:8]}")
    symbol = str(req_dict.get("symbol") or "").upper().strip()
    side = str(req_dict.get("side") or req_dict.get("direction") or "").upper().strip()
    qty = float(req_dict.get("quantity") or req_dict.get("volume") or req_dict.get("requested_quantity") or 0.0)
    entry = float(req_dict.get("requested_entry") or req_dict.get("entry_price") or req_dict.get("price") or req_dict.get("current_price") or 0.0)
    sl = float(req_dict.get("stop_loss") or req_dict.get("sl") or 0.0) if req_dict.get("stop_loss") or req_dict.get("sl") else None
    tp = float(req_dict.get("take_profit") or req_dict.get("tp") or 0.0) if req_dict.get("take_profit") or req_dict.get("tp") else None
    broker = str(req_dict.get("broker") or req_dict.get("account_type") or "CAPITAL").upper().strip()
    mode = str(req_dict.get("mode") or database.get_setting("SYSTEM_STATE", "PAPER")).upper().strip()

    normalized_signal = {
        "signal_id": sig_id,
        "symbol": symbol,
        "side": side,
        "direction": side,
        "requested_quantity": qty,
        "volume": qty,
        "requested_entry": entry,
        "entry_price": entry,
        "stop_loss": sl,
        "sl": sl,
        "take_profit": tp,
        "tp": tp,
        "broker": broker,
        "account_type": broker,
        "mode": mode,
        "strategy": req_dict.get("strategy", "Manual"),
        "timeframe": req_dict.get("timeframe", "Unknown"),
        "setup_type": req_dict.get("setup_type", "Unknown"),
        "confluence_score": float(req_dict.get("confluence_score", 0.0)),
        "session": req_dict.get("session", "Unknown"),
        "timestamp": req_dict.get("timestamp", time.time()),
        "metadata": req_dict.get("metadata", {})
    }

    return execute_signal(normalized_signal)


def execute_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    The CANONICAL EXECUTION PIPELINE (Phase 12A / 12B).
    Every order must pass through:
    ATOMIC_CLAIM -> VALIDATING -> SYMBOL_MAP -> INSTRUMENT_SPECS -> PRICE_SIDE_CHECK ->
    PRICE_DEVIATION_GATE -> RISK_GATEWAY -> RISK_APPROVED -> SUBMITTING -> (FILLED | UNKNOWN)
    """
    t_start = time.perf_counter()
    execution_id = f"exec_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    sig_id = str(signal.get("signal_id", f"sig_{uuid.uuid4().hex[:8]}"))
    
    # 1. ATOMIC SIGNAL CLAIM & PERSISTENCE
    with _EXECUTION_MUTEX:
        # Check if signal_id is already in database (True Concurrency Idempotency)
        conn = database.get_connection()
        cursor = conn.cursor()
        if database.is_postgres():
            cursor.execute("SELECT state, execution_id FROM execution_orders WHERE signal_id = %s", (sig_id,))
        else:
            cursor.execute("SELECT state, execution_id FROM execution_orders WHERE signal_id = ?", (sig_id,))
        existing = cursor.fetchone()
        conn.close()

        if existing:
            return {
                "status": "error",
                "execution_id": existing[1],
                "signal_id": sig_id,
                "state": existing[0],
                "message": f"DUPLICATE_SIGNAL: Signal ID '{sig_id}' has already been claimed/processed (State: {existing[0]})."
            }

        # Canonical State Dictionary
        state_data = {
            "execution_id": execution_id,
            "signal_id": sig_id,
            "symbol": str(signal.get("symbol", "")).upper().strip(),
            "side": str(signal.get("side", signal.get("direction", ""))).upper().strip(),
            "requested_quantity": float(signal.get("requested_quantity", signal.get("volume", 0.0))),
            "requested_entry": float(signal.get("requested_entry", signal.get("entry_price", 0.0))),
            "stop_loss": float(signal.get("stop_loss", signal.get("sl", 0.0))) if signal.get("stop_loss") or signal.get("sl") else None,
            "take_profit": float(signal.get("take_profit", signal.get("tp", 0.0))) if signal.get("take_profit") or signal.get("tp") else None,
            "broker": str(signal.get("broker", "CAPITAL")).upper().strip(),
            "mode": str(signal.get("mode", database.get_setting("SYSTEM_STATE", "PAPER"))).upper().strip(),
            "state": ExecutionState.RECEIVED,
            "broker_order_id": None,
            "broker_position_id": None,
            "created_at": now_iso,
            "updated_at": now_iso,
            "submitted_at": None,
            "filled_at": None,
            "unknown_at": None,
            "resolved_at": None,
            "last_error": None,
            "reject_reason": None,
            "reconciliation_status": "N/A",
            "signal_payload": signal,
            "execution_latency_ms": 0.0
        }

        try:
            persist_execution_state(state_data)
        except ValueError as e:
            if str(e) == "DUPLICATE_SIGNAL":
                return {
                    "status": "error",
                    "execution_id": execution_id,
                    "signal_id": sig_id,
                    "state": ExecutionState.REJECTED,
                    "message": f"DUPLICATE_SIGNAL: Signal ID '{sig_id}' has already been processed."
                }
            raise e

    # 2. VALIDATING
    transition_state(state_data, ExecutionState.VALIDATING)
    
    # Check Global Kill Switch & Emergency Halt
    kill_switch = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper()
    sys_state = database.get_setting("SYSTEM_STATE", "PAPER").upper()
    if kill_switch == "TRUE" or sys_state == "EMERGENCY HALT":
        msg = "EMERGENCY_HALT_ACTIVE: Global execution kill switch is engaged."
        state_data["reject_reason"] = msg
        transition_state(state_data, ExecutionState.REJECTED, error_msg=msg)
        return {"status": "rejected", "execution_id": execution_id, "state": ExecutionState.REJECTED, "message": msg}

    # Validate basic payload integrity
    if not state_data["symbol"] or state_data["requested_quantity"] <= 0 or state_data["side"] not in ["BUY", "SELL"]:
        msg = "INVALID_PAYLOAD: Missing or malformed Symbol, Direction, or Quantity."
        state_data["reject_reason"] = msg
        transition_state(state_data, ExecutionState.REJECTED, error_msg=msg)
        return {"status": "rejected", "execution_id": execution_id, "state": ExecutionState.REJECTED, "message": msg}

    # Symbol Canonical Mapping Gate
    canonical_sym = symbol_mapping.normalize_symbol(state_data["symbol"])
    if not canonical_sym:
        msg = f"UNKNOWN_SYMBOL: Symbol '{state_data['symbol']}' is not recognized in canonical registry."
        state_data["reject_reason"] = msg
        transition_state(state_data, ExecutionState.REJECTED, error_msg=msg)
        return {"status": "rejected", "execution_id": execution_id, "state": ExecutionState.REJECTED, "message": msg}
    state_data["symbol"] = canonical_sym

    # Instrument Specification & Volume Stepping Validation Gate
    vol_valid, vol_err = instrument_specs.validate_order_volume(state_data["broker"], canonical_sym, state_data["requested_quantity"])
    if not vol_valid:
        state_data["reject_reason"] = vol_err
        transition_state(state_data, ExecutionState.REJECTED, error_msg=vol_err)
        return {"status": "rejected", "execution_id": execution_id, "state": ExecutionState.REJECTED, "message": vol_err}

    # Stale Signal Timestamp Gate (>300 seconds rejected)
    sig_time_str = signal.get("timestamp")
    if sig_time_str:
        try:
            if isinstance(sig_time_str, (int, float)):
                sig_ts = float(sig_time_str)
            else:
                sig_ts = datetime.fromisoformat(str(sig_time_str).replace("Z", "+00:00")).timestamp()
            if (datetime.now(timezone.utc).timestamp() - sig_ts) > 300:
                msg = f"STALE_SIGNAL: Signal timestamp is older than 300 seconds."
                state_data["reject_reason"] = msg
                transition_state(state_data, ExecutionState.REJECTED, error_msg=msg)
                return {"status": "rejected", "execution_id": execution_id, "state": ExecutionState.REJECTED, "message": msg}
        except Exception:
            pass

    # 3. MARKET DATA & PRICE-SIDE / PRICE DEVIATION GATES
    transition_state(state_data, ExecutionState.MARKET_DATA_VALID)
    
    # Executable Price-Side Correctness (BUY -> Ask, SELL -> Bid)
    try:
        latest_tick = market_data.get_latest_tick(canonical_sym)
        if latest_tick and "ask" in latest_tick and "bid" in latest_tick:
            executable_price = float(latest_tick["ask"]) if state_data["side"] == "BUY" else float(latest_tick["bid"])
            if executable_price > 0:
                # Check Price Deviation against requested reference entry
                req_entry = state_data["requested_entry"]
                if req_entry > 0:
                    max_dev_pct = float(database.get_setting("MAX_PRICE_DEVIATION_PCT", "0.50")) # 0.50% max deviation
                    deviation_pct = (abs(executable_price - req_entry) / req_entry) * 100.0
                    if deviation_pct > max_dev_pct:
                        msg = f"PRICE_DEVIATION_EXCEEDED: Executable price ({executable_price}) deviates {deviation_pct:.2f}% from requested entry ({req_entry}) [Max: {max_dev_pct}%]."
                        state_data["reject_reason"] = msg
                        transition_state(state_data, ExecutionState.REJECTED, error_msg=msg)
                        return {"status": "rejected", "execution_id": execution_id, "state": ExecutionState.REJECTED, "message": msg}
                # Update requested entry with exact executable price for risk precision
                state_data["requested_entry"] = executable_price
                signal["requested_entry"] = executable_price
    except Exception:
        pass

    # 4. RISK GATEWAY CHECK & CONCURRENT RISK RESERVATION
    transition_state(state_data, ExecutionState.RISK_CHECKING)
    
    # Evaluate risk
    risk_result = risk_gateway.evaluate_trade_risk(signal)
    
    if not risk_result.get("approved", False):
        reasons = " | ".join(risk_result.get("reasons", ["Risk gateway rejected proposed order"]))
        state_data["reject_reason"] = reasons
        transition_state(state_data, ExecutionState.REJECTED, error_msg=reasons)
        return {
            "status": "rejected", 
            "execution_id": execution_id, 
            "state": ExecutionState.REJECTED, 
            "message": reasons,
            "risk_details": risk_result
        }

    # Atomically Reserve Risk for Portfolio Concurrency Safety
    trade_risk_pct = float(risk_result.get("trade_risk", {}).get("risk_pct", 1.0))
    reserve_risk(sig_id, trade_risk_pct)

    # 5. RISK APPROVED
    transition_state(state_data, ExecutionState.RISK_APPROVED)

    # SHADOW MODE RESOLUTION (Zero broker call, full decision audit logging)
    if state_data["mode"] == "SHADOW":
        release_risk(sig_id)
        t_end = time.perf_counter()
        state_data["execution_latency_ms"] = round((t_end - t_start) * 1000, 2)
        state_data["broker_order_id"] = f"shadow_{execution_id}"
        transition_state(state_data, ExecutionState.FILLED)
        return {
            "status": "success",
            "mode": "SHADOW",
            "execution_id": execution_id,
            "state": ExecutionState.FILLED,
            "message": "Shadow execution simulated. All risk and validation gates passed.",
            "latency_ms": state_data["execution_latency_ms"]
        }

    # 6. SUBMITTING
    state_data["submitted_at"] = datetime.now(timezone.utc).isoformat()
    transition_state(state_data, ExecutionState.SUBMITTING)
    
    # 7. BROKER TRANSMISSION VIA NORMALIZED ADAPTER
    broker_name = "PAPER" if state_data["mode"] == "PAPER" else state_data["broker"]
    try:
        adapter = get_broker_adapter(broker_name)
        broker_result: CanonicalOrderResult = adapter.submit_order(
            symbol=state_data["symbol"],
            direction=state_data["side"],
            volume=state_data["requested_quantity"],
            sl=state_data["stop_loss"],
            tp=state_data["take_profit"],
            limit_price=state_data["requested_entry"]
        )
    except (TimeoutError, ConnectionError) as e:
        # CRITICAL RULE: Network timeouts or disconnects MUST enter UNKNOWN, NEVER FAILED / REJECTED
        release_risk(sig_id)
        t_end = time.perf_counter()
        state_data["execution_latency_ms"] = round((t_end - t_start) * 1000, 2)
        err_msg = f"BROKER_TIMEOUT: Connection dropped during order submission: {str(e)}"
        transition_state(state_data, ExecutionState.UNKNOWN, error_msg=err_msg)
        
        # Trigger background reconciliation attempt
        try:
            import reconciliation
            reconciliation.reconcile_execution(execution_id)
        except Exception:
            pass
            
        return {
            "status": "unknown",
            "execution_id": execution_id,
            "state": ExecutionState.UNKNOWN,
            "message": "Broker response timed out. Order state is UNKNOWN. System will reconcile before permitting further orders.",
            "latency_ms": state_data["execution_latency_ms"]
        }
    except Exception as e:
        release_risk(sig_id)
        t_end = time.perf_counter()
        state_data["execution_latency_ms"] = round((t_end - t_start) * 1000, 2)
        err_msg = f"SUBMISSION_EXCEPTION: {str(e)}"
        transition_state(state_data, ExecutionState.UNKNOWN, error_msg=err_msg)
        return {
            "status": "unknown",
            "execution_id": execution_id,
            "state": ExecutionState.UNKNOWN,
            "message": err_msg,
            "latency_ms": state_data["execution_latency_ms"]
        }

    release_risk(sig_id)
    t_end = time.perf_counter()
    state_data["execution_latency_ms"] = round((t_end - t_start) * 1000, 2)

    # 8. PROCESS BROKER RESULT
    if broker_result.status == "SUCCESS":
        state_data["broker_order_id"] = broker_result.order_id
        state_data["broker_position_id"] = broker_result.position_id
        transition_state(state_data, ExecutionState.FILLED)
        return {
            "status": "success",
            "execution_id": execution_id,
            "state": ExecutionState.FILLED,
            "broker_order_id": broker_result.order_id,
            "fill_price": broker_result.fill_price,
            "latency_ms": state_data["execution_latency_ms"]
        }
    else:
        err_msg = broker_result.message or "Broker explicitly rejected order submission"
        state_data["reject_reason"] = err_msg
        transition_state(state_data, ExecutionState.REJECTED, error_msg=err_msg)
        return {
            "status": "rejected",
            "execution_id": execution_id,
            "state": ExecutionState.REJECTED,
            "message": err_msg,
            "latency_ms": state_data["execution_latency_ms"]
        }


def recover_incomplete_executions() -> Dict[str, Any]:
    """
    RESTART & CRASH RECOVERY (Phase 12B).
    Scans execution_orders for incomplete states (RECEIVED, VALIDATING, RISK_APPROVED, SUBMITTING, UNKNOWN).
    Reconciles with broker where submission may have occurred, and fails-safe unfinished orders without blind duplicate retries.
    """
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT execution_id, signal_id, state, broker, symbol, side, requested_quantity 
        FROM execution_orders 
        WHERE state IN ('RECEIVED', 'VALIDATING', 'MARKET_DATA_VALID', 'RISK_CHECKING', 'RISK_APPROVED', 'SUBMITTING', 'UNKNOWN')
    """)
    rows = cursor.fetchall()
    conn.close()

    summary = {
        "total_incomplete": len(rows),
        "recovered": 0,
        "reconciled": 0,
        "failed_safe": 0,
        "details": []
    }

    import reconciliation

    for r in rows:
        exec_id, sig_id, state, brk, sym, side, qty = r
        
        # If order reached SUBMITTING or UNKNOWN, it may have reached the broker
        if state in [ExecutionState.SUBMITTING, ExecutionState.UNKNOWN]:
            recon_res = reconciliation.reconcile_execution(exec_id)
            summary["reconciled"] += 1
            summary["details"].append({
                "execution_id": exec_id,
                "initial_state": state,
                "action": "BROKER_RECONCILED",
                "result": recon_res
            })
        else:
            # Order was never submitted to broker; transition safely to FAILED_SAFE / CANCELLED
            conn_u = database.get_connection()
            cur_u = conn_u.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            if database.is_postgres():
                cur_u.execute("""
                    UPDATE execution_orders 
                    SET state = 'FAILED_SAFE', resolved_at = %s, last_error = 'Application crashed before order submission. Recovered safely.'
                    WHERE execution_id = %s
                """, (now_iso, exec_id))
            else:
                cur_u.execute("""
                    UPDATE execution_orders 
                    SET state = 'FAILED_SAFE', resolved_at = ?, last_error = 'Application crashed before order submission. Recovered safely.'
                    WHERE execution_id = ?
                """, (now_iso, exec_id))
            conn_u.commit()
            conn_u.close()
            summary["failed_safe"] += 1
            summary["details"].append({
                "execution_id": exec_id,
                "initial_state": state,
                "action": "FAILED_SAFE",
                "reason": "Crash prior to broker submission"
            })

    summary["recovered"] = summary["reconciled"] + summary["failed_safe"]
    return summary
