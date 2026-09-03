# -*- coding: utf-8 -*-
"""
Phase 65 — FRED macro data provider tests.

Fully offline: `fred_provider._http_get` is monkeypatched with deterministic
fake ALFRED responses. No real API key, no network, reproducible.

Covers: normalization (country / indicator / timestamp / units / numeric),
partial coverage, HTTP failure modes (429 / 404 / 500 / timeout / malformed),
missing forecast (FRED has none — never fabricated), duplicate/vintage
collapsing, revision handling, strict lookahead (future excluded, exact
included, observation-period-past-but-release-future excluded), provenance,
flow into the existing scoring engine, the preserved seed_demo default, and
safety (no execution side effect / import).
"""
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.providers import fred_provider as fp

client = TestClient(app)


class _Resp:
    def __init__(self, code, body):
        self.status_code = code
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _obs(rows):
    return {"observations": [{"date": d, "realtime_start": rt, "value": v} for d, rt, v in rows]}


# A realistic ALFRED fixture: monthly CPI, one revised print, plus unemployment.
_FIXTURE = {
    "CPIAUCSL": _obs([
        ("2026-04-01", "2026-05-13", "3.1"),
        ("2026-05-01", "2026-06-11", "3.2"),
        ("2026-06-01", "2026-07-11", "3.3"),
        ("2026-06-01", "2026-08-20", "3.4"),   # <- revision of June
        ("2026-07-01", "2026-08-12", "3.5"),
    ]),
    "UNRATE": _obs([
        ("2026-06-01", "2026-07-05", "4.0"),
        ("2026-07-01", "2026-08-02", "4.1"),
    ]),
}


@pytest.fixture
def fred(monkeypatch):
    """Force the FRED provider with a mocked HTTP layer + clean registry."""
    monkeypatch.setenv("MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setenv("FRED_API_KEY", "x" * 32)
    monkeypatch.setenv("FRED_CACHE_TTL_SEC", "0")  # always re-hydrate in tests
    from macro_intelligence_engine import EconomicDataRegistry

    def _default_get(params, timeout):
        return _Resp(200, _FIXTURE.get(params["series_id"], {"observations": []}))

    monkeypatch.setattr(fp, "_http_get", _default_get)
    fp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    yield monkeypatch
    fp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False


# --- normalization -----------------------------------------------------

def test_hydrate_registers_normalized_records(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    st = fp.FredMacroProvider().hydrate_registry(force=True)
    assert st["provider_state"] in ("LIVE", "LIVE_STALE")
    assert st["records_registered"] > 0
    assert "USD" in st["coverage"]

    recs = EconomicDataRegistry._RELEASES
    cpi = [r for r in recs if r.metric == "CPI" and r.country == "USD"]
    assert cpi
    r = cpi[-1]
    assert r.country == "USD"
    assert r.unit == "%"
    assert r.source.startswith("FRED:CPIAUCSL")
    assert r.source_timestamp  # retrieved_at
    assert r.period.count("-") == 1  # observation period, YYYY-MM


def test_forecast_is_never_fabricated(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    for r in EconomicDataRegistry._RELEASES:
        assert r.forecast is None  # FRED has no consensus — must stay None


def test_numeric_parsing_skips_missing_values(fred):
    fred.setattr(fp, "_http_get", lambda p, t: _Resp(200, _obs([
        ("2026-06-01", "2026-07-11", "."),      # FRED "missing"
        ("2026-07-01", "2026-08-11", "3.5"),
        ("2026-08-01", "2026-09-11", ""),
    ])) if p["series_id"] == "CPIAUCSL" else _Resp(200, {"observations": []}))
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    cpi = [r for r in EconomicDataRegistry._RELEASES if r.metric == "CPI"]
    assert [r.actual for r in cpi] == [3.5]  # only the valid row survived


def test_country_and_indicator_mapping(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    pairs = {(r.country, r.metric) for r in EconomicDataRegistry._RELEASES}
    assert ("USD", "CPI") in pairs
    assert ("USD", "UNEMPLOYMENT") in pairs
    # nothing mapped to a bogus country
    assert all(c in ("USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF") for c, _ in pairs)


# --- vintages / revisions -------------------------------------------

def test_revision_preserves_initial_value(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    june = [r for r in EconomicDataRegistry._RELEASES if r.metric == "CPI" and r.period == "2026-06"]
    assert june
    r = june[0]
    assert r.revision_status == "REVISED"
    assert r.initial_actual == 3.3   # first print
    assert r.actual == 3.4           # latest vintage
    assert r.revision_delta == pytest.approx(0.1)
    assert r.revision_timestamp is not None


def test_duplicate_periods_collapse_to_one_record(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    june = [r for r in EconomicDataRegistry._RELEASES if r.metric == "CPI" and r.period == "2026-06"]
    assert len(june) == 1  # 2 vintages -> 1 canonical record


# --- lookahead --------------------------------------------------------

def test_lookahead_future_release_excluded(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    # July CPI "released" 2026-08-12
    before = datetime(2026, 8, 11, tzinfo=timezone.utc)
    at = datetime(2026, 8, 12, 13, 30, tzinfo=timezone.utc)
    n_before = len([r for r in EconomicDataRegistry.get_releases_as_of(as_of=before, country="USD")
                    if r.metric == "CPI" and r.period == "2026-07"])
    n_at = len([r for r in EconomicDataRegistry.get_releases_as_of(as_of=at, country="USD")
                if r.metric == "CPI" and r.period == "2026-07"])
    assert n_before == 0
    assert n_at == 1


def test_lookahead_observation_period_past_but_release_future_excluded(fred):
    """The classic trap: an August value released in September must NOT be
    visible in early September just because its observation period is 'August'."""
    from macro_intelligence_engine import EconomicDataRegistry

    fred.setattr(fp, "_http_get", lambda p, t: _Resp(200, _obs([
        ("2026-08-01", "2026-09-15", "9.9"),   # August data, released mid-September
    ])) if p["series_id"] == "CPIAUCSL" else _Resp(200, {"observations": []}))
    fp.FredMacroProvider().hydrate_registry(force=True)

    early_sept = datetime(2026, 9, 3, tzinfo=timezone.utc)
    visible = [r for r in EconomicDataRegistry.get_releases_as_of(as_of=early_sept, country="USD")
              if r.metric == "CPI"]
    assert visible == []  # observation period is August, but it wasn't public yet


def test_lookahead_earlier_release_included(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    way_later = datetime(2027, 1, 1, tzinfo=timezone.utc)
    cpi = [r for r in EconomicDataRegistry.get_releases_as_of(as_of=way_later, country="USD")
           if r.metric == "CPI"]
    assert len(cpi) >= 2  # all historical prints visible


# --- HTTP failure modes ------------------------------------------

@pytest.mark.parametrize("code", [429, 500, 503, 404])
def test_http_error_does_not_crash_or_fabricate(fred, code):
    fred.setattr(fp, "_http_get", lambda p, t: _Resp(code, None))
    from macro_intelligence_engine import EconomicDataRegistry

    st = fp.FredMacroProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"
    assert st["records_registered"] == 0
    assert st["last_error"]
    assert EconomicDataRegistry._RELEASES == []  # nothing fabricated


def test_timeout_is_handled(fred):
    def _boom(p, t):
        raise TimeoutError("read timed out")

    fred.setattr(fp, "_http_get", _boom)
    st = fp.FredMacroProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"
    assert any("TimeoutError" in v for v in st["series_errors"].values())


def test_broken_provider_backs_off(fred):
    """After a failed hydrate the provider must not re-hammer the API on the
    next request — it returns instantly from backoff until the window expires."""
    calls = {"n": 0}

    def _fail(p, t):
        calls["n"] += 1
        return _Resp(500, None)

    fred.setattr(fp, "_http_get", _fail)
    fred.setenv("FRED_CACHE_TTL_SEC", "9999")  # so a non-forced call isn't a TTL no-op

    p = fp.FredMacroProvider()
    p.hydrate_registry(force=True)
    after_first = calls["n"]
    assert after_first > 0

    # a normal (non-forced) request while in backoff -> zero new HTTP calls
    st = p.hydrate_registry(force=False)
    assert calls["n"] == after_first
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"


def test_hydrate_respects_wall_clock_budget(fred):
    """A provider that responds very slowly must not block past the budget."""
    import time as _t

    fred.setenv("FRED_HYDRATE_BUDGET_SEC", "2")
    fred.setenv("FRED_TIMEOUT_SEC", "1")

    def _slow(p, t):
        _t.sleep(0.4)
        return _Resp(200, {"observations": []})

    fred.setattr(fp, "_http_get", _slow)
    t0 = _t.perf_counter()
    fp.FredMacroProvider().hydrate_registry(force=True)
    elapsed = _t.perf_counter() - t0
    assert elapsed < 12  # 8 parallel workers + 2s budget, never the 30-series serial sum


def test_malformed_json_is_handled(fred):
    fred.setattr(fp, "_http_get", lambda p, t: _Resp(200, None))
    st = fp.FredMacroProvider().hydrate_registry(force=True)
    assert st["provider_state"] == "PROVIDER_UNAVAILABLE"


def test_partial_coverage_is_honest(fred):
    def _get(p, t):
        if p["series_id"] == "CPIAUCSL":
            return _Resp(200, _FIXTURE["CPIAUCSL"])
        return _Resp(404, None)

    fred.setattr(fp, "_http_get", _get)
    from macro_intelligence_engine import EconomicDataRegistry

    st = fp.FredMacroProvider().hydrate_registry(force=True)
    assert st["provider_state"] in ("LIVE", "LIVE_STALE")
    metrics = {r.metric for r in EconomicDataRegistry._RELEASES}
    assert metrics == {"CPI"}  # only what actually came back
    assert st["series_errors"]  # the 404s are recorded, not hidden


# --- provenance ------------------------------------------------------

def test_provenance_on_records(fred):
    from macro_intelligence_engine import EconomicDataRegistry

    fp.FredMacroProvider().hydrate_registry(force=True)
    r = EconomicDataRegistry._RELEASES[0]
    assert r.source.startswith("FRED:")          # source_identifier
    assert r.source_timestamp                     # retrieved_at
    assert r.release_timestamp.endswith("Z")      # release timestamp, UTC
    assert r.period                               # observation period


def test_api_meta_reports_live_when_hydrated(fred):
    r = client.get("/api/macro/overview")
    assert r.status_code == 200
    d = r.json()
    assert d["data_provider"] == "fred"
    assert d["provider_is_live"] is True
    assert d["provenance"] == "live"
    assert d.get("provider_state") in ("LIVE", "LIVE_STALE")


def test_api_meta_reports_unavailable_on_provider_failure(fred):
    fred.setattr(fp, "_http_get", lambda p, t: _Resp(500, None))
    d = client.get("/api/macro/overview").json()
    assert d["provider_is_live"] is True
    assert d["provenance"] == "unavailable"
    assert d["provider_state"] == "PROVIDER_UNAVAILABLE"


def test_provider_outage_does_not_fall_back_to_seed_data(fred):
    """§20 / §23: a FRED outage must surface as PROVIDER_UNAVAILABLE — the
    seeded demo dataset must NOT be shown silently in its place."""
    fred.setattr(fp, "_http_get", lambda p, t: _Resp(503, None))

    sc = client.get("/api/macro/scorecard/USD").json()
    assert sc["available"] is False
    assert sc["state"] == "PROVIDER_UNAVAILABLE"
    assert sc["composite_score"] is None
    assert sc["categories"] == []

    hm = client.get("/api/macro/heatmap/USD").json()
    assert hm["available"] is False
    assert hm["state"] == "PROVIDER_UNAVAILABLE"
    assert hm["indicators"] == []

    # and the underlying registry is empty, not seeded
    from macro_intelligence_engine import EconomicDataRegistry
    assert EconomicDataRegistry._PROVIDER_MANAGED is True
    assert EconomicDataRegistry._RELEASES == []


# --- scoring flow --------------------------------------------------

def test_real_records_flow_into_scoring_engine(fred):
    from macro_intelligence_engine import MacroFactorGroupingEngine

    fp.FredMacroProvider().hydrate_registry(force=True)
    groups = MacroFactorGroupingEngine.evaluate_factor_groups(country="USD")
    assert "INFLATION" in groups
    assert isinstance(groups["INFLATION"]["score"], (int, float))
    # the scorecard consumes it without error
    from api import macro_scorecard
    sc = macro_scorecard.get_scorecard("USD")
    assert sc["available"] is True
    assert sc["provenance"] == "live"


def test_incomplete_data_surprise_has_full_key_set():
    """Phase 65 fix: a release with a real actual but no forecast (FRED) must
    return the same key set as a scored surprise so downstream consumers
    (MacroFactorGroupingEngine) never KeyError."""
    from macro_intelligence_engine import EconomicSurpriseEngine, MacroReleaseRecord

    rec = MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-07",
        release_timestamp="2026-08-12T13:30:00Z",
        forecast=None, actual=3.4, previous=3.3, unit="%",
        source="FRED:CPIAUCSL", source_timestamp="2026-08-12T13:30:00Z",
    )
    scored = EconomicSurpriseEngine.evaluate_release_surprise(rec)
    for k in ("z_score", "display_name", "unit", "family", "normalized_surprise",
              "surprise_state", "direction", "raw_surprise"):
        assert k in scored
    assert scored["z_score"] == 0.0
    assert scored["surprise_state"] == "UNAVAILABLE"
    assert scored["actual"] == 3.4  # the real value is preserved, not zeroed


# --- default preserved ------------------------------------------

def test_seed_demo_default_is_unchanged(monkeypatch):
    monkeypatch.delenv("MACRO_DATA_PROVIDER", raising=False)
    d = client.get("/api/macro/scorecard/USD").json()
    assert d["provenance"] == "seed_demo"
    assert d["provider_state"] == "SEED_DEMO"
    assert client.get("/api/macro/scorecard/CAD").json()["state"] == "INSUFFICIENT_EVIDENCE"


def test_provider_none_is_unavailable(monkeypatch):
    monkeypatch.setenv("MACRO_DATA_PROVIDER", "none")
    d = client.get("/api/macro/overview").json()
    assert d["provenance"] == "unavailable"


# --- safety -------------------------------------------------------

def test_provider_has_no_execution_side_effect(fred):
    def _safety():
        h = client.get("/api/health").json()
        return h["automation_enabled"], h["live_broker_transmission"]

    before = _safety()
    assert before == (False, "BLOCKED")
    fp.FredMacroProvider().hydrate_registry(force=True)
    client.get("/api/macro/scorecard/USD")
    client.get("/api/macro/heatmap/USD")
    assert _safety() == (False, "BLOCKED")


def test_provider_module_imports_no_execution_module():
    import types

    import api.providers.fred_provider as mod

    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation"}
    bound = {v.__name__ for v in vars(mod).values() if isinstance(v, types.ModuleType)}
    assert not (bound & forbidden)


def test_no_api_key_committed_in_source():
    """Guard: the provider source must not contain a hardcoded key."""
    src = fp.__file__
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    assert "api_key=" not in text.replace('"api_key":', "").replace("api_key=self", "")  # only env-derived
    assert "stlouisfed" in text  # sanity: this is the FRED provider
    _ = os  # keep import used
