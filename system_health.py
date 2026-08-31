"""
System Health Gate & Live Automation Safety Evaluator (Phase 12B)
Evaluates holistic system health before permitting automated execution.
Deterministic and strictly fail-closed.
"""

from typing import Dict, Any, List
import database
import reconciliation
from broker_adapter import get_broker_adapter


def evaluate_system_health(broker: str = "MT5", mode: str = "PAPER") -> Dict[str, Any]:
    """
    Authoritative evaluator for system health and automated execution safety.
    Returns:
    {
        "automation_allowed": bool,
        "overall_status": "HEALTHY" | "DEGRADED" | "BLOCKED",
        "reasons": List[str],
        "checks": Dict[str, Any]
    }
    """
    reasons: List[str] = []
    checks: Dict[str, Any] = {}
    
    # 1. Global Kill Switch & Emergency Halt Check
    kill_switch = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper()
    sys_state = database.get_setting("SYSTEM_STATE", "PAPER").upper()
    checks["kill_switch_engaged"] = (kill_switch == "TRUE")
    checks["emergency_halt_engaged"] = (sys_state == "EMERGENCY HALT")
    
    if kill_switch == "TRUE":
        reasons.append("GLOBAL_KILL_SWITCH_ACTIVE: Execution kill switch is manually engaged.")
    if sys_state == "EMERGENCY HALT":
        reasons.append("EMERGENCY_HALT_ACTIVE: System is in EMERGENCY HALT state.")

    # 2. Database Health Check
    try:
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        checks["database_connected"] = True
    except Exception as e:
        checks["database_connected"] = False
        reasons.append(f"DATABASE_UNREACHABLE: Database health check failed: {e}")

    # 3. Background Reconciliation Worker Health Check
    recon_health = reconciliation.get_reconciliation_health(max_stale_seconds=60)
    checks["reconciliation"] = recon_health
    if mode in ["LIVE", "LIVE_MICRO"]:
        if not recon_health.get("healthy", False):
            reasons.append(f"RECONCILIATION_UNHEALTHY: {recon_health.get('reason')}")

    # 4. Unresolved UNKNOWN Execution Orders Check
    try:
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM execution_orders WHERE state = 'UNKNOWN'")
        unknown_count = cur.fetchone()[0]
        conn.close()
        checks["unresolved_unknown_orders_count"] = unknown_count
        if unknown_count > 0:
            reasons.append(f"UNRESOLVED_UNKNOWN_ORDERS: Found {unknown_count} orders in UNKNOWN state. Reconciliation required.")
    except Exception as e:
        reasons.append(f"EXECUTION_ORDERS_QUERY_FAILED: {e}")

    # 5. Broker Connection & Account State Health Check
    if mode in ["LIVE", "LIVE_MICRO"]:
        try:
            adapter = get_broker_adapter(broker)
            b_status = adapter.health_check()
            checks["broker_status"] = b_status
            if not b_status.connected:
                reasons.append(f"BROKER_DISCONNECTED: {broker} adapter is not connected: {b_status.error_message}")
        except Exception as e:
            reasons.append(f"BROKER_CHECK_FAILED: Unable to reach {broker} adapter: {e}")

    # 6. Orphan Position Check
    if mode in ["LIVE", "LIVE_MICRO"]:
        try:
            pos_recon = reconciliation.reconcile_open_positions(broker)
            checks["position_reconciliation"] = pos_recon
            if pos_recon.get("broker_only"):
                reasons.append(f"ORPHAN_POSITIONS_DETECTED: {len(pos_recon['broker_only'])} orphan positions exist on {broker}.")
        except Exception as e:
            reasons.append(f"POSITION_RECONCILIATION_FAILED: {e}")

    # Determination
    automation_allowed = (len(reasons) == 0)
    overall_status = "HEALTHY" if automation_allowed else "BLOCKED"

    return {
        "automation_allowed": automation_allowed,
        "overall_status": overall_status,
        "reasons": reasons,
        "checks": checks
    }
