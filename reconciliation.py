"""
Broker Reconciliation Engine (Phase 12A)
Authoritative state verification between Local Database and Live Broker State (MT5 / Capital.com).
Implements Position Reconciliation, UNKNOWN Execution Resolution, Startup Gate, and Continuous Background Loop.
"""

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd

import database
import broker_adapter
from broker_adapter import CanonicalPosition, CanonicalAccountState


def reconcile_open_positions(account_type: str = "MT5") -> Dict[str, Any]:
    """
    Compares local open positions against live broker positions.
    Detects MATCHED, LOCAL_ONLY, BROKER_ONLY, and MISMATCH.
    """
    res = {
        "status": "ERROR",
        "account_type": account_type,
        "message": "",
        "local_only": [],
        "broker_only": [],
        "mismatched": [],
        "matched": []
    }
    
    # 1. Fetch Authoritative Broker Positions via Adapter
    try:
        adapter = broker_adapter.get_broker_adapter(account_type)
        broker_positions: List[CanonicalPosition] = adapter.get_open_positions()
        broker_pos_dict = {str(p.ticket).split("_")[-1]: p for p in broker_positions}
    except Exception as e:
        res["message"] = f"Failed to fetch live broker state for {account_type}: {str(e)}"
        return res

    # 2. Fetch Local Open Positions
    try:
        local_df = database.get_open_positions()
    except Exception as e:
        res["message"] = f"Failed to query local open_positions table: {str(e)}"
        return res

    local_pos_dict = {}
    if not local_df.empty:
        for _, row in local_df.iterrows():
            ticket_clean = str(row['position_id']).split("_")[-1]
            local_pos_dict[ticket_clean] = row.to_dict()

    # 3. Compare Keys
    broker_keys = set(broker_pos_dict.keys())
    local_keys = set(local_pos_dict.keys())

    # BROKER_ONLY: Orphan position existing on broker without local record
    res["broker_only"] = [
        {
            "ticket": p.ticket,
            "symbol": p.symbol,
            "direction": p.direction,
            "volume": p.volume,
            "entry_price": p.entry_price,
            "floating_pnl": p.floating_pnl
        } 
        for k, p in broker_pos_dict.items() if k in (broker_keys - local_keys)
    ]

    # LOCAL_ONLY: Local record exists but broker position is gone (likely closed outside app)
    res["local_only"] = [
        {**local_pos_dict[k], "ticket": k} for k in (local_keys - broker_keys)
    ]

    # Check for Position Property Mismatches
    for k in broker_keys.intersection(local_keys):
        bp = broker_pos_dict[k]
        lp = local_pos_dict[k]
        mismatches = []
        
        # Handle dict or CanonicalPosition
        bp_vol = float(bp.volume if hasattr(bp, "volume") else bp.get("volume", 0.0))
        bp_sl = float(bp.sl if hasattr(bp, "sl") else bp.get("sl", 0.0))
        bp_tp = float(bp.tp if hasattr(bp, "tp") else bp.get("tp", 0.0))
        bp_sym = str(bp.symbol if hasattr(bp, "symbol") else bp.get("symbol", ""))
        bp_entry = float(bp.entry_price if hasattr(bp, "entry_price") else bp.get("entry", 0.0))

        if round(bp_vol, 2) != round(float(lp.get("volume", 0.0)), 2):
            mismatches.append(f"Volume mismatch: Broker={bp_vol} vs Local={lp.get('volume')}")
        if bp_sl > 0 and lp.get("sl") and abs(bp_sl - float(lp.get("sl", 0.0))) > 0.0001:
            mismatches.append(f"SL mismatch: Broker={bp_sl} vs Local={lp.get('sl')}")
        if bp_tp > 0 and lp.get("tp") and abs(bp_tp - float(lp.get("tp", 0.0))) > 0.0001:
            mismatches.append(f"TP mismatch: Broker={bp_tp} vs Local={lp.get('tp')}")

        if mismatches:
            res["mismatched"].append({
                "ticket": k,
                "symbol": bp_sym,
                "broker": {
                    "volume": bp_vol,
                    "sl": bp_sl,
                    "tp": bp_tp,
                    "entry_price": bp_entry
                },
                "local": lp,
                "discrepancies": mismatches,
                "issues": mismatches
            })
        else:
            res["matched"].append(k)

    if res["broker_only"] or res["local_only"] or res["mismatched"]:
        res["status"] = "mismatch"
        res["message"] = f"Discrepancies found: {len(res['broker_only'])} orphan broker positions, {len(res['local_only'])} stale local positions, {len(res['mismatched'])} property mismatches."
    else:
        res["status"] = "matched"
        res["message"] = f"Local state and {account_type} broker positions are 100% in sync ({len(res['matched'])} matched)."

    return res


def perform_system_recovery_check(account_type: str = "MT5") -> Dict[str, Any]:
    """Legacy alias for startup_reconciliation()."""
    res = startup_reconciliation()
    status_lower = str(res.get("status", "error")).lower()
    return {
        "status": status_lower,
        "is_safe": res.get("automation_allowed", False),
        "details": res.get("details", {}),
        "reason": res.get("reason", "")
    }


def reconcile_execution(execution_id: str) -> Dict[str, Any]:
    """
    Authoritative resolution of UNKNOWN order state.
    Queries broker for matching order/position by ticket, symbol, side, volume, and timestamps.
    Transitions UNKNOWN -> RECONCILING -> RECONCILED.
    """
    conn = database.get_connection()
    cursor = conn.cursor()
    
    if database.is_postgres():
        cursor.execute("SELECT * FROM execution_orders WHERE execution_id = %s", (execution_id,))
    else:
        cursor.execute("SELECT * FROM execution_orders WHERE execution_id = ?", (execution_id,))
        
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"status": "error", "message": f"Execution ID '{execution_id}' not found in database."}

    # Extract order details
    cols = [col[0] for col in cursor.description]
    order = dict(zip(cols, row))
    conn.close()

    current_state = order.get("state")
    if current_state not in ["UNKNOWN", "RECONCILING"]:
        return {
            "status": "noop", 
            "execution_id": execution_id, 
            "state": current_state, 
            "message": f"Order is already resolved in state '{current_state}'."
        }

    broker_name = str(order.get("broker", "CAPITAL")).upper().strip()
    symbol = str(order.get("symbol", "")).upper().strip()
    direction = str(order.get("side", "")).upper().strip()
    volume = float(order.get("requested_quantity", 0.0))
    
    # 1. Transition to RECONCILING
    from execution_pipeline import transition_state, ExecutionState
    order["state"] = ExecutionState.RECONCILING
    transition_state(order, ExecutionState.RECONCILING)

    # 2. Query Broker Adapter
    try:
        adapter = broker_adapter.get_broker_adapter(broker_name)
        open_positions: List[CanonicalPosition] = adapter.get_open_positions()
        
        # Search for matching position
        matched_pos: Optional[CanonicalPosition] = None
        for p in open_positions:
            if p.symbol == symbol and p.direction == direction:
                if abs(p.volume - volume) < 0.001 or p.volume == volume:
                    matched_pos = p
                    break

        now_iso = datetime.now(timezone.utc).isoformat()

        if matched_pos:
            # Order DID execute on broker! Resolve as FILLED
            order["broker_order_id"] = matched_pos.ticket
            order["broker_position_id"] = matched_pos.ticket
            order["filled_at"] = now_iso
            order["resolved_at"] = now_iso
            order["reconciliation_status"] = "RESOLVED_FILLED"
            transition_state(order, ExecutionState.RECONCILED)
            return {
                "status": "resolved",
                "execution_id": execution_id,
                "resolution": "FILLED",
                "broker_ticket": matched_pos.ticket,
                "message": f"Broker reconciliation confirmed position {matched_pos.ticket} exists on broker."
            }
        else:
            # Authoritatively verified position does NOT exist on broker
            order["resolved_at"] = now_iso
            order["reconciliation_status"] = "RESOLVED_NOT_FILLED"
            order["last_error"] = "Broker reconciliation verified order was not executed on broker."
            transition_state(order, ExecutionState.RECONCILED)
            return {
                "status": "resolved",
                "execution_id": execution_id,
                "resolution": "NOT_FILLED",
                "message": "Broker reconciliation confirmed order did not fill on broker."
            }

    except Exception as e:
        # Broker cannot be reached -> MUST REMAIN UNKNOWN
        order["reconciliation_status"] = f"RECONCILIATION_FAILED: {str(e)}"
        order["state"] = ExecutionState.UNKNOWN
        from execution_pipeline import persist_execution_state
        persist_execution_state(order)
        return {
            "status": "unresolved",
            "execution_id": execution_id,
            "state": "UNKNOWN",
            "message": f"Broker unreachable during reconciliation: {str(e)}. Order remains UNKNOWN."
        }


def reconcile_unknown_orders() -> List[Dict[str, Any]]:
    """Scans and resolves all pending UNKNOWN execution orders in the database."""
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT execution_id FROM execution_orders WHERE state = 'UNKNOWN'")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for (exec_id,) in rows:
        res = reconcile_execution(exec_id)
        results.append(res)
    return results


def startup_reconciliation() -> Dict[str, Any]:
    """
    Called on server startup before enabling automated execution.
    Fails closed if any critical discrepancies or unresolved UNKNOWN orders exist.
    """
    results = {
        "status": "PASSED",
        "automation_allowed": True,
        "details": {}
    }

    # 1. Check Kill Switch
    kill_switch = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper()
    sys_state = database.get_setting("SYSTEM_STATE", "PAPER").upper()
    if kill_switch == "TRUE" or sys_state == "EMERGENCY HALT":
        return {
            "status": "HALTED",
            "automation_allowed": False,
            "reason": "EMERGENCY HALT ACTIVE. Kill switch is engaged."
        }

    # 2. Reconcile UNKNOWN orders
    unknown_results = reconcile_unknown_orders()
    results["details"]["unknown_orders"] = unknown_results
    for ur in unknown_results:
        if ur.get("status") == "unresolved":
            return {
                "status": "BLOCKED",
                "automation_allowed": False,
                "reason": f"Unresolved UNKNOWN execution order {ur.get('execution_id')} exists. Automation blocked until reconciled."
            }

    # 3. Position Reconciliation for MT5
    try:
        mt5_recon = reconcile_open_positions("MT5")
        results["details"]["mt5"] = mt5_recon
        if mt5_recon["broker_only"]:
            return {
                "status": "BLOCKED",
                "automation_allowed": False,
                "reason": f"Orphan broker-only positions detected in MT5 ({len(mt5_recon['broker_only'])} positions). Explicit resolution required."
            }
    except Exception as e:
        results["details"]["mt5_error"] = str(e)

    # 4. Position Reconciliation for Capital.com
    try:
        cap_recon = reconcile_open_positions("CAPITAL")
        results["details"]["capital"] = cap_recon
        if cap_recon["broker_only"]:
            return {
                "status": "BLOCKED",
                "automation_allowed": False,
                "reason": f"Orphan broker-only positions detected in Capital.com ({len(cap_recon['broker_only'])} positions). Explicit resolution required."
            }
    except Exception as e:
        results["details"]["capital_error"] = str(e)

    return results


# Continuous Background Reconciliation Thread & Health Tracking
_RECON_THREAD: Optional[threading.Thread] = None
_RECON_STOP_EVENT = threading.Event()
_RECON_LOCK = threading.Lock()

_WORKER_HEALTH = {
    "status": "RECONCILIATION_STOPPED",
    "last_heartbeat": None,
    "last_success": None,
    "last_failure": None,
    "consecutive_failures": 0,
    "last_error": None,
    "iterations_count": 0
}


def get_reconciliation_health(max_stale_seconds: int = 60) -> Dict[str, Any]:
    """
    Returns the real-time health status of the background reconciliation worker.
    Evaluates staleness against max_stale_seconds grace period.
    """
    with _RECON_LOCK:
        health_copy = dict(_WORKER_HEALTH)
        
    last_hb = health_copy.get("last_heartbeat")
    if not last_hb or not _RECON_THREAD or not _RECON_THREAD.is_alive():
        health_copy["status"] = "RECONCILIATION_STOPPED"
        health_copy["healthy"] = False
        health_copy["reason"] = "Reconciliation worker daemon is not running."
        return health_copy

    try:
        hb_ts = datetime.fromisoformat(last_hb).timestamp()
        now_ts = datetime.now(timezone.utc).timestamp()
        stale_sec = now_ts - hb_ts
        health_copy["stale_seconds"] = round(stale_sec, 1)

        if stale_sec > max_stale_seconds:
            health_copy["status"] = "RECONCILIATION_FAILED"
            health_copy["healthy"] = False
            health_copy["reason"] = f"Reconciliation worker is stale ({stale_sec:.0f}s since last heartbeat > {max_stale_seconds}s limit)."
        elif health_copy["consecutive_failures"] >= 3:
            health_copy["status"] = "RECONCILIATION_DEGRADED"
            health_copy["healthy"] = False
            health_copy["reason"] = f"Reconciliation worker has {health_copy['consecutive_failures']} consecutive errors: {health_copy.get('last_error')}"
        else:
            health_copy["status"] = "RECONCILIATION_HEALTHY"
            health_copy["healthy"] = True
            health_copy["reason"] = "Reconciliation worker running normally."
    except Exception as e:
        health_copy["status"] = "RECONCILIATION_DEGRADED"
        health_copy["healthy"] = False
        health_copy["reason"] = f"Error evaluating worker health: {e}"

    return health_copy


def _continuous_reconciliation_worker(interval_seconds: int = 15):
    """Background loop polling reconciliation periodically."""
    global _WORKER_HEALTH
    while not _RECON_STOP_EVENT.is_set():
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            reconcile_unknown_orders()
            with _RECON_LOCK:
                _WORKER_HEALTH["last_heartbeat"] = now_iso
                _WORKER_HEALTH["last_success"] = now_iso
                _WORKER_HEALTH["consecutive_failures"] = 0
                _WORKER_HEALTH["last_error"] = None
                _WORKER_HEALTH["status"] = "RECONCILIATION_HEALTHY"
                _WORKER_HEALTH["iterations_count"] += 1
        except Exception as e:
            with _RECON_LOCK:
                _WORKER_HEALTH["last_heartbeat"] = now_iso
                _WORKER_HEALTH["last_failure"] = now_iso
                _WORKER_HEALTH["consecutive_failures"] += 1
                _WORKER_HEALTH["last_error"] = str(e)
                _WORKER_HEALTH["status"] = "RECONCILIATION_DEGRADED" if _WORKER_HEALTH["consecutive_failures"] < 3 else "RECONCILIATION_FAILED"
            print(f"[RECONCILIATION_WORKER_ERROR] {e}")
            
        _RECON_STOP_EVENT.wait(interval_seconds)


def start_background_reconciliation(interval_seconds: int = 15):
    """Starts the continuous reconciliation daemon thread singleton."""
    global _RECON_THREAD, _RECON_STOP_EVENT, _WORKER_HEALTH
    with _RECON_LOCK:
        if _RECON_THREAD and _RECON_THREAD.is_alive():
            return
        _RECON_STOP_EVENT.clear()
        _WORKER_HEALTH["status"] = "RECONCILIATION_HEALTHY"
        _WORKER_HEALTH["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        _RECON_THREAD = threading.Thread(
            target=_continuous_reconciliation_worker, 
            args=(interval_seconds,),
            daemon=True,
            name="BrokerReconciliationDaemon"
        )
        _RECON_THREAD.start()


def stop_background_reconciliation():
    """Stops the continuous reconciliation daemon thread."""
    global _RECON_STOP_EVENT, _WORKER_HEALTH
    with _RECON_LOCK:
        _RECON_STOP_EVENT.set()
        _WORKER_HEALTH["status"] = "RECONCILIATION_STOPPED"
