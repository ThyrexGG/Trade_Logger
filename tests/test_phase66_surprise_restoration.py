# -*- coding: utf-8 -*-
"""
Phase 66 — surprise restoration + family-specific interpretation (§10 / §11).

Once a real consensus forecast is merged, ``surprise = actual - forecast`` is
available again, and its *meaning* stays family-specific: an inflation beat is
hawkish, a labor miss (higher unemployment / claims) is dovish — never one
universal "positive = bullish" rule.
"""
import pytest

from api.macro_evidence import merge_forecasts
from api.providers.forecast_provider import EconomicForecast


@pytest.fixture
def reg():
    from macro_intelligence_engine import EconomicDataRegistry

    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = True
    EconomicDataRegistry._PROVIDER_MANAGED = False
    yield EconomicDataRegistry
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False


def _add(reg, metric, actual, previous="0"):
    from macro_intelligence_engine import MacroReleaseRecord

    reg.register_release(MacroReleaseRecord(
        metric=metric, country="USD", period="2026-08",
        release_timestamp="2026-09-01T12:30:00Z", forecast=None, actual=actual,
        previous=float(previous), unit="%", source="FRED",
        source_timestamp="2026-09-01T12:30:00Z",
    ))
    return reg._RELEASES[-1]


def test_inflation_beat_is_hawkish(reg):
    _add(reg, "CPI", 3.4, "3.2")
    merge_forecasts([EconomicForecast(provider="forecast", source="X", indicator="CPI",
                                      country="USD", period="2026-08", forecast=3.0)])
    from macro_intelligence_engine import EconomicSurpriseEngine

    s = EconomicSurpriseEngine.evaluate_release_surprise(reg._RELEASES[0])
    assert "HAWKISH" in s["direction"]
    assert s["raw_surprise"] == pytest.approx(0.4)


def test_labor_miss_higher_unemployment_is_dovish_softening(reg):
    _add(reg, "UNEMPLOYMENT", 4.5, "4.2")
    merge_forecasts([EconomicForecast(provider="forecast", source="X", indicator="UNEMPLOYMENT",
                                      country="USD", period="2026-08", forecast=4.2)])
    from macro_intelligence_engine import EconomicSurpriseEngine

    s = EconomicSurpriseEngine.evaluate_release_surprise(reg._RELEASES[0])
    # higher unemployment than forecast -> softening / dovish, NOT "positive"
    assert "SOFTENING" in s["direction"] or "BEARISH LABOR" in s["direction"]


def test_growth_beat_is_expansionary(reg):
    _add(reg, "GDP", 3.5, "2.5")
    merge_forecasts([EconomicForecast(provider="forecast", source="X", indicator="GDP",
                                      country="USD", period="2026-08", forecast=2.8)])
    from macro_intelligence_engine import EconomicSurpriseEngine

    s = EconomicSurpriseEngine.evaluate_release_surprise(reg._RELEASES[0])
    assert "EXPANSION" in s["direction"] or "BULLISH GROWTH" in s["direction"]


def test_actual_missing_keeps_surprise_unavailable(reg):
    from macro_intelligence_engine import EconomicSurpriseEngine, MacroReleaseRecord

    reg.register_release(MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-09",
        release_timestamp="2026-10-01T12:30:00Z", forecast=3.1, actual=None,
        previous=3.4, unit="%", source="forecast", source_timestamp="2026-09-20T00:00:00Z",
    ))
    merge_forecasts([EconomicForecast(provider="forecast", source="X", indicator="CPI",
                                      country="USD", period="2026-09", forecast=3.0)])
    s = EconomicSurpriseEngine.evaluate_release_surprise(reg._RELEASES[-1])
    assert s["surprise_state"] == "UNAVAILABLE"
