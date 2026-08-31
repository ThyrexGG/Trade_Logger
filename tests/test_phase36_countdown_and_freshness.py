"""
Phase 36 — Event Countdown Proximity & Calendar Freshness Test Suite
Validates countdown proximity buckets and freshness audits.
"""

import pytest
from datetime import datetime, timezone, timedelta
from xauusd_news_reliability import NewsCountdownEngine, CalendarFreshnessAuditor


def test_countdown_proximity_buckets():
    """Validates deterministic countdown proximity bucket assignment."""
    now = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

    # 10m in the future -> 0–15 MIN
    t_10m = (now + timedelta(minutes=10)).isoformat()
    res1 = NewsCountdownEngine.calculate_countdown(t_10m, now)
    assert res1["proximity_bucket"] == "0–15 MIN"
    assert res1["is_active_window"] is True

    # 25m in the future -> 15–30 MIN
    t_25m = (now + timedelta(minutes=25)).isoformat()
    res2 = NewsCountdownEngine.calculate_countdown(t_25m, now)
    assert res2["proximity_bucket"] == "15–30 MIN"

    # 45m in the future -> 30–60 MIN
    t_45m = (now + timedelta(minutes=45)).isoformat()
    res3 = NewsCountdownEngine.calculate_countdown(t_45m, now)
    assert res3["proximity_bucket"] == "30–60 MIN"

    # 45m in the past -> POST-EVENT
    t_past = (now - timedelta(minutes=45)).isoformat()
    res4 = NewsCountdownEngine.calculate_countdown(t_past, now)
    assert res4["proximity_bucket"] == "POST-EVENT"
    assert res4["is_post_event"] is True


def test_calendar_freshness_auditor():
    """Validates FRESH, AGING, STALE classifications based on feed retrieval age."""
    now = datetime.now(timezone.utc)

    # Fresh data (<300s)
    fresh_cal = {
        "retrieval_timestamp": (now - timedelta(seconds=100)).isoformat(),
        "events": [{"event_name": "CPI", "scheduled_time": "12:30", "currency": "USD"}],
        "provider_status": "ACTIVE",
    }
    audit_fresh = CalendarFreshnessAuditor.audit_freshness(fresh_cal)
    assert audit_fresh["freshness_status"] == "FRESH"

    # Stale data (>1800s)
    stale_cal = {
        "retrieval_timestamp": (now - timedelta(seconds=3600)).isoformat(),
        "events": [{"event_name": "CPI", "scheduled_time": "12:30", "currency": "USD"}],
        "provider_status": "ACTIVE",
    }
    audit_stale = CalendarFreshnessAuditor.audit_freshness(stale_cal)
    assert audit_stale["freshness_status"] == "STALE"
