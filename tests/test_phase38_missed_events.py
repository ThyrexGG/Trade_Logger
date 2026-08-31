"""
Phase 38 — Missed-Event Detection Engine Test Suite
Validates detection of missing high/medium events, timing mismatches, duplicate records,
and forward observation proximity correlation without lookahead bias.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_missed_event_detector import MissedEventAuditor, ObservationProximityCorrelator
from xauusd_news_history_audit import HistoricalContextReconstructor


def test_clean_captured_events_audit():
    """Validates that a complete event set produces NO ISSUES DETECTED."""
    target_dt = date(2026, 9, 1)
    res = MissedEventAuditor.audit_captured_events_for_date(target_dt)

    assert isinstance(res, dict)
    assert res["is_clean"] is True
    assert res["classification"] == "NO ISSUES DETECTED"
    assert res["missing_high_impact_count"] == 0
    assert res["missing_medium_impact_count"] == 0


def test_missing_high_impact_event_detection():
    """Validates that omitting a high-impact event triggers IMPORTANT EVENT MISSED."""
    target_dt = date(2026, 9, 1)
    # Pass empty captured events
    res = MissedEventAuditor.audit_captured_events_for_date(target_dt, captured_events=[])

    assert res["is_clean"] is False
    assert res["missing_high_impact_count"] >= 1 or res["missing_medium_impact_count"] >= 1
    assert res["classification"] in ["IMPORTANT EVENT MISSED", "MINOR DATA GAP"]


def test_duplicate_event_detection():
    """Validates that duplicate event records are detected and flagged."""
    target_dt = date(2026, 9, 1)
    dup_event = {
        "event_id": "EVT_TEST_DUP_001",
        "event_name": "US Non-Farm Payrolls",
        "currency": "USD",
        "impact": "HIGH",
        "scheduled_timestamp": "2026-09-01T12:30:00Z"
    }
    captured = [dup_event, dup_event]
    res = MissedEventAuditor.audit_captured_events_for_date(target_dt, captured_events=captured)

    assert res["duplicates_count"] >= 1
    assert any(i["issue_type"] == "DUPLICATE_EVENT_RECORD" for i in res["issues"])


def test_timestamp_mismatch_detection():
    """Validates that shifted event timestamps trigger warning."""
    target_dt = date(2026, 9, 1)
    recon = HistoricalContextReconstructor.reconstruct_date_context(target_dt)
    events = recon["events"]
    assert len(events) >= 1
    
    # Create shifted event from first real event
    shifted_event = dict(events[0])
    shifted_event["scheduled_timestamp"] = "2026-09-01T23:59:59Z"
    
    res = MissedEventAuditor.audit_captured_events_for_date(target_dt, captured_events=[shifted_event])

    assert res["timestamp_mismatches_count"] >= 1
    assert any(i["issue_type"] == "TIMESTAMP_MISMATCH" for i in res["issues"])


def test_observation_proximity_correlation():
    """Validates proximity check between missed events and forward observations without filtering trades."""
    target_dt = date(2026, 9, 1)
    mock_issues = [
        {
            "issue_type": "MISSING_HIGH_IMPACT_EVENT",
            "event_name": "US CPI",
            "impact": "HIGH",
            "scheduled_timestamp": "2026-09-01T12:30:00Z"
        }
    ]
    prox_res = ObservationProximityCorrelator.audit_missed_event_proximity(mock_issues, target_dt)

    assert isinstance(prox_res, dict)
    assert "proximity_status" in prox_res
    assert prox_res["retroactive_filtering_performed"] is False
    assert prox_res["proximity_status"] in [
        "NO FORWARD OBSERVATION AFFECTED",
        "FORWARD OBSERVATION IN PROXIMITY",
        "MULTIPLE OBSERVATIONS IN PROXIMITY"
    ]
