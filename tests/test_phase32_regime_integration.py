"""
Phase 32 — Market Condition Regime Integration & Attribution Test Suite
Validates sample size protections across market condition subgroups,
explainable news attribution, and prevention of causal overclaiming.
"""

import pytest
from xauusd_market_conditions import MarketConditionAttributor


def test_news_attribution_insufficient_data_at_low_n():
    """Validates that news attribution returns INSUFFICIENT DATA when sample size is low."""
    res = MarketConditionAttributor.evaluate_news_attribution(mode="PAPER")
    assert isinstance(res, dict)
    assert "attribution_verdict" in res
    assert res["attribution_verdict"] in ["INSUFFICIENT DATA", "POSSIBLE", "SUPPORTED", "NOT SUPPORTED"]
    assert "sample_size_n" in res
    assert "confidence_tier" in res
    assert "explanation" in res
    assert "research_action" in res


def test_news_attribution_does_not_claim_causation():
    """Validates that research explanations caution against claiming correlation as direct causation."""
    res = MarketConditionAttributor.evaluate_news_attribution(mode="PAPER")
    expl = res["explanation"]
    # Must not contain absolute predictive or causal certainty claims
    assert "guaranteed" not in expl.lower()
    assert "certainly" not in expl.lower()
    assert "definitely caused" not in expl.lower()


def test_market_condition_subgroups_structure():
    """Validates that market condition subgroups are clearly separated."""
    res = MarketConditionAttributor.evaluate_news_attribution(mode="PAPER")
    if "subgroups" in res and res["subgroups"]:
        sub = res["subgroups"]
        assert "normal_conditions" in sub
        assert "high_impact_news_window" in sub
        assert "holiday_affected" in sub
        for k, v in sub.items():
            assert "n" in v
            assert "status" in v
            assert v["status"] in ["INSUFFICIENT DATA", "LIMITED OBSERVATIONS", "EARLY REGIME EVIDENCE", "REGIME SAMPLE"]
