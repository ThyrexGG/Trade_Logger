# -*- coding: utf-8 -*-
"""
Stage 18G — economic-calendar provider (ForexFactory / FMP).

Offline (no network). Verifies:
  * normalization: real impact / currency / forecast / time from a raw feed row
  * the provider caches, persists a last-good snapshot, and degrades cleanly on
    a rate-limit / unreachable feed
  * macro_service.get_events merges the calendar into the FRED observation rows
  * FRED-sourced rows now get a currency and an impact rating (presentation fix)
  * no execution / broker / risk import
"""
from datetime import date, datetime, timedelta, timezone

import pytest

import api.providers.calendar_provider as cal
from api.macro_provider import classify_impact, normalize_event


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("MACRO_CALENDAR_PROVIDER", raising=False)
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    # hermetic: no cross-test bleed through the persisted last-good snapshot
    import historical_data_store as store
    monkeypatch.setattr(store, "load_artifact", lambda *a, **k: None)
    monkeypatch.setattr(store, "save_artifact", lambda *a, **k: "noop")
    cal.reset_state_for_tests()
    yield
    cal.reset_state_for_tests()


def _sample_rows():
    base = datetime.now(timezone.utc).replace(minute=30, second=0, microsecond=0)
    return [
        {"title": "Core CPI m/m", "country": "USD", "impact": "High",
         "date": (base + timedelta(days=1)).isoformat(), "forecast": "0.3%", "previous": "0.2%"},
        {"title": "Non-Farm Employment Change", "country": "USD", "impact": "High",
         "date": (base + timedelta(days=2)).isoformat(), "forecast": "175K", "previous": "142K"},
        {"title": "GDP m/m", "country": "GBP", "impact": "Medium",
         "date": (base + timedelta(days=3)).isoformat(), "forecast": "0.1%", "previous": "0.4%"},
        {"title": "Bank Holiday", "country": "EUR", "impact": "Holiday",
         "date": (base + timedelta(days=4)).isoformat(), "forecast": "", "previous": ""},
    ]


def test_normalization_carries_impact_currency_forecast_time():
    ev = cal._event(source="ForexFactory", provider="forexfactory", ccy="USD",
                    title="Core CPI m/m", when=_sample_rows()[0]["date"],
                    impact="High", actual=None, forecast="0.3%", previous="0.2%")
    assert ev["currency"] == "USD"
    assert ev["impact"] == "HIGH"
    assert ev["indicator"] == "CORE_CPI"
    assert ev["forecast"] == pytest.approx(0.3)
    assert ev["previous"] == pytest.approx(0.2)
    assert ev["status"] == "SCHEDULED"
    assert ev["timestamp"].endswith("+00:00")


def test_number_parser_handles_suffixes_and_signs():
    assert cal._num("175K") == pytest.approx(175000)
    assert cal._num("-0.1%") == pytest.approx(-0.1)
    assert cal._num("1.2M") == pytest.approx(1_200_000)
    assert cal._num("Tentative") is None
    assert cal._num("") is None


def test_provider_serves_and_snapshots(monkeypatch):
    p = cal.get_calendar_provider()
    rows = _sample_rows()
    p._fetch_raw = lambda: ([cal._event(
        source="ForexFactory", provider="forexfactory", ccy=r["country"],
        title=r["title"], when=r["date"], impact=r["impact"],
        actual=None, forecast=r["forecast"], previous=r["previous"]) for r in rows
        if cal._event(source="x", provider="forexfactory", ccy=r["country"], title=r["title"],
                      when=r["date"], impact=r["impact"], actual=None,
                      forecast=r["forecast"], previous=r["previous"])], {})
    evs = p.get_events(date.today(), date.today() + timedelta(days=10))
    assert len(evs) >= 3
    assert {e["impact"] for e in evs} & {"HIGH", "MEDIUM"}
    st = p.status()
    assert st["provider_state"] == "LIVE"
    assert st["events_cached"] >= 3


def test_rate_limited_feed_degrades_without_raising():
    p = cal.get_calendar_provider()
    p._fetch_raw = lambda: ([], {"thisweek": "http_429"})
    assert p.get_events(date.today(), date.today() + timedelta(days=7)) == []
    st = p.status()
    assert st["provider_state"] in ("PROVIDER_UNAVAILABLE", "PENDING")
    assert "429" in str(st["fetch_errors"])


def test_service_merges_calendar_into_events(monkeypatch):
    import api.macro_service as ms

    monkeypatch.setenv("MACRO_CALENDAR_ENABLED", "1")   # opt in to the calendar layer under pytest
    monkeypatch.setattr(cal, "calendar_provider_key", lambda: "forexfactory")
    fake = cal.get_calendar_provider()
    upcoming = cal._event(source="ForexFactory", provider="forexfactory", ccy="USD",
                          title="Non-Farm Employment Change",
                          when=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                          impact="High", actual=None, forecast="175K", previous="142K")
    monkeypatch.setattr(fake, "_fetch_raw", lambda: ([upcoming], {}))
    monkeypatch.setattr(cal, "get_calendar_provider", lambda: fake)

    r = ms.get_events(window="upcoming", limit=25)
    titles = [e["event"] for e in r["events"]]
    assert "Non-Farm Employment Change" in titles
    assert r["available"] is True


def test_fred_rows_get_currency_and_impact():
    raw = {
        "name": "NFP", "metric": "NFP", "country": "USD",
        "release_timestamp": "2026-09-04T13:30:00Z",
        "actual": 214.0, "previous": -156.0, "unit": "k jobs (MoM chg)",
        "source": "FRED:PAYEMS", "family": "LABOR",
    }
    ev = normalize_event(raw, provider="fred", is_live=True)
    assert ev["currency"] == "USD"
    assert ev["impact"] == "HIGH"      # was always LOW before the fix


def test_classify_impact_table():
    assert classify_impact("CPI", None) == "HIGH"
    assert classify_impact("RETAIL_SALES", None) == "MEDIUM"
    assert classify_impact("YIELD_10Y", None) == "LOW"
    assert classify_impact(None, "FOMC Statement") == "HIGH"


def test_calendar_provider_no_execution_imports():
    import inspect
    # ignore the module docstring / comments — check real import statements only
    src = inspect.getsource(cal)
    code_lines = [ln for ln in src.splitlines()
                  if ln.strip().startswith(("import ", "from "))]
    joined = "\n".join(code_lines)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway",
                "order_execution", "reconciliation"):
        assert bad not in joined
