"""
Phase 38 — Market Condition Subgroup Correlation & Sample-Size Protection Test Suite
Validates forward observation subgrouping across holidays, news windows, and sessions,
enforcing strict statistical sample size protection rules (N < 10, 10-20, 20-30, N >= 30).
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_market_condition_correlation import SubgroupCorrelationEngine


def test_subgroup_correlation_structure_and_disclaimer():
    """Validates subgroup correlation report structure and presence of mandatory disclaimer."""
    res = SubgroupCorrelationEngine.audit_subgroup_correlations(mode="PAPER")

    assert isinstance(res, dict)
    assert "subgroups" in res
    assert len(res["subgroups"]) == 10
    assert "disclaimer" in res
    assert "does not establish that news or holidays caused" in res["disclaimer"]


def test_sample_size_protection_tiers():
    """Validates that sample counts are categorized into exact statistical confidence tiers."""
    tier_0, col_0 = SubgroupCorrelationEngine.classify_sample_tier(0)
    assert tier_0 == "INSUFFICIENT DATA"

    tier_5, col_5 = SubgroupCorrelationEngine.classify_sample_tier(5)
    assert tier_5 == "INSUFFICIENT DATA"

    tier_15, col_15 = SubgroupCorrelationEngine.classify_sample_tier(15)
    assert tier_15 == "LIMITED OBSERVATIONS"

    tier_25, col_25 = SubgroupCorrelationEngine.classify_sample_tier(25)
    assert tier_25 == "EARLY REGIME EVIDENCE"

    tier_50, col_50 = SubgroupCorrelationEngine.classify_sample_tier(50)
    assert tier_50 == "REGIME SAMPLE"


def test_small_sample_metrics_masked():
    """Validates that subgroups with N < 10 mask statistical metrics to prevent small-sample overinterpretation."""
    res = SubgroupCorrelationEngine.audit_subgroup_correlations(mode="PAPER")
    for sg in res["subgroups"]:
        if sg["sample_n"] < 10:
            assert sg["win_rate_pct"] == "N/A (<10)"
            assert sg["avg_r"] == "N/A (<10)"
            assert sg["statistical_tier"] == "INSUFFICIENT DATA"
