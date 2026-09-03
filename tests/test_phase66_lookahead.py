# -*- coding: utf-8 -*-
"""
Phase 66 — lookahead integrity across all evidence sources.

The four explicit cases from the phase spec:
  * future release excluded
  * exact release included
  * forecast vintage excluded when future
  * COT future report excluded
plus: retrieved-after-but-released-before is valid.
"""
from datetime import datetime, timezone

import pytest

from api.macro_evidence import merge_forecasts
from api.providers.forecast_provider import EconomicForecast, forecast_lookahead_ok


@pytest.fixture
def reg():
    from macro_intelligence_engine import EconomicDataRegistry, MacroReleaseRecord

    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = True
    EconomicDataRegistry._PROVIDER_MANAGED = False
    # a release that becomes public 2026-09-11
    EconomicDataRegistry.register_release(MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-08",
        release_timestamp="2026-09-11T12:30:00Z",
        forecast=None, actual=3.4, previous=3.3, unit="%",
        source="FRED:CPIAUCSL", source_timestamp="2026-10-01T00:00:00Z",  # retrieved later
    ))
    yield EconomicDataRegistry
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False


def test_future_release_excluded(reg):
    before = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert reg.get_releases_as_of(as_of=before, country="USD", metric="CPI") == []


def test_exact_release_included(reg):
    at = datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
    assert len(reg.get_releases_as_of(as_of=at, country="USD", metric="CPI")) == 1


def test_retrieved_after_but_released_before_is_valid(reg):
    """source_timestamp (retrieval) is 2026-10-01 but release_timestamp is
    2026-09-11 — a query as-of 2026-09-15 must still see it."""
    at = datetime(2026, 9, 15, tzinfo=timezone.utc)
    assert len(reg.get_releases_as_of(as_of=at, country="USD", metric="CPI")) == 1


def test_forecast_vintage_excluded_when_future(reg):
    fc = EconomicForecast(provider="forecast", source="X", indicator="CPI",
                          country="USD", period="2026-08", forecast=3.1,
                          forecast_timestamp="2026-09-09T00:00:00Z")
    # as-of before the forecast was published
    as_of = datetime(2026, 9, 8, tzinfo=timezone.utc)
    assert forecast_lookahead_ok(fc, as_of) is False
    res = merge_forecasts([fc], as_of=as_of)
    assert res["merged"] == 0
    assert reg._RELEASES[0].forecast is None


def test_forecast_vintage_included_when_known(reg):
    fc = EconomicForecast(provider="forecast", source="X", indicator="CPI",
                          country="USD", period="2026-08", forecast=3.1,
                          forecast_timestamp="2026-09-05T00:00:00Z")
    as_of = datetime(2026, 9, 10, tzinfo=timezone.utc)
    res = merge_forecasts([fc], as_of=as_of)
    assert res["merged"] == 1
    assert reg._RELEASES[0].forecast == 3.1


def test_cot_future_report_excluded(monkeypatch):
    from api.providers import cftc_provider as cp
    from macro_intelligence_engine import EconomicDataRegistry

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return [{
                "cftc_contract_market_code": "088691",
                "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
                "report_date_as_yyyy_mm_dd": "2026-08-25T00:00:00.000",
                "noncomm_positions_long_all": "250000",
                "noncomm_positions_short_all": "60000",
                "comm_positions_long_all": "1", "comm_positions_short_all": "1",
                "open_interest_all": "1",
            }]

    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    monkeypatch.setenv("CFTC_CACHE_TTL_SEC", "0")
    monkeypatch.setattr(cp, "_http_get", lambda p, t: _Resp())
    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry._PROVIDER_MANAGED = False

    cp.CftcCotProvider().hydrate_registry(force=True)
    # report 2026-08-25 (Tue) is public 2026-08-28 20:30Z
    early = datetime(2026, 8, 27, tzinfo=timezone.utc)
    assert reg_cot(EconomicDataRegistry, early) == 0
    late = datetime(2026, 8, 29, tzinfo=timezone.utc)
    assert reg_cot(EconomicDataRegistry, late) == 1

    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry._PROVIDER_MANAGED = False


def reg_cot(registry, as_of):
    return len([r for r in registry.get_releases_as_of(as_of=as_of, country="USD")
                if r.metric == "COT_NET_POSITIONING"])
