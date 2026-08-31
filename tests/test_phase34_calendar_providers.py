"""
Phase 34 — Calendar Provider Abstraction & Source Transparency Test Suite
Validates provider polymorphism, source selection, Forex Factory fallback honesty,
and cryptographic dataset fingerprinting.
"""

import pytest
from xauusd_daily_preflight import (
    BaseCalendarProvider,
    ForexFactoryProvider,
    StandardMacroCalendarProvider,
    FallbackCalendarProvider,
    EconomicCalendarProviderFactory,
)


def test_calendar_provider_polymorphism():
    """Validates that all calendar providers implement BaseCalendarProvider interface."""
    providers = [ForexFactoryProvider(), StandardMacroCalendarProvider(), FallbackCalendarProvider()]
    for p in providers:
        assert isinstance(p, BaseCalendarProvider)
        assert isinstance(p.source_name, str)
        assert isinstance(p.provider_status, str)
        cal = p.get_calendar()
        assert isinstance(cal, dict)
        assert "source_name" in cal
        assert "events" in cal
        assert "dataset_fingerprint" in cal
        assert len(cal["dataset_fingerprint"]) == 64


def test_forex_factory_provider_honesty():
    """Validates that ForexFactoryProvider reports UNAVAILABLE and activates fallback rather than fabricating data."""
    ff = ForexFactoryProvider()
    assert ff.source_name == "FOREX_FACTORY"
    assert "UNAVAILABLE" in ff.provider_status
    cal = ff.get_calendar()
    assert "forex_factory_live_status" in cal
    assert "UNAVAILABLE" in cal["forex_factory_live_status"]


def test_economic_calendar_factory_selection():
    """Validates factory provider instantiation based on preference."""
    std = EconomicCalendarProviderFactory.get_provider("AUTO")
    assert isinstance(std, StandardMacroCalendarProvider)

    ff = EconomicCalendarProviderFactory.get_provider("FOREX_FACTORY")
    assert isinstance(ff, ForexFactoryProvider)

    fb = EconomicCalendarProviderFactory.get_provider("FALLBACK")
    assert isinstance(fb, FallbackCalendarProvider)
