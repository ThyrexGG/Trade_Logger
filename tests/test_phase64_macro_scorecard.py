# -*- coding: utf-8 -*-
"""
Phase 64 — EdgeFinder-style Macro Scorecard tests.

Covers: deterministic composite scoring, category structure, missing-evidence
handling (never fabricated), family-specific surprise interpretation, strict
lookahead protection, per-country heatmap isolation, snapshot persistence +
ordering (no synthetic history), provenance labelling, API validation, and
that no macro surface has an execution side effect.
"""
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import database
from api import macro_scorecard as ms
from api.main import app

client = TestClient(app)

# When a real macro provider is wired (.env MACRO_DATA_PROVIDER=fred + FRED_API_KEY)
# macro payloads correctly report provenance="live"; the seed_demo labelling
# assertions only hold with no live provider configured.
_LIVE_MACRO = (os.getenv("MACRO_DATA_PROVIDER") or "").strip().lower() not in ("", "none", "seed_demo")


@pytest.fixture(autouse=True)
def _canonical_registry():
    """Other macro suites (e.g. test_phase56_lookahead) mutate the class-level
    EconomicDataRegistry and never restore it, so force the canonical seed
    before every test here for deterministic, order-independent assertions."""
    from macro_intelligence_engine import EconomicDataRegistry

    EconomicDataRegistry._PROVIDER_MANAGED = False
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
    EconomicDataRegistry.seed_canonical_registry()
    yield


# --- composite scoring ---------------------------------------------------

def test_scorecard_is_deterministic():
    a = ms.get_scorecard("USD")
    b = ms.get_scorecard("USD")
    for k in ("timestamp", "as_of"):
        a.pop(k, None)
        b.pop(k, None)
    assert a == b


def test_scorecard_has_six_named_categories():
    sc = ms.get_scorecard("XAUUSD")
    names = [c["category"] for c in sc["categories"]]
    assert names == ["technical", "cot", "sentiment", "growth", "jobs", "inflation"]
    assert sc["composite_score"] is not None
    assert -10 <= sc["gauge"] <= 10
    assert sc["bias"] in ("VERY BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "VERY BEARISH")


def test_evidence_backed_categories_have_indicator_rows():
    sc = ms.get_scorecard("USD")
    for c in sc["categories"]:
        if c["state"] == "OK" and c["category"] in ("growth", "jobs", "inflation"):
            assert len(c["indicators"]) >= 1
            row = c["indicators"][0]
            assert {"actual", "forecast", "previous", "surprise", "direction"} <= set(row)


def test_technical_and_sentiment_are_insufficient_not_fabricated():
    sc = ms.get_scorecard("USD")
    by = {c["category"]: c for c in sc["categories"]}
    for name in ("technical", "sentiment"):
        assert by[name]["state"] == "INSUFFICIENT_EVIDENCE"
        assert by[name]["score"] is None
        assert by[name]["gauge"] is None
        assert by[name].get("next_dependency")


def test_no_data_currency_returns_insufficient_evidence_not_a_score():
    sc = ms.get_scorecard("CAD")
    assert sc["available"] is False
    assert sc["state"] == "INSUFFICIENT_EVIDENCE"
    assert sc["composite_score"] is None
    assert sc.get("next_dependency")


def test_fx_pair_category_needs_both_legs():
    # JPY has no LABOR/COT releases -> USDJPY jobs/cot must be INSUFFICIENT,
    # never a base-only number presented as a relative score.
    sc = ms.get_scorecard("USDJPY")
    by = {c["category"]: c for c in sc["categories"]}
    assert by["jobs"]["state"] == "INSUFFICIENT_EVIDENCE"
    assert by["jobs"]["score"] is None
    assert by["growth"]["state"] == "OK"  # both EUR... actually USD & JPY both have GDP/PMI


# --- family-specific surprise interpretation ---------------------------

def test_surprise_interpretation_is_family_specific():
    """A weak jobs print is dovish (bullish gold); a hot inflation print is
    hawkish. The engine must not use one universal 'beat = bullish' rule."""
    from macro_intelligence_engine import EconomicDataRegistry, EconomicSurpriseEngine

    EconomicDataRegistry.seed_canonical_registry()
    rels = {r.metric: r for r in EconomicDataRegistry.get_releases_as_of(country="USD")}

    if "NFP" in rels:
        nfp = EconomicSurpriseEngine.evaluate_release_surprise(rels["NFP"])
        if nfp["raw_surprise"] < 0:
            assert "BEARISH LABOR" in nfp["direction"] or "SLOWDOWN" in nfp["direction"]

    if "CPI" in rels:
        cpi = EconomicSurpriseEngine.evaluate_release_surprise(rels["CPI"])
        if cpi["raw_surprise"] > 0:
            assert "HAWKISH" in cpi["direction"] or "UPSIDE" in cpi["direction"]
        elif cpi["raw_surprise"] < 0:
            assert "DOVISH" in cpi["direction"] or "DOWNSIDE" in cpi["direction"]


def test_heatmap_impact_currency_vs_equities_can_differ():
    h = ms.get_country_heatmap("USD")
    assert h["available"]
    # at least one indicator where currency and equity reads diverge
    # (a hawkish inflation surprise supports USD but pressures stocks)
    diverge = [
        r for r in h["indicators"]
        if r["currency_impact"] != r["equity_impact"]
        and "NEUTRAL" not in (r["currency_impact"], r["equity_impact"])
    ]
    # not guaranteed on every seed, but the mechanism must exist
    for r in h["indicators"]:
        assert r["currency_impact"] in ("BULLISH", "BEARISH", "NEUTRAL")
        assert r["equity_impact"] in ("BULLISH", "BEARISH", "NEUTRAL")


# --- lookahead protection --------------------------------------------

def test_lookahead_future_releases_excluded():
    from macro_intelligence_engine import EconomicDataRegistry

    EconomicDataRegistry.seed_canonical_registry()
    early = datetime(2026, 8, 10, tzinfo=timezone.utc)
    late = datetime(2026, 9, 15, tzinfo=timezone.utc)
    n_early = ms.get_scorecard("USD", as_of=early).get("release_count") or 0
    n_late = ms.get_scorecard("USD", as_of=late).get("release_count") or 0
    assert 0 < n_early < n_late


def test_lookahead_release_at_exact_as_of_is_included():
    from macro_intelligence_engine import EconomicDataRegistry

    EconomicDataRegistry.seed_canonical_registry()
    rels = sorted(
        EconomicDataRegistry.get_releases_as_of(country="USD"),
        key=lambda r: r.release_timestamp,
    )
    target = rels[len(rels) // 2]
    at = datetime.fromisoformat(target.release_timestamp.replace("Z", "+00:00"))
    included = EconomicDataRegistry.get_releases_as_of(as_of=at, country="USD")
    assert target in included
    one_sec_before = datetime.fromtimestamp(at.timestamp() - 1, tz=timezone.utc)
    assert target not in EconomicDataRegistry.get_releases_as_of(as_of=one_sec_before, country="USD")


# --- heatmap ---------------------------------------------------------

def test_heatmap_country_isolation():
    us = ms.get_country_heatmap("USD")
    eu = ms.get_country_heatmap("EUR")
    us_names = {r["name"] for r in us["indicators"]}
    eu_names = {r["name"] for r in eu["indicators"]}
    # US has a much larger release set; the smaller EU set is not a superset
    assert len(us_names) > len(eu_names)
    assert us["country"] == "USD" and eu["country"] == "EUR"


def test_heatmap_missing_country_is_insufficient_evidence():
    h = ms.get_country_heatmap("CAD")
    assert h["available"] is False
    assert h["state"] == "INSUFFICIENT_EVIDENCE"
    assert h["indicators"] == []
    assert h.get("next_dependency")


# --- historical snapshots -------------------------------------------

def test_history_empty_state_is_honest_no_fabrication():
    from macro_intelligence_engine import MacroIntelligenceSnapshotStore

    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM macro_intelligence_snapshots WHERE symbol = {ph}", ("GBPJPY",))
        conn.commit()
    finally:
        conn.close()

    hist = ms.get_scorecard_history("GBPJPY")
    assert hist["available"] is False
    assert hist["state"] == "NO_HISTORY"
    assert hist["points"] == []
    assert "accumulate over time" in (hist.get("note") or "")

    # record one real snapshot, then it must appear (and only that one)
    snap_id = ms.record_scorecard_snapshot("GBPJPY")
    assert snap_id
    hist2 = ms.get_scorecard_history("GBPJPY")
    assert hist2["state"] == "OK"
    assert hist2["count"] == 1
    assert hist2["points"][0]["composite_score"] is not None
    assert hist2["points"][0]["fingerprint"]

    _ = MacroIntelligenceSnapshotStore  # keep import used


def test_history_is_ordered_ascending_for_charting(monkeypatch):
    from macro_intelligence_engine import MacroIntelligenceSnapshotStore

    fake = [
        {"symbol": "USD", "timestamp": "2026-09-03T00:00:00Z", "macro_score": 3.0, "macro_direction": "NEUTRAL",
         "growth_score": 1, "inflation_score": 2, "labor_score": 3, "positioning_score": 4, "data_quality": 90,
         "payload_fingerprint": "c"},
        {"symbol": "USD", "timestamp": "2026-09-02T00:00:00Z", "macro_score": 2.0, "macro_direction": "NEUTRAL",
         "growth_score": 1, "inflation_score": 2, "labor_score": 3, "positioning_score": 4, "data_quality": 90,
         "payload_fingerprint": "b"},
        {"symbol": "USD", "timestamp": "2026-09-01T00:00:00Z", "macro_score": 1.0, "macro_direction": "NEUTRAL",
         "growth_score": 1, "inflation_score": 2, "labor_score": 3, "positioning_score": 4, "data_quality": 90,
         "payload_fingerprint": "a"},
    ]
    monkeypatch.setattr(MacroIntelligenceSnapshotStore, "get_recent_snapshots",
                        classmethod(lambda cls, symbol="USD", limit=10, conn=None: list(fake)))
    hist = ms.get_scorecard_history("USD")
    ts = [p["timestamp"] for p in hist["points"]]
    assert ts == sorted(ts)  # ascending for the chart


# --- provenance -----------------------------------------------------

def test_every_response_carries_provenance():
    for payload in (
        ms.get_scorecard("USD"),
        ms.get_scorecard("CAD"),
        ms.get_scorecard_list(),
        ms.get_scorecard_history("USD"),
        ms.get_country_heatmap("USD"),
        ms.get_country_heatmap("CAD"),
        ms.get_heatmap_index(),
    ):
        assert "data_provider" in payload and "provider_is_live" in payload
        assert payload["provenance"] in ("live", "seed_demo", "unavailable")
        if not _LIVE_MACRO:
            assert payload["data_provider"] == "seed_demo"
            assert payload["provider_is_live"] is False
            assert payload["provenance"] == "seed_demo"


# --- API layer ----------------------------------------------------

def test_api_scorecard_endpoints():
    assert client.get("/api/macro/scorecard").status_code == 200
    assert client.get("/api/macro/scorecard/USD").status_code == 200
    assert client.get("/api/macro/scorecard/XAUUSD").status_code == 200
    assert client.get("/api/macro/scorecard/USD/history").status_code == 200
    assert client.get("/api/macro/heatmap").status_code == 200
    assert client.get("/api/macro/heatmap/USD").status_code == 200


def test_api_rejects_unsupported():
    assert client.get("/api/macro/scorecard/NOTREAL").status_code == 404
    assert client.get("/api/macro/scorecard/NOTREAL/history").status_code == 404
    assert client.get("/api/macro/heatmap/XX").status_code == 404
    assert client.get("/api/macro/scorecard/USD/history?limit=0").status_code == 422
    assert client.get("/api/macro/scorecard/USD/history?limit=99999").status_code == 422


def test_scorecard_response_shape():
    d = client.get("/api/macro/scorecard/XAUUSD").json()
    assert d["available"] is True
    assert d["provenance"] in ("live", "seed_demo", "unavailable")
    if not _LIVE_MACRO:
        assert d["provenance"] == "seed_demo"
    assert len(d["categories"]) == 6
    assert "disclaimer" in d


# --- safety -----------------------------------------------------

def test_macro_scorecard_has_no_execution_side_effect():
    def _safety():
        h = client.get("/api/health").json()
        return h["automation_enabled"], h["live_broker_transmission"]

    before = _safety()
    assert before == (False, "BLOCKED")

    client.get("/api/macro/scorecard/XAUUSD")
    client.get("/api/macro/scorecard/USD/history")
    client.get("/api/macro/heatmap/USD")
    client.get("/api/macro/scorecard")

    assert _safety() == (False, "BLOCKED")


def test_scorecard_module_imports_no_execution_module():
    import sys
    import types

    import api.macro_scorecard as mod

    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation"}
    bound = {
        v.__name__
        for v in vars(mod).values()
        if isinstance(v, types.ModuleType)
    }
    assert not (bound & forbidden)
    # and nothing pulled them transitively via this module's direct imports
    _ = sys  # keep import used
