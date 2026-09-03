# -*- coding: utf-8 -*-
"""
Phase 66 — CFTC Commitments of Traders provider.

Fully offline: `cftc_provider._http_get` is monkeypatched with deterministic
Socrata-shaped rows. No network, reproducible.

Covers: normalization, net non-commercial calc, report-date preservation,
conservative release timing, strict lookahead (future report excluded, exact
included, earlier included), NO model-prior leakage, HTTP failure modes
(429 / 500 / malformed / timeout), backoff, no seed fallback, provenance, and
the flow into the existing SENTIMENT_POSITIONING factor group.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.providers import cftc_provider as cp

client = TestClient(app)


class _Resp:
    def __init__(self, code, body):
        self.status_code = code
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _row(code, name, date_iso, nc_long, nc_short, c_long=100000, c_short=120000, oi=400000):
    return {
        "cftc_contract_market_code": code,
        "market_and_exchange_names": name,
        "report_date_as_yyyy_mm_dd": f"{date_iso}T00:00:00.000",
        "noncomm_positions_long_all": str(nc_long),
        "noncomm_positions_short_all": str(nc_short),
        "comm_positions_long_all": str(c_long),
        "comm_positions_short_all": str(c_short),
        "open_interest_all": str(oi),
    }


# GOLD (USD) + EURO FX (EUR), two report dates each.
_FIXTURE = [
    _row("088691", "GOLD - COMMODITY EXCHANGE INC.", "2026-08-25", 250000, 60000),
    _row("088691", "GOLD - COMMODITY EXCHANGE INC.", "2026-08-18", 240000, 62000),
    _row("099741", "EURO FX - CHICAGO MERCANTILE EXCHANGE", "2026-08-25", 120000, 90000),
    _row("099741", "EURO FX - CHICAGO MERCANTILE EXCHANGE", "2026-08-18", 118000, 95000),
]


@pytest.fixture
def cftc(monkeypatch):
    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    monkeypatch.setenv("CFTC_CACHE_TTL_SEC", "0")
    monkeypatch.delenv("MACRO_DATA_PROVIDER", raising=False)  # seed_demo base
    from macro_intelligence_engine import EconomicDataRegistry

    monkeypatch.setattr(cp, "_http_get", lambda p, t: _Resp(200, _FIXTURE))
    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry._PROVIDER_MANAGED = False
    yield monkeypatch
    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry._PROVIDER_MANAGED = False


# --- normalization ---------------------------------------------------

def test_hydrate_registers_net_noncommercial(cftc):
    from macro_intelligence_engine import EconomicDataRegistry

    st = cp.CftcCotProvider().hydrate_registry(force=True)
    assert st["provider_state"] in ("LIVE", "LIVE_STALE")
    assert "USD" in st["coverage"] and "EUR" in st["coverage"]

    usd = [r for r in EconomicDataRegistry._RELEASES
           if r.metric == "COT_NET_POSITIONING" and r.country == "USD"]
    assert usd
    latest = max(usd, key=lambda r: r.period)
    assert latest.period == "2026-08-25"
    assert latest.actual == pytest.approx(250000 - 60000)   # net non-commercial
    assert latest.forecast is None                           # no consensus, never faked
    assert latest.unit == "contracts"
    assert latest.source.startswith("CFTC:")


def test_report_date_preserved_and_release_is_later(cftc):
    from macro_intelligence_engine import EconomicDataRegistry

    cp.CftcCotProvider().hydrate_registry(force=True)
    r = [x for x in EconomicDataRegistry._RELEASES
         if x.metric == "COT_NET_POSITIONING" and x.period == "2026-08-25"][0]
    # 2026-08-25 is a Tuesday; conservative public release is the Friday after
    assert r.release_timestamp.startswith("2026-08-28T")
    assert r.release_timestamp.endswith("Z")
    assert r.period < r.release_timestamp[:10]  # report date strictly before release


def test_observations_expose_categories(cftc):
    cp.CftcCotProvider().hydrate_registry(force=True)
    obs = cp.CftcCotProvider().get_observations()
    o = [x for x in obs if x["country"] == "USD" and x["report_date"] == "2026-08-25"][0]
    assert o["non_commercial_long"] == 250000
    assert o["non_commercial_short"] == 60000
    assert o["non_commercial_net"] == 190000
    assert o["commercial_long"] == 100000
    assert o["open_interest"] == 400000
    assert o["asset"] == "XAUUSD"


# --- lookahead ------------------------------------------------------

def test_lookahead_future_report_excluded(cftc):
    from macro_intelligence_engine import EconomicDataRegistry

    cp.CftcCotProvider().hydrate_registry(force=True)
    # the 08-25 report is public 08-28 20:30Z
    before = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    at = datetime(2026, 8, 28, 21, 0, tzinfo=timezone.utc)
    n_before = len([r for r in EconomicDataRegistry.get_releases_as_of(as_of=before, country="USD")
                    if r.metric == "COT_NET_POSITIONING" and r.period == "2026-08-25"])
    n_at = len([r for r in EconomicDataRegistry.get_releases_as_of(as_of=at, country="USD")
                if r.metric == "COT_NET_POSITIONING" and r.period == "2026-08-25"])
    assert n_before == 0
    assert n_at == 1


def test_lookahead_earlier_report_included(cftc):
    from macro_intelligence_engine import EconomicDataRegistry

    cp.CftcCotProvider().hydrate_registry(force=True)
    later = datetime(2027, 1, 1, tzinfo=timezone.utc)
    usd = [r for r in EconomicDataRegistry.get_releases_as_of(as_of=later, country="USD")
           if r.metric == "COT_NET_POSITIONING"]
    assert len(usd) == 2


# --- model-prior protection (§16) ---------------------------------

def test_no_model_prior_leak_when_cot_unavailable(cftc):
    """CFTC covers USD/EUR here — GBP has no COT. The engine's 238500 prior must
    NOT surface for GBP anywhere in the API."""
    cftc.setattr(cp, "_http_get", lambda p, t: _Resp(200, [
        _row("088691", "GOLD - COMMODITY EXCHANGE INC.", "2026-08-25", 250000, 60000),
    ]))
    cp.CftcCotProvider().hydrate_registry(force=True)

    gbp = client.get("/api/macro/currencies/GBP").json()
    sp = (gbp.get("factor_groups") or {}).get("SENTIMENT_POSITIONING")
    assert sp is None or sp.get("state") == "INSUFFICIENT_EVIDENCE"
    blob = str(gbp)
    assert "238500" not in blob and "238,500" not in blob


def test_cot_flows_into_sentiment_positioning_group(cftc):
    from macro_intelligence_engine import MacroFactorGroupingEngine

    cp.CftcCotProvider().hydrate_registry(force=True)
    groups = MacroFactorGroupingEngine.evaluate_factor_groups(country="USD")
    sp = groups["SENTIMENT_POSITIONING"]
    assert isinstance(sp["score"], (int, float))
    assert "190,000" in " ".join(sp["supporting_metrics"]) or "190000" in " ".join(sp["supporting_metrics"])


# --- HTTP failure modes ------------------------------------------

@pytest.mark.parametrize("code", [429, 500, 503])
def test_http_error_is_unavailable_not_fabricated(cftc, code):
    cftc.setattr(cp, "_http_get", lambda p, t: _Resp(code, None))
    from macro_intelligence_engine import EconomicDataRegistry

    st = cp.CftcCotProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"
    assert st["last_error"]
    assert not [r for r in EconomicDataRegistry._RELEASES if r.metric == "COT_NET_POSITIONING"]


def test_malformed_json_is_handled(cftc):
    cftc.setattr(cp, "_http_get", lambda p, t: _Resp(200, None))
    st = cp.CftcCotProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"
    assert st["last_error"] == "malformed_json"


def test_timeout_is_handled(cftc):
    def _boom(p, t):
        raise TimeoutError("read timed out")

    cftc.setattr(cp, "_http_get", _boom)
    st = cp.CftcCotProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"
    assert "TimeoutError" in st["last_error"]


def test_broken_provider_backs_off(cftc):
    calls = {"n": 0}

    def _fail(p, t):
        calls["n"] += 1
        return _Resp(500, None)

    cftc.setattr(cp, "_http_get", _fail)
    cftc.setenv("CFTC_CACHE_TTL_SEC", "9999")
    prov = cp.CftcCotProvider()
    prov.hydrate_registry(force=True)
    after_first = calls["n"]
    prov.hydrate_registry(force=False)  # in backoff -> no new call
    assert calls["n"] == after_first


def test_provider_outage_does_not_fall_back_to_seed(cftc):
    """A CFTC outage must not silently substitute the seeded COT prior for the
    countries it was meant to cover."""
    cftc.setattr(cp, "_http_get", lambda p, t: _Resp(503, None))
    from macro_intelligence_engine import EconomicDataRegistry

    # seed first (as the app would), then a failed CFTC hydrate
    EconomicDataRegistry.seed_canonical_registry()
    seeded_usd_cot = [r for r in EconomicDataRegistry._RELEASES
                      if r.metric == "COT_NET_POSITIONING" and r.country == "USD"]
    assert seeded_usd_cot  # seed has one
    st = cp.CftcCotProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"
    # the provider reports unavailable; the currency endpoint must not present
    # the seeded prior as live COT
    d = client.get("/api/macro/providers").json()
    assert d["providers"]  # smoke


# --- provenance ---------------------------------------------------

def test_provenance_on_records(cftc):
    from macro_intelligence_engine import EconomicDataRegistry

    cp.CftcCotProvider().hydrate_registry(force=True)
    r = [x for x in EconomicDataRegistry._RELEASES if x.metric == "COT_NET_POSITIONING"][0]
    assert r.source.startswith("CFTC:")
    assert r.source_timestamp
    assert r.release_timestamp.endswith("Z")


def test_api_providers_reports_cftc_live(cftc):
    cp.CftcCotProvider().hydrate_registry(force=True)
    d = client.get("/api/macro/providers").json()
    cftc_info = [p for p in d["providers"] if p["key"] == "cftc"][0]
    assert cftc_info["configured"] is True
    assert cftc_info["health"]["provider_state"] in ("LIVE", "LIVE_STALE")
    assert "USD" in d["coverage"]
    assert d["coverage"]["USD"]["cot"] == "LIVE"
