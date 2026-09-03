# -*- coding: utf-8 -*-
"""
Phase 66 — evidence orchestrator: coverage matrix, provider states, defaults.

Offline. Verifies the seed_demo default is unchanged, per-category coverage is
honest (missing != zero), and provider selection composes without coupling the
scoring engine to a vendor.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.macro_evidence import ensure_evidence

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    from macro_intelligence_engine import EconomicDataRegistry

    for v in ("MACRO_DATA_PROVIDER", "MACRO_COT_PROVIDER", "MACRO_FORECAST_PROVIDER",
              "MACRO_SENTIMENT_PROVIDER"):
        monkeypatch.delenv(v, raising=False)
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry._PROVIDER_MANAGED = False
    yield
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry._PROVIDER_MANAGED = False


def test_seed_demo_default_unchanged():
    ev = ensure_evidence()
    assert ev["data_provider"] == "seed_demo"
    assert ev["provider_is_live"] is False
    assert ev["provenance"] == "seed_demo"
    assert ev["provider_state"] == "SEED_DEMO"


def test_coverage_matrix_is_honest_about_missing_data():
    ev = ensure_evidence()
    cov = ev["coverage"]
    # seed has USD/EUR/GBP/JPY releases, nothing for CAD/AUD/NZD/CHF
    assert cov["USD"]["growth"] == "SEED_DEMO"
    assert cov["CAD"]["growth"] == "INSUFFICIENT_EVIDENCE"
    # sentiment has no provider anywhere
    assert all(cov[c]["sentiment"] == "INSUFFICIENT_EVIDENCE" for c in cov)
    # COT: seed has a USD prior release, none for EUR
    assert cov["EUR"]["cot"] == "INSUFFICIENT_EVIDENCE"


def test_capabilities_summary_lists_declared_and_configured():
    ev = ensure_evidence()
    caps = ev["capabilities"]
    assert caps["consensus_forecast"]["declared_by"] == ["forecast"]
    assert caps["consensus_forecast"]["configured_by"] == []
    assert caps["consensus_forecast"]["available"] is False
    assert caps["cot_positioning"]["declared_by"] == ["cftc"]


def test_none_provider_marks_everything_unavailable(monkeypatch):
    monkeypatch.setenv("MACRO_DATA_PROVIDER", "none")
    ev = ensure_evidence()
    assert ev["provider_state"] == "NONE"
    assert ev["coverage"]["USD"]["growth"] == "NONE"


def test_forecast_none_path_is_clean(monkeypatch):
    monkeypatch.setenv("MACRO_FORECAST_PROVIDER", "none")
    ev = ensure_evidence()
    assert ev["forecast_status"]["provider_state"] == "NOT_CONFIGURED"
    assert ev["forecast_merge"] == {"merged": 0, "unmatched": 0}
    assert ev["conflicts"] == []


def test_providers_endpoint_shape():
    d = client.get("/api/macro/providers").json()
    assert d["available"] in (True, False)
    assert {p["key"] for p in d["providers"]} >= {"fred", "cftc", "forecast", "sentiment"}
    assert "USD" in d["coverage"]
    assert isinstance(d["precedence"], list) and d["precedence"]
    # no secret anywhere in the payload
    blob = str(d).lower()
    assert "api_key" not in blob and "secret" not in blob


def test_evidence_never_raises_even_if_a_provider_explodes(monkeypatch):
    import api.providers.cftc_provider as cp

    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")

    def _boom(*a, **k):
        raise RuntimeError("provider on fire")

    monkeypatch.setattr(cp.CftcCotProvider, "hydrate_registry", _boom)
    ev = ensure_evidence()  # must not raise
    assert ev["cot_status"]["provider_state"] == "PROVIDER_UNAVAILABLE"
