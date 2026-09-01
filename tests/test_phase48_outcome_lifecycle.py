"""
Phase 48 — Tests for Deterministic Outcome Lifecycle (TP_HIT, SL_HIT, EXPIRED, CANCELLED, INVALIDATED)
"""

import pytest
import database
from datetime import datetime, timezone
from xauusd_forward_lifecycle import ForwardOutcomeLifecycleManager
from xauusd_forward_validator import XAUUSDForwardJournal


def test_lifecycle_event_recording():
    ev = ForwardOutcomeLifecycleManager.record_lifecycle_event(
        signal_id="SIG_TEST_48_001",
        observation_id="OBS_TEST_48_001",
        stage="SIGNAL_EVALUATION",
        from_status="DETECTED",
        to_status="ELIGIBLE",
        execution_mode="PAPER",
        outcome_reason="Passed 11-state eligibility gate."
    )
    assert ev["signal_id"] == "SIG_TEST_48_001"
    assert ev["transition"] == "DETECTED -> ELIGIBLE"
    assert len(ev["fingerprint"]) == 64

    # Clean up test event
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM xauusd_forward_lifecycle_events WHERE signal_id = 'SIG_TEST_48_001'")
    conn.commit()
    conn.close()


def test_trade_outcome_resolution():
    sig_id = "SIG_OUTCOME_TEST_001"
    try:
        # Create a test signal in xauusd_forward_signals
        XAUUSDForwardJournal.log_forward_signal({
            "signal_id": sig_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": "XAUUSD",
            "requested_entry": 2400.0,
            "stop_loss": 2395.0,
            "take_profit": 2415.0,
            "planned_rr": 3.0,
            "execution_mode": "PAPER",
            "status": "OPEN"
        })

        # Update to TP_HIT (COMPLETED)
        res = ForwardOutcomeLifecycleManager.update_trade_outcome(
            signal_id=sig_id,
            outcome="COMPLETED",
            realized_r=3.0,
            exit_price=2415.0,
            exit_reason="Take Profit Hit at 2415.0",
            holding_time_min=45
        )
        assert res["success"] is True
        assert res["to_status"] == "COMPLETED"
        assert res["realized_r"] == 3.0

        # Repeated update should report ALREADY_RESOLVED without duplicate mutation
        res_repeat = ForwardOutcomeLifecycleManager.update_trade_outcome(
            signal_id=sig_id,
            outcome="COMPLETED",
            realized_r=3.0
        )
        assert res_repeat["success"] is True
        assert res_repeat["status"] == "ALREADY_RESOLVED"

    finally:
        # Strict test isolation: Clean up test signal and lifecycle events
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM xauusd_forward_signals WHERE signal_id = ?", (sig_id,))
        cur.execute("DELETE FROM xauusd_forward_lifecycle_events WHERE signal_id = ?", (sig_id,))
        conn.commit()
        conn.close()
