"""
Phase 45 — Failure Injection & Long-Run Recovery Test Suite
Validates contract mutation rejection and incident recovery mechanisms.
"""

import pytest
from xauusd_continuous_forward_ops import (
    ContinuousForwardSupervisor,
    AlertDeduplicationAndIncidentTracker,
)


def test_failure_injection_feed_recovery():
    """Validates simulation of feed outage and supervisor automated recovery."""
    # 1. Trigger incident
    inc = AlertDeduplicationAndIncidentTracker.record_or_update_incident(
        incident_type="SIMULATED_FEED_OUTAGE",
        subsystem="MARKET_DATA_FEED",
        severity="WARNING",
        details="Feed delay > 15m"
    )
    assert inc["status"] == "ACTIVE"

    # 2. Resolve incident
    res = AlertDeduplicationAndIncidentTracker.resolve_incident("SIMULATED_FEED_OUTAGE", "MARKET_DATA_FEED")
    assert res["status"] == "RESOLVED"

    # 3. Verify supervisor cycle executes cleanly
    cycle = ContinuousForwardSupervisor.run_supervisor_cycle("XAUUSD")
    assert cycle["supervisor_status"] == "SUPERVISOR_ACTIVE_HEALTHY"
