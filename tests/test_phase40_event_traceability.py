"""
Phase 40 — Event Impact Traceability Test Suite
Validates:
1. Classification of proximity buckets (0-15 MIN, 15-30 MIN, 30-60 MIN, 1-3 HOURS, etc.).
2. Temporal partitioning of observations (BEFORE, DURING, AFTER).
3. Traceability output structure and fingerprinting.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_event_traceability import EventImpactTraceEngine


def test_proximity_bucket_classification():
    """Validates proximity bucket boundaries."""
    assert EventImpactTraceEngine.classify_proximity_bucket(300) == "0-15 MIN"
    assert EventImpactTraceEngine.classify_proximity_bucket(-800) == "0-15 MIN"
    assert EventImpactTraceEngine.classify_proximity_bucket(1200) == "15-30 MIN"
    assert EventImpactTraceEngine.classify_proximity_bucket(2400) == "30-60 MIN"
    assert EventImpactTraceEngine.classify_proximity_bucket(7200) == "1-3 HOURS"
    assert EventImpactTraceEngine.classify_proximity_bucket(15000) == "3-6 HOURS"
    assert EventImpactTraceEngine.classify_proximity_bucket(50000) == "6-24 HOURS"
    assert EventImpactTraceEngine.classify_proximity_bucket(100000) == ">24 HOURS"


def test_event_impact_trace_observations_partitioning():
    """Validates before, during, and after observation partitioning around macro release."""
    ev_time = datetime(2026, 9, 1, 12, 30, 0, tzinfo=timezone.utc)
    event = {
        "event_name": "US Non-Farm Payrolls",
        "currency": "USD",
        "impact": "HIGH",
        "scheduled_timestamp": ev_time.isoformat(),
        "forecast": "180K",
        "previous": "175K",
        "actual": "210K"
    }

    obs_list = [
        {"signal_id": "OBS_BEFORE", "timestamp": (ev_time - timedelta(minutes=45)).isoformat(), "realized_r": 0.5},
        {"signal_id": "OBS_DURING", "timestamp": (ev_time + timedelta(minutes=5)).isoformat(), "realized_r": -1.0},
        {"signal_id": "OBS_AFTER", "timestamp": (ev_time + timedelta(hours=2)).isoformat(), "realized_r": 1.2},
    ]

    trace = EventImpactTraceEngine.trace_event_impact(event, obs_list)

    assert trace["total_observations_evaluated"] == 3
    assert trace["observations_before_count"] == 1
    assert trace["observations_during_count"] == 1
    assert trace["observations_after_count"] == 1
    assert len(trace["affected_observations"]) == 2  # OBS_BEFORE (45m) and OBS_DURING (5m) within 1h
    assert len(trace["provenance_fingerprint"]) == 64
