"""
Phase 48 — Tests for Duplicate / Replay Protection in Observation Bridge
"""

import pytest
import database
from datetime import datetime, timezone
from xauusd_forward_lifecycle import ForwardSignalToObservationBridge


def test_rejected_signals_not_promoted():
    # Signal with missing provenance must be rejected and not promoted to observation
    bad_signal = {
        "signal_id": "SIG_REPLAY_TEST_BAD_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        # Missing required entry/sl/tp
    }
    res = ForwardSignalToObservationBridge.process_signal_to_observation(bad_signal)
    assert res["success"] is False
    assert res["observation_id"] is None
    assert "REJECTED" in res["status"]

    # Clean up test event
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM xauusd_forward_lifecycle_events WHERE signal_id = 'SIG_REPLAY_TEST_BAD_001'")
    conn.commit()
    conn.close()
