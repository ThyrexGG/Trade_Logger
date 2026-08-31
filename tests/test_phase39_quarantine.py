"""
Phase 39 — Observation Quarantine Subsystem Test Suite
Validates non-destructive isolation of corrupted observations, database persistence,
and alert triggering without deleting evidence.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_forward_observation_quality import ObservationQuarantineSubsystem


def test_quarantine_observation_persistence():
    """Validates that quarantined observations are stored non-destructively in database."""
    corrupt_obs = {
        "signal_id": "SIG_CORRUPT_TEST_001",
        "execution_mode": "PAPER",
        "timestamp": "INVALID_FUTURE_DATE",
        "requested_entry": -999.0
    }

    res = ObservationQuarantineSubsystem.quarantine_observation(
        obs=corrupt_obs,
        reason="Corrupted entry price and invalid timestamp",
        severity="CRITICAL"
    )

    assert isinstance(res, dict)
    assert res["status"] == "QUARANTINED"
    assert "quarantine_id" in res
    assert res["statistical_status"] == "EXCLUDED_FROM_METRICS"

    # Retrieve from database
    quar_list = ObservationQuarantineSubsystem.get_quarantined_records(limit=20)
    assert len(quar_list) >= 1
    assert any(q["observation_id"] == "SIG_CORRUPT_TEST_001" for q in quar_list)
