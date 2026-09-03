# -*- coding: utf-8 -*-
"""
Phase 67 — GET /api/intelligence/asset/{asset} contract.

Read-only. Schema shape, invalid / unknown asset handling, historical as-of,
and no execution verb.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


_TOP_KEYS = {
    "asset", "as_of", "generated_at", "mode", "categories", "cross_category_state",
    "cross_category", "coverage", "conflicts", "data_gaps", "provenance",
    "provider_health", "model_version", "disclaimer", "safety_barrier",
}


def test_live_snapshot_schema():
    r = client.get("/api/intelligence/asset/XAUUSD")
    assert r.status_code == 200
    j = r.json()
    assert _TOP_KEYS <= set(j)
    assert j["asset"] == "XAUUSD"
    assert j["mode"] == "LIVE"
    assert isinstance(j["categories"], list) and len(j["categories"]) == 7
    for c in j["categories"]:
        assert {"category", "state", "direction", "score", "evidence_count"} <= set(c)
    # never a single blended composite
    assert "overall_score" not in j and "composite_score" not in j
    assert j["safety_barrier"]["live_broker_transmission"] == "BLOCKED"
    assert "execution signal" in j["disclaimer"].lower()


def test_symbol_is_case_insensitive():
    assert client.get("/api/intelligence/asset/eurusd").json()["asset"] == "EURUSD"


def test_invalid_symbol_422():
    assert client.get("/api/intelligence/asset/@@@").status_code == 422


def test_unknown_symbol_404():
    r = client.get("/api/intelligence/asset/NOTREAL")
    assert r.status_code == 404


def test_historical_as_of():
    r = client.get("/api/intelligence/asset/XAUUSD?as_of=2026-08-01T00:00:00Z")
    assert r.status_code == 200
    j = r.json()
    assert j["mode"] == "HISTORICAL"
    assert j["as_of"].startswith("2026-08-01T00:00:00")
    # live-only categories are honestly INSUFFICIENT_EVIDENCE, not fabricated
    states = {c["category"]: c["state"] for c in j["categories"]}
    assert states["TECHNICAL"] in ("INSUFFICIENT_EVIDENCE", "PROVIDER_UNAVAILABLE")


def test_bad_as_of_422():
    assert client.get("/api/intelligence/asset/XAUUSD?as_of=not-a-date").status_code == 422


def test_endpoint_is_get_only():
    assert client.post("/api/intelligence/asset/XAUUSD").status_code == 405
    assert client.delete("/api/intelligence/asset/XAUUSD").status_code == 405
    assert client.put("/api/intelligence/asset/XAUUSD").status_code == 405


def test_no_secret_in_response(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "SECRET" + "z" * 24)
    blob = str(client.get("/api/intelligence/asset/XAUUSD").json())
    assert "SECRET" + "z" * 24 not in blob
    assert "api_key" not in blob.lower()


def test_provider_outage_surfaces_not_neutral(monkeypatch):
    """A macro provider outage must surface as PROVIDER_UNAVAILABLE with a null
    score — never a fabricated neutral reading."""
    import api.evidence_fusion as fusion
    from api import macro_scorecard

    def _outage(instrument, as_of=None):
        return {
            "instrument": instrument, "available": False, "state": "PROVIDER_UNAVAILABLE",
            "reason": "The configured macro data provider is unavailable.",
            "composite_score": None, "gauge": None, "bias": None, "categories": [],
            "data_provider": "fred", "provenance": "unavailable",
        }

    monkeypatch.setattr(macro_scorecard, "get_scorecard", _outage)
    fusion.invalidate()
    try:
        j = client.get("/api/intelligence/asset/XAUUSD").json()
        macro = next(c for c in j["categories"] if c["category"] == "MACRO")
        assert macro["state"] == "PROVIDER_UNAVAILABLE"
        assert macro["state"] != "INSUFFICIENT_EVIDENCE"
        assert macro["score"] is None
        assert macro["direction"] == "UNKNOWN"
    finally:
        fusion.invalidate()
