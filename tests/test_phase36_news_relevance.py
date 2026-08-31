"""
Phase 36 — High-Impact News Relevance & Deterministic Classification Test Suite
Validates deterministic mapping of USD, Fed, US Macro, and Gold drivers into LOW, MEDIUM, HIGH, and EXTREME.
"""

import pytest
from xauusd_news_reliability import HighImpactNewsDetector


def test_extreme_impact_classification():
    """Validates that FOMC, Fed Rate Decisions, and Powell speeches receive EXTREME rating."""
    res1 = HighImpactNewsDetector.classify_event_impact("FOMC Rate Decision", "USD")
    assert res1["impact_rating"] == "EXTREME"
    assert res1["xauusd_relevance"] == "HIGH"

    res2 = HighImpactNewsDetector.classify_event_impact("Fed Chair Powell Speaks", "USD")
    assert res2["impact_rating"] == "EXTREME"


def test_high_impact_macro_classification():
    """Validates that CPI, Core PCE, NFP, GDP, and ISM receive HIGH rating."""
    events = [
        "Core CPI (MoM)",
        "Non-Farm Employment Change",
        "Core PCE Price Index",
        "Advance GDP (QoQ)",
        "ISM Manufacturing PMI",
    ]
    for ev in events:
        res = HighImpactNewsDetector.classify_event_impact(ev, "USD")
        assert res["impact_rating"] == "HIGH"
        assert res["xauusd_relevance"] == "HIGH"


def test_medium_and_routine_classification():
    """Validates that Jobless Claims receives MEDIUM, and non-USD routine receives LOW."""
    res_jc = HighImpactNewsDetector.classify_event_impact("Initial Jobless Claims", "USD")
    assert res_jc["impact_rating"] == "MEDIUM"

    res_eur = HighImpactNewsDetector.classify_event_impact("French Consumer Spending", "EUR")
    assert res_eur["impact_rating"] == "LOW"
    assert res_eur["xauusd_relevance"] == "LOW"
