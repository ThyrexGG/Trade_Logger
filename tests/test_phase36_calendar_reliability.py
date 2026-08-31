"""
Phase 36 — Calendar Reliability & Provider Classification Test Suite
Validates EconomicEventSchema, source classification honesty (LIVE SECONDARY, FALLBACK, UNAVAILABLE),
and provider health diagnostics.
"""

import pytest
from xauusd_news_reliability import (
    EconomicEventSchema,
    CalendarSourceClassifier,
)
from xauusd_daily_preflight import (
    ForexFactoryProvider,
    StandardMacroCalendarProvider,
    FallbackCalendarProvider,
)


def test_economic_event_schema_instantiation():
    """Validates complete structured economic event schema with data fingerprint."""
    ev = EconomicEventSchema(
        event_id="EV_US_CPI_20260831",
        event_name="US Core CPI (YoY)",
        currency="USD",
        country="United States",
        impact="HIGH",
        scheduled_timestamp="2026-08-31T12:30:00Z",
        actual="3.2%",
        forecast="3.1%",
        previous="3.3%",
        source="STANDARD_MACRO_FEED",
        first_seen_timestamp="2026-08-31T00:00:00Z",
        last_updated_timestamp="2026-08-31T12:30:05Z",
        availability_status="RELEASED",
        data_fingerprint="abc123def456",
    )
    d = ev.to_dict()
    assert d["event_id"] == "EV_US_CPI_20260831"
    assert d["impact"] == "HIGH"
    assert d["actual"] == "3.2%"
    assert d["data_fingerprint"] == "abc123def456"


def test_calendar_source_classifier_honesty():
    """Validates that ForexFactoryProvider is truthfully classified as fallback/unavailable when unauthenticated."""
    ff_provider = ForexFactoryProvider()
    class_ff = CalendarSourceClassifier.classify_source_status(ff_provider)
    assert class_ff["classification"] == "FALLBACK SOURCE"
    assert "UNAVAILABLE" in class_ff["forex_factory_live_feed"]
    assert "Direct authenticated Forex Factory" in class_ff["reason_for_state"]

    std_provider = StandardMacroCalendarProvider()
    class_std = CalendarSourceClassifier.classify_source_status(std_provider)
    assert class_std["classification"] == "LIVE SECONDARY SOURCE"
    assert class_std["forex_factory_live_feed"] == "UNAVAILABLE"
