"""
Phase 39 — News Feedback & Lookahead Auditor Test Suite
Validates strict information horizon partitioning:
- [KNOWN PRIOR]
- [OBSERVED AT TIME]
- [POST-EVENT]
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_forward_observation_quality import NewsFeedbackLookaheadAuditor


def test_clean_information_horizon_partitioning():
    """Validates that past events are observed and future events are correctly marked post-event."""
    obs_time = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
    obs = {
        "signal_id": "SIG_HORIZON_001",
        "timestamp": obs_time.isoformat(),
        "requested_entry": 2400.0,
    }

    scheduled_events = [
        {
            "event_name": "US Core CPI",
            "currency": "USD",
            "impact": "HIGH",
            "scheduled_timestamp": "2026-09-01T12:30:00+00:00",
            "forecast": "0.3%",
            "previous": "0.2%",
            "actual": "0.4%",
        },
        {
            "event_name": "FOMC Meeting Minutes",
            "currency": "USD",
            "impact": "HIGH",
            "scheduled_timestamp": "2026-09-01T18:00:00+00:00",
            "forecast": "N/A",
            "previous": "N/A",
            "actual": "Released Later",
        }
    ]

    res = NewsFeedbackLookaheadAuditor.audit_observation_information_horizon(obs, scheduled_events)

    assert res["lookahead_protected"] is True
    assert res["status"] == "LOOKAHEAD FREE"
    assert res["known_prior_count"] == 2
    assert res["observed_at_time_count"] == 1
    assert res["post_event_count"] == 1
    assert res["observed_at_time"][0]["event_name"] == "US Core CPI"
    assert res["post_event_info"][0]["event_name"] == "FOMC Meeting Minutes"


def test_lookahead_violation_detection():
    """Validates that if future release actual is contained in observation payload, it is flagged."""
    obs_time = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
    obs_with_future_leak = {
        "signal_id": "SIG_LEAK_001",
        "timestamp": obs_time.isoformat(),
        "requested_entry": 2400.0,
        "nearest_event_actual": "LEAKED_FUTURE_ACTUAL_FIGURE"
    }

    scheduled_events = [
        {
            "event_name": "FOMC Rate Decision",
            "currency": "USD",
            "impact": "HIGH",
            "scheduled_timestamp": "2026-09-01T18:00:00+00:00",
            "forecast": "5.50%",
            "previous": "5.25%",
            "actual": "5.50%",
        }
    ]

    res = NewsFeedbackLookaheadAuditor.audit_observation_information_horizon(obs_with_future_leak, scheduled_events)

    assert res["lookahead_protected"] is False
    assert res["lookahead_violations_count"] >= 1
    assert res["status"] == "LOOKAHEAD CONTAMINATION DETECTED"
