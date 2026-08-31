"""
Unit tests for research_explanations.py
Verifies:
- Centralized metric dictionary completeness and tooltips
- Context-aware classification (Sample size, CI bounds, and Expectancy overrides)
- Monte Carlo mandatory simulation vs live distinction
- Drawdown illustrative calculations
- Signal gate failure explanation formatting
- Risk preview explanation
- Strict absence of emojis and forbidden fake-certainty words
"""

import pytest
import re
from research_explanations import (
    METRIC_CATALOG,
    ExplainableResearchClassifier,
    get_tooltip,
    get_why_text
)


def test_metric_catalog_completeness():
    required_keys = [
        "expectancy_r", "bootstrap_ci", "holdout_expectancy_r", "wfo",
        "monte_carlo", "max_drawdown_r", "win_rate_pct", "profit_factor",
        "complexity_score", "mae", "mfe", "risk_reward_ratio", "slippage", "latency",
        "stage_1d", "stage_4h", "stage_15m", "stage_5m", "stage_1m"
    ]
    for key in required_keys:
        assert key in METRIC_CATALOG, f"Missing {key} in METRIC_CATALOG"
        entry = METRIC_CATALOG[key]
        assert "display_name" in entry
        assert "short_desc" in entry
        assert "detailed_desc" in entry
        assert len(get_tooltip(key)) > 10


def test_sample_size_classification_rules():
    # N < 30 => INSUFFICIENT DATA
    tier_15, _ = ExplainableResearchClassifier.classify_sample_size(15)
    assert tier_15 == "INSUFFICIENT DATA"

    tier_29, _ = ExplainableResearchClassifier.classify_sample_size(29)
    assert tier_29 == "INSUFFICIENT DATA"

    # 30 <= N < 50 => LIMITED SAMPLE
    tier_35, _ = ExplainableResearchClassifier.classify_sample_size(35)
    assert tier_35 == "LIMITED SAMPLE"

    # 50 <= N < 100 => MODERATE SAMPLE
    tier_82, _ = ExplainableResearchClassifier.classify_sample_size(82)
    assert tier_82 == "MODERATE SAMPLE"

    # N >= 100 => LARGE SAMPLE
    tier_150, _ = ExplainableResearchClassifier.classify_sample_size(150)
    assert tier_150 == "LARGE SAMPLE"


def test_confidence_interval_interpretation():
    # Strictly positive CI
    status_pos, text_pos = ExplainableResearchClassifier.classify_confidence_interval(+0.477, +0.817)
    assert status_pos == "POSITIVE EVIDENCE"
    assert "strictly above zero" in text_pos

    # CI crossing zero
    status_cross, text_cross = ExplainableResearchClassifier.classify_confidence_interval(-0.150, +0.450)
    assert status_cross == "UNCERTAIN"
    assert "crosses zero" in text_cross

    # Strictly negative CI
    status_neg, text_neg = ExplainableResearchClassifier.classify_confidence_interval(-0.500, -0.100)
    assert status_neg == "NEGATIVE EVIDENCE"
    assert "strictly below zero" in text_neg


def test_context_aware_expectancy_overrides():
    # Scenario 1: High expectancy (+0.50R) but N < 30 must NEVER be labeled STRONG
    res_small_n = ExplainableResearchClassifier.interpret_expectancy(
        expectancy_r=+0.50,
        trades_n=18,
        ci_low=-0.30,
        ci_high=+1.30
    )
    assert res_small_n["status"] == "INSUFFICIENT DATA"
    assert res_small_n["badge"] == "INSUFFICIENT DATA"

    # Scenario 2: Positive expectancy (+0.20R) but CI crosses zero must be UNCERTAIN
    res_uncertain = ExplainableResearchClassifier.interpret_expectancy(
        expectancy_r=+0.20,
        trades_n=40,
        ci_low=-0.30,
        ci_high=+0.70
    )
    assert res_uncertain["status"] == "UNCERTAIN"
    assert res_uncertain["badge"] == "WARNING"

    # Scenario 3: XAUUSD Holdout (+0.637R, N=82, CI=[+0.477, +0.817]) is STRONG
    res_xauusd = ExplainableResearchClassifier.interpret_expectancy(
        expectancy_r=+0.637,
        trades_n=82,
        ci_low=+0.477,
        ci_high=+0.817,
        wfo_pass_pct=100.0
    )
    assert res_xauusd["status"] in ["STRONG", "VERY STRONG"]
    assert res_xauusd["badge"] == "PASS"
    assert res_xauusd["sample_tier"] == "MODERATE SAMPLE"


def test_drawdown_interpretation():
    dd_info = ExplainableResearchClassifier.interpret_drawdown(median_dd_r=4.25, p95_dd_r=7.80)
    assert dd_info["status"] == "HEALTHY"
    assert "4.25%" in dd_info["interpretation_1pct"]
    assert "equity drawdown" in dd_info["interpretation_05pct"]
    assert "illustrative" in dd_info["note"].lower()


def test_monte_carlo_mandatory_distinction():
    mc_info = ExplainableResearchClassifier.interpret_monte_carlo(prob_neg_return_pct=0.08, prob_20r_dd_pct=0.0)
    assert "LOW HISTORICAL SIMULATION RISK" in mc_info["status"]
    assert "NOT mean there is zero real-world probability" in mc_info["mandatory_distinction"]


def test_signal_gate_explanation():
    # Passing context
    passing_ctx = {"bias_1d_pass": True, "sweep_15m_pass": True, "entry_1m_pass": True}
    res_pass = ExplainableResearchClassifier.explain_signal_gate_status(passing_ctx)
    assert res_pass["eligible"] is True
    assert "ELIGIBLE" in res_pass["overall_status"]

    # Failing context (1D bias blocked)
    failing_ctx = {"bias_1d_pass": False, "sweep_15m_pass": True}
    res_fail = ExplainableResearchClassifier.explain_signal_gate_status(failing_ctx)
    assert res_fail["eligible"] is False
    assert res_fail["overall_status"] == "BLOCKED"
    assert "conflicts" in res_fail["block_reason"]


def test_risk_preview_explanation():
    risk_info = ExplainableResearchClassifier.explain_risk_preview(
        risk_amount_usd=10.0,
        stop_pips=25.0,
        target_pips=75.0,
        rr_ratio=3.0,
        account_balance=2000.0
    )
    assert risk_info["assessment"] == "EXCELLENT"
    assert risk_info["projected_reward_usd"] == 30.0
    assert "maximum planned loss" in risk_info["max_loss_explanation"]


def test_no_emojis_or_forbidden_certainty_words():
    forbidden_words = ["guaranteed profitable", "will make money", "100% safe", "certain profit", "proven to work", "99% guaranteed"]
    
    # Check all catalog strings
    for key, val in METRIC_CATALOG.items():
        text_blob = str(val).lower()
        for word in forbidden_words:
            assert word not in text_blob, f"Found forbidden certainty word '{word}' in METRIC_CATALOG[{key}]"
        
        # Check no emojis
        # Basic regex check for high unicode emoji ranges
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        assert not emoji_pattern.search(str(val)), f"Found emoji in METRIC_CATALOG[{key}]"
