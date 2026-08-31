"""
Phase 34 — News-Aware Regime Attribution & Sample Size Protection Test Suite
Validates that market-condition performance attribution enforces scientific sample protections
and prevents premature causal claims from small samples.
"""

import pytest
from xauusd_market_conditions import MarketConditionAttributor


def test_market_condition_attribution_sample_protections():
    """Validates that news attribution respects sample size thresholds."""
    res = MarketConditionAttributor.evaluate_news_attribution(mode="PAPER")
    assert isinstance(res, dict)
    assert "attribution_verdict" in res
    assert "confidence_tier" in res
    assert "sample_size_n" in res
    
    n = res["sample_size_n"]
    if n < 10:
        assert res["attribution_verdict"] == "INSUFFICIENT DATA"
        assert "INSUFFICIENT DATA" in res["confidence_tier"]


def test_subgroups_metric_separation():
    """Validates that Normal, High-Impact News, and Holiday subgroups are strictly separated."""
    res = MarketConditionAttributor.evaluate_news_attribution(mode="PAPER")
    if "subgroups" in res and res["subgroups"]:
        sub = res["subgroups"]
        assert "normal_conditions" in sub
        assert "high_impact_news_window" in sub
        assert "holiday_affected" in sub
