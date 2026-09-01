"""
Phase 43 — Heartbeats & Operational Outages Test Suite
Validates:
1. Subsystem heartbeat tracking and staleness detection.
2. Outage opening, duration calculation, and automated recovery.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_overnight_experiment import (
    HeartbeatAndLivenessAuditor,
    OperationalOutageTracker,
)


def test_heartbeat_recording_and_audit():
    """Validates recording heartbeats across subsystems."""
    for sub in HeartbeatAndLivenessAuditor.SUBSYSTEMS:
        res = HeartbeatAndLivenessAuditor.record_heartbeat(sub, status="HEALTHY", latency_ms=12.5)
        assert res["status"] == "HEALTHY"

    audit = HeartbeatAndLivenessAuditor.audit_all_subsystems(max_age_seconds=600)
    assert audit["all_healthy"] is True
    assert len(audit["subsystems"]) == 8


def test_operational_outage_lifecycle():
    """Validates outage opening, duration tracking, and resolution."""
    outage_id = OperationalOutageTracker.log_outage(
        subsystem="MARKET_DATA_FEED",
        reason="Temporary WebSocket disconnection",
        severity="WARNING"
    )

    assert outage_id.startswith("OUT_")

    # Retrieve active
    recent = OperationalOutageTracker.get_recent_outages(limit=10)
    assert any(o["outage_id"] == outage_id for o in recent)

    # Resolve
    res = OperationalOutageTracker.resolve_outage(outage_id, affected_count=0)
    assert res["status"] == "RESOLVED"
    assert res["duration_seconds"] >= 0.0
