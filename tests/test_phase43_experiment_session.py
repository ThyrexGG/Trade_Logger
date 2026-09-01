"""
Phase 43 — Overnight Experiment Session Test Suite
Validates session start, end, persistence, and SHA-256 fingerprinting.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_overnight_experiment import OvernightExperimentSessionEngine


def test_start_and_end_overnight_session():
    """Validates complete session lifecycle."""
    sess_start = OvernightExperimentSessionEngine.start_session("XAUUSD")

    assert "session_id" in sess_start
    assert sess_start["status"] == "ACTIVE"
    assert len(sess_start["session_fingerprint"]) == 64
    assert sess_start["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"

    # End session
    sess_end = OvernightExperimentSessionEngine.end_session(sess_start["session_id"], "XAUUSD")
    assert "end_time" in sess_end
    assert "reconciliation" in sess_end
    assert sess_end["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"

    # Retrieve sessions
    recent = OvernightExperimentSessionEngine.get_recent_sessions(limit=5)
    assert len(recent) >= 1
    assert any(s["session_id"] == sess_start["session_id"] for s in recent)
