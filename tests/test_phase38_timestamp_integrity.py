"""
Phase 38 — Timestamp Integrity & Strict No-Lookahead Test Suite
Validates that actual values are unavailable before event release timestamps,
while forecast and previous data remain properly accessible.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_news_history_audit import HistoricalContextReconstructor


def test_actual_value_unavailable_before_release():
    """Validates that querying before scheduled release timestamp masks actual value (no lookahead)."""
    target_dt = date(2026, 9, 1)
    
    # Query at 10:00 UTC (BEFORE 12:30 UTC US Macro releases)
    pre_release_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    recon = HistoricalContextReconstructor.reconstruct_date_context(
        target_date=target_dt,
        query_timestamp=pre_release_time
    )

    events = recon["events"]
    assert len(events) >= 1

    # Check that events scheduled at 12:30 UTC have actual == None and is_released == False
    for ev in events:
        sched_dt = datetime.fromisoformat(ev["scheduled_timestamp"].replace("Z", "+00:00"))
        if sched_dt > pre_release_time:
            assert ev["actual"] is None, f"Lookahead violation: Actual present before release for {ev['event_name']}"
            assert ev["is_released_at_query_time"] is False
            assert ev["actual_available_at"] == "NOT_YET_RELEASED"


def test_actual_value_available_after_release():
    """Validates that querying after scheduled release timestamp reveals actual release."""
    target_dt = date(2026, 9, 1)
    
    # Query at 18:00 UTC (AFTER 12:30 UTC US Macro releases)
    post_release_time = datetime(2026, 9, 1, 18, 0, 0, tzinfo=timezone.utc)
    recon = HistoricalContextReconstructor.reconstruct_date_context(
        target_date=target_dt,
        query_timestamp=post_release_time
    )

    events = recon["events"]
    assert len(events) >= 1

    for ev in events:
        sched_dt = datetime.fromisoformat(ev["scheduled_timestamp"].replace("Z", "+00:00"))
        if sched_dt <= post_release_time:
            assert ev["is_released_at_query_time"] is True
            assert ev["actual_available_at"] != "NOT_YET_RELEASED"


def test_forecast_and_previous_availability_prior_to_event():
    """Validates that forecast and previous estimates are known prior to release."""
    target_dt = date(2026, 9, 1)
    pre_release_time = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)
    recon = HistoricalContextReconstructor.reconstruct_date_context(
        target_date=target_dt,
        query_timestamp=pre_release_time
    )

    info_part = recon["information_partition"]
    assert len(info_part["known_prior_items"]) >= 1
    assert info_part["lookahead_protected"] is True

    for item in info_part["known_prior_items"]:
        assert "forecast" in item
        assert "previous" in item
        assert item["label"] == "[KNOWN PRIOR]"
