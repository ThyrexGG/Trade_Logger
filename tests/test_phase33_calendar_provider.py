"""
Phase 33 — Economic Calendar Live & Provider Honesty Test Suite
Validates economic calendar event retrieval, provider honesty (LIVE vs FALLBACK),
source labeling, and dataset fingerprinting.
"""

import pytest
from xauusd_market_conditions import EconomicCalendarProvider


def test_calendar_provider_honesty():
    """Validates that calendar provider returns explicit provider_status and source_name."""
    cal = EconomicCalendarProvider.get_todays_calendar()
    assert isinstance(cal, dict)
    assert "provider_status" in cal
    assert cal["provider_status"] in ["LIVE", "FALLBACK", "UNAVAILABLE"]
    assert "source_name" in cal
    assert "forex_factory_live_status" in cal
    assert "dataset_fingerprint" in cal
    assert len(cal["dataset_fingerprint"]) == 64


def test_calendar_events_fields_integrity():
    """Validates that every calendar event has complete required fields."""
    cal = EconomicCalendarProvider.get_todays_calendar()
    events = cal["events"]
    assert len(events) >= 1
    for ev in events:
        assert "event_name" in ev
        assert "currency" in ev
        assert "impact_level" in ev
        assert "scheduled_time" in ev
        assert "is_xauusd_relevant" in ev
        assert "proximity_bucket" in ev
        assert "potential_effect" in ev
