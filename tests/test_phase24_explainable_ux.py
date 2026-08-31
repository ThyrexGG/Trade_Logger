"""
Unit tests for Phase 24 Explainable Research UX & Universal Metric Explanations.
"""

import pytest
from research_explanations import METRIC_CATALOG, MetricExplanation, ExplainableResearchClassifier, get_tooltip, get_why_text


def test_metric_catalog_comprehensive_coverage():
    """Verify that all 34+ required technical metrics exist in METRIC_CATALOG with complete 4-question metadata."""
    required_metrics = [
        "expectancy", "expectancy_r", "forward_expectancy",
        "win_rate", "win_rate_pct", "profit_factor", "r_multiple",
        "bootstrap_ci", "sample_size", "forward_sample_size",
        "holdout", "holdout_expectancy_r", "validation", "wfo", "walk_forward",
        "monte_carlo", "max_drawdown_r", "drawdown", "drawdown_status",
        "mae", "mae_r", "mfe", "mfe_r",
        "fvg", "mss", "sweep", "dol", "displacement", "atr",
        "slippage", "spread", "latency", "fill_rate", "timeout_rate", "missed_entry",
        "edge_consistency_score", "strategy_drift", "drift_status", "regime",
        "paper_execution", "shadow_execution",
        "stage_1d", "stage_4h", "stage_15m", "stage_5m", "stage_1m", "validation_stage"
    ]
    
    for metric_id in required_metrics:
        assert metric_id in METRIC_CATALOG, f"Missing metric: {metric_id}"
        entry = METRIC_CATALOG[metric_id]
        assert "display_name" in entry, f"Missing display_name for {metric_id}"
        assert "what_is_it" in entry or "detailed_desc" in entry, f"Missing what_is_it for {metric_id}"
        assert "why_it_matters" in entry, f"Missing why_it_matters for {metric_id}"
        assert "caveat" in entry or "detailed_desc" in entry, f"Missing caveat for {metric_id}"


def test_metric_explanation_component_4_questions():
    """Verify that MetricExplanation produces the required 4 questions and fields."""
    exp = MetricExplanation.explain("expectancy_r", 0.637, trades_n=82, ci_low=0.477, ci_high=0.817)
    
    assert exp["display_name"] == "Expectancy (E[R])"
    assert exp["classification"] == "STRONG"
    assert "what_is_it" in exp and len(exp["what_is_it"]) > 0
    assert "good_or_bad" in exp and len(exp["good_or_bad"]) > 0
    assert "why_it_matters" in exp and len(exp["why_it_matters"]) > 0
    assert "what_to_watch" in exp and len(exp["what_to_watch"]) > 0
    assert "tooltip_text" in exp and len(exp["tooltip_text"]) > 0


def test_metric_explanation_sample_size_override():
    """Verify that N < 30 sample size always overrides raw expectancy to INSUFFICIENT DATA."""
    # Positive expectancy with N = 15 must be classified as PROMISING VALUE — INSUFFICIENT DATA or INSUFFICIENT DATA
    exp = MetricExplanation.explain("forward_expectancy", 0.850, trades_n=15, ci_low=-0.20, ci_high=1.50)
    assert "INSUFFICIENT DATA" in exp["classification"]
    assert exp["classification"] != "STRONG"


def test_metric_explanation_ci_crossing_zero():
    """Verify that CI crossing zero prevents positive expectancy from being classified as STRONG."""
    exp = MetricExplanation.explain("forward_expectancy", 0.450, trades_n=40, ci_low=-0.05, ci_high=0.95)
    assert "UNCERTAIN" in exp["classification"]
    assert exp["classification"] != "STRONG"


def test_metric_explanation_drawdown_tiers():
    """Verify drawdown classification across Normal, Elevated, Stress, and Severe tiers."""
    dd_normal = MetricExplanation.explain("drawdown", 3.5)
    assert dd_normal["classification"] == "NORMAL"
    
    dd_elevated = MetricExplanation.explain("drawdown", 6.0)
    assert dd_elevated["classification"] == "ELEVATED"
    
    dd_stress = MetricExplanation.explain("drawdown", 8.5)
    assert dd_stress["classification"] == "STRESS"
    
    dd_severe = MetricExplanation.explain("drawdown", 14.0)
    assert dd_severe["classification"] == "SEVERE"


def test_metric_explanation_fill_rate():
    """Verify limit order fill rate classification."""
    fill_healthy = MetricExplanation.explain("fill_rate", 85.0)
    assert fill_healthy["classification"] == "HEALTHY"
    
    fill_mod = MetricExplanation.explain("fill_rate", 68.0)
    assert fill_mod["classification"] == "MODERATE"
    
    fill_deg = MetricExplanation.explain("fill_rate", 45.0)
    assert fill_deg["classification"] == "DEGRADED"


def test_tooltip_helpers():
    """Verify tooltip and why text helper functions."""
    tt = get_tooltip("expectancy_r")
    assert len(tt) > 10
    why = get_why_text("expectancy_r")
    assert "Why this matters" in why
