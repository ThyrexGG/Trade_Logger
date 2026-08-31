"""
Tests for Restart & Crash Recovery (Phase 12B)
"""

import uuid
import pytest
from datetime import datetime, timezone
import database
import execution_pipeline
from execution_pipeline import ExecutionState, recover_incomplete_executions, persist_execution_state


def test_crash_recovery_unsubmitted_orders():
    """
    Orders stuck in VALIDATING or RISK_APPROVED (never submitted to broker)
    must transition safely to FAILED_SAFE upon recovery, without submitting blind duplicate orders.
    """
    exec_id_1 = f"crash_test_{uuid.uuid4().hex[:8]}"
    sig_id_1 = f"sig_crash_{uuid.uuid4().hex[:8]}"
    
    state_data = {
        "execution_id": exec_id_1,
        "signal_id": sig_id_1,
        "symbol": "EURUSD",
        "side": "BUY",
        "requested_quantity": 0.01,
        "requested_entry": 1.0850,
        "broker": "CAPITAL",
        "mode": "PAPER",
        "state": ExecutionState.VALIDATING,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    persist_execution_state(state_data)

    # Run recovery
    summary = recover_incomplete_executions()
    assert summary["recovered"] >= 1
    assert summary["failed_safe"] >= 1

    # Verify state in database is FAILED_SAFE
    conn = database.get_connection()
    cur = conn.cursor()
    query = "SELECT state, last_error FROM execution_orders WHERE execution_id = %s" if database.is_postgres() else "SELECT state, last_error FROM execution_orders WHERE execution_id = ?"
    cur.execute(query, (exec_id_1,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == ExecutionState.FAILED_SAFE
    assert "crashed before order submission" in row[1]
