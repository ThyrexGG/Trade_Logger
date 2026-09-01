"""
Phase 45 — Alert Deduplication & Incident Tracking Test Suite
Validates incident creation, active duration updates, and resolution without alert spam.
"""

import pytest
from xauusd_continuous_forward_ops import AlertDeduplicationAndIncidentTracker


def test_incident_deduplication_and_resolution():
    """Validates incident deduplication and resolution lifecycle."""
    inc1 = AlertDeduplicationAndIncidentTracker.record_or_update_incident(
        incident_type="TEST_OUTAGE",
        subsystem="MARKET_DATA_FEED",
        severity="WARNING",
        details="Temporary latency spike"
    )
    assert inc1["action"] == "CREATED_NEW_INCIDENT"
    assert inc1["status"] == "ACTIVE"

    # Second call updates existing incident rather than duplicating
    inc2 = AlertDeduplicationAndIncidentTracker.record_or_update_incident(
        incident_type="TEST_OUTAGE",
        subsystem="MARKET_DATA_FEED",
        severity="WARNING",
        details="Latency spike continuing"
    )
    assert inc2["action"] == "UPDATED_EXISTING_INCIDENT"
    assert inc2["incident_id"] == inc1["incident_id"]

    # Resolution
    res = AlertDeduplicationAndIncidentTracker.resolve_incident("TEST_OUTAGE", "MARKET_DATA_FEED")
    assert res is not None
    assert res["status"] == "RESOLVED"
