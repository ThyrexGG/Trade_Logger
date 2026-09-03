# -*- coding: utf-8 -*-
"""
Phase 66 — consensus-forecast contract + merge onto releases.

Offline. The default `NullForecastProvider` supplies nothing (there is no free
authoritative consensus feed); these tests use an in-test fake provider to
exercise the canonical model, the identity-based merge, vintage/lookahead
filtering, and surprise restoration.
"""
from datetime import datetime, timezone

import pytest

from api.macro_evidence import merge_forecasts
from api.providers.forecast_provider import (
    EconomicForecast,
    NullForecastProvider,
    forecast_lookahead_ok,
    get_forecast_provider,
)


@pytest.fixture
def clean_registry():
    from macro_intelligence_engine import EconomicDataRegistry, MacroReleaseRecord

    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = True
    EconomicDataRegistry._PROVIDER_MANAGED = False
    EconomicDataRegistry.register_release(MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-08",
        release_timestamp="2026-09-11T12:30:00Z",
        forecast=None, actual=3.4, previous=3.3, unit="%",
        source="FRED:CPIAUCSL", source_timestamp="2026-09-11T12:30:00Z",
    ))
    yield EconomicDataRegistry
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False


def _fc(**kw):
    base = dict(provider="forecast", source="TestConsensus", indicator="CPI",
               country="USD", period="2026-08", forecast=3.1, previous=3.3, unit="%")
    base.update(kw)
    return EconomicForecast(**base)


# --- default provider -------------------------------------------------

def test_null_forecast_provider_supplies_nothing(monkeypatch):
    monkeypatch.delenv("MACRO_FORECAST_PROVIDER", raising=False)
    p = get_forecast_provider()
    assert isinstance(p, NullForecastProvider)
    assert p.configured is False
    assert p.get_forecasts() == []
    assert p.status()["provider_state"] == "NOT_CONFIGURED"


# --- canonical model -------------------------------------------------

def test_forecast_identity_is_country_metric_period():
    assert _fc().identity() == ("USD", "CPI", "2026-08")


def test_forecast_never_manufactured():
    fc = _fc(forecast=None)
    assert fc.forecast is None  # None stays None — merge drops it


# --- merge by identity --------------------------------------------

def test_merge_attaches_forecast_to_matching_release(clean_registry):
    res = merge_forecasts([_fc()])
    assert res["merged"] == 1
    rec = clean_registry._RELEASES[0]
    assert rec.forecast == 3.1


def test_merge_rejects_wrong_period(clean_registry):
    res = merge_forecasts([_fc(period="2026-07")])
    assert res["merged"] == 0
    assert res["unmatched"] == 1
    assert clean_registry._RELEASES[0].forecast is None


def test_merge_rejects_wrong_country(clean_registry):
    res = merge_forecasts([_fc(country="EUR")])
    assert res["merged"] == 0
    assert clean_registry._RELEASES[0].forecast is None


def test_merge_rejects_wrong_indicator(clean_registry):
    res = merge_forecasts([_fc(indicator="CORE_CPI")])
    assert res["merged"] == 0
    assert clean_registry._RELEASES[0].forecast is None


def test_merge_never_creates_a_release(clean_registry):
    before = len(clean_registry._RELEASES)
    merge_forecasts([_fc(period="2099-01")])
    assert len(clean_registry._RELEASES) == before


# --- vintage / lookahead ----------------------------------------

def test_forecast_with_no_vintage_only_valid_in_now_context():
    fc = _fc(forecast_timestamp=None)
    assert forecast_lookahead_ok(fc, as_of=None) is True
    assert forecast_lookahead_ok(fc, as_of=datetime(2026, 9, 1, tzinfo=timezone.utc)) is False


def test_forecast_vintage_excluded_when_future():
    fc = _fc(forecast_timestamp="2026-09-05T00:00:00Z")
    as_of = datetime(2026, 9, 3, tzinfo=timezone.utc)
    assert forecast_lookahead_ok(fc, as_of) is False


def test_forecast_vintage_included_when_past():
    fc = _fc(forecast_timestamp="2026-09-01T00:00:00Z")
    as_of = datetime(2026, 9, 3, tzinfo=timezone.utc)
    assert forecast_lookahead_ok(fc, as_of) is True


def test_merge_respects_forecast_vintage(clean_registry):
    future_vintage = _fc(forecast_timestamp="2026-09-10T00:00:00Z")
    res = merge_forecasts([future_vintage], as_of=datetime(2026, 9, 3, tzinfo=timezone.utc))
    assert res["merged"] == 0
    assert clean_registry._RELEASES[0].forecast is None


# --- surprise restoration --------------------------------------

@pytest.mark.parametrize("forecast,expect_state", [
    (2.9, "POSITIVE"),   # actual 3.4 > forecast -> upside inflation surprise
    (3.9, "NEGATIVE"),   # actual 3.4 < forecast
    (3.4, "INLINE"),     # actual == forecast
])
def test_surprise_restored_once_forecast_present(clean_registry, forecast, expect_state):
    from macro_intelligence_engine import EconomicSurpriseEngine

    merge_forecasts([_fc(forecast=forecast)])
    s = EconomicSurpriseEngine.evaluate_release_surprise(clean_registry._RELEASES[0])
    assert s["surprise_state"] != "UNAVAILABLE"
    if expect_state == "INLINE":
        assert s["surprise_state"] == "INLINE"
    else:
        assert expect_state in s["surprise_state"]


def test_surprise_unavailable_without_forecast(clean_registry):
    from macro_intelligence_engine import EconomicSurpriseEngine

    s = EconomicSurpriseEngine.evaluate_release_surprise(clean_registry._RELEASES[0])
    assert s["surprise_state"] == "UNAVAILABLE"
    assert s["actual"] == 3.4  # real value preserved, not zeroed
