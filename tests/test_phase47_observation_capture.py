"""
Phase 47 — Observation Capture Test Suite
Validates atomic capture of genuine forward observations with full metadata.
Cleans up test records to preserve pristine N = 0 production state.
"""

from datetime import datetime, timezone
import pytest
import database
from xauusd_forward_evidence_collection import (
    ForwardObservationCaptureEngine,
    ObservationDuplicateProtectionEngine,
)


def test_observation_capture_and_deduplication():
    """Validates observation capture and duplicate detection."""
    obs_id = f"TEST_CAP_{datetime.now(timezone.utc).timestamp()}"
    obs_payload = {
        "signal_id": obs_id,
        "symbol": "XAUUSD",
        "direction": "BUY",
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": 2500.0,
        "exit_time": datetime.now(timezone.utc).isoformat(),
        "exit_price": 2510.0,
        "r_multiple": 1.0,
        "execution_mode": "PAPER",
        "strategy_contract_hash": "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    }

    try:
        # 1. First capture
        res1 = ForwardObservationCaptureEngine.capture_forward_observation(obs_payload)
        assert res1["capture_status"] == "CAPTURED_AND_VALIDATED"
        assert res1["is_captured"] is True

        # 2. Replay / Duplicate attempt
        res2 = ForwardObservationCaptureEngine.capture_forward_observation(obs_payload)
        assert res2["capture_status"] == "DUPLICATE_IGNORED"
        assert res2["is_captured"] is False
    finally:
        # Clean up test records
        conn = database.get_connection()
        cur = conn.cursor()
        placeholder = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM xauusd_forward_signals WHERE signal_id = {placeholder}", (obs_id,))
        cur.execute(f"DELETE FROM xauusd_forward_observation_events WHERE observation_id = {placeholder}", (obs_id,))
        conn.commit()
        conn.close()
