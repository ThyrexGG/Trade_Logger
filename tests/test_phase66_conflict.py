# -*- coding: utf-8 -*-
"""
Phase 66 — multi-provider conflict detection & source precedence.

Offline, pure. `detect_conflicts` never silently picks a value: identical values
agree, materially different values produce a CONFLICT naming the
precedence-selected winner.
"""
from api.macro_evidence import detect_conflicts, source_rank


def _claim(source, value, field="actual", identity=("USD", "CPI", "2026-08")):
    return {"identity": identity, "field": field, "source": source, "value": value}


# --- precedence ----------------------------------------------------

def test_source_precedence_ranks():
    assert source_rank("U.S. Bureau of Labor Statistics (BLS)") == 4
    assert source_rank("FRED:CPIAUCSL") == 3
    assert source_rank("OECD Main Economic Indicators") == 2
    assert source_rank("SomeAggregator") == 1
    assert source_rank("") == 0


# --- agreement ---------------------------------------------------

def test_identical_values_are_not_a_conflict():
    assert detect_conflicts([_claim("FRED", 3.4), _claim("BLS", 3.4)]) == []


def test_values_within_tolerance_are_not_a_conflict():
    assert detect_conflicts([_claim("FRED", 3.40), _claim("BLS", 3.42)]) == []


def test_single_claim_is_never_a_conflict():
    assert detect_conflicts([_claim("FRED", 3.4)]) == []


# --- disagreement ----------------------------------------------

def test_different_values_produce_conflict_with_precedence_winner():
    out = detect_conflicts([_claim("FRED:CPIAUCSL", 3.1), _claim("U.S. BLS", 3.4)])
    assert len(out) == 1
    c = out[0]
    assert c["state"] == "CONFLICT"
    assert c["selected_source"] == "U.S. BLS"   # rank 4 beats FRED rank 3
    assert c["selected_value"] == 3.4
    assert c["country"] == "USD" and c["metric"] == "CPI" and c["period"] == "2026-08"
    assert {cl["source"] for cl in c["claims"]} == {"FRED:CPIAUCSL", "U.S. BLS"}


def test_conflict_is_per_identity_and_field():
    out = detect_conflicts([
        _claim("FRED", 3.1, identity=("USD", "CPI", "2026-08")),
        _claim("BLS", 3.4, identity=("USD", "CPI", "2026-08")),
        _claim("FRED", 2.0, identity=("EUR", "CPI", "2026-08")),
        _claim("Eurostat", 2.02, identity=("EUR", "CPI", "2026-08")),  # within tol -> agree
    ])
    assert len(out) == 1
    assert out[0]["country"] == "USD"


def test_different_series_same_name_not_merged_via_forecast(monkeypatch):
    """A forecast for CORE_CPI must not attach to a CPI release even though both
    'are CPI' — the merge keys on the canonical metric, so they stay separate."""
    from api.macro_evidence import merge_forecasts
    from api.providers.forecast_provider import EconomicForecast
    from macro_intelligence_engine import EconomicDataRegistry, MacroReleaseRecord

    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = True
    EconomicDataRegistry.register_release(MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-08",
        release_timestamp="2026-09-11T12:30:00Z", forecast=None, actual=3.4,
        previous=3.3, unit="%", source="FRED", source_timestamp="2026-09-11T12:30:00Z",
    ))
    res = merge_forecasts([EconomicForecast(
        provider="forecast", source="X", indicator="CORE_CPI", country="USD",
        period="2026-08", forecast=3.0,
    )])
    assert res["merged"] == 0
    assert EconomicDataRegistry._RELEASES[0].forecast is None
    EconomicDataRegistry._RELEASES = []
    EconomicDataRegistry._INITIALIZED = False
