"""
Phase 49 — Tests for Conservative Confidence Intervals & Uncertainty Disclaimers
"""

import pytest
from xauusd_forward_statistical_monitoring import ConservativeUncertaintyEngine


def test_wilson_ci_bounds():
    """Validates Wilson score confidence intervals for binomial win rate."""
    # N = 1, Win = 1 (100% win rate)
    ci95 = ConservativeUncertaintyEngine.calculate_win_rate_ci_wilson(win_count=1, n=1, confidence=0.95)
    # Wilson interval for 1/1 at 95% is approximately [20.7%, 100.0%]
    assert ci95[0] < 30.0
    assert ci95[1] == 100.0


def test_n1_wr100_rejected_as_certainty():
    """Validates that N=1 WR=100% is explicitly marked INSUFFICIENT SAMPLE and prohibited as strategy win rate."""
    unc = ConservativeUncertaintyEngine.evaluate_uncertainty_state(
        n=1,
        win_rate_pct=100.0,
        expectancy_r=2.0,
        r_values=[2.0]
    )
    assert unc["statistical_status"] == "INSUFFICIENT_SAMPLE"
    assert "OBSERVED WIN RATE = 100.0%" in unc["win_rate_statement"]
    assert "strictly prohibited" in unc["prohibited_claim"]


def test_bootstrap_expectancy_ci():
    """Validates non-parametric bootstrap confidence intervals."""
    r_vals = [2.0, -1.0, 2.0, -1.0, 2.0, -1.0, 2.0, 2.0, -1.0, 2.0]
    cis = ConservativeUncertaintyEngine.calculate_expectancy_ci_bootstrap(r_vals, n_bootstraps=500, seed=42)
    assert "ci_90" in cis
    assert "ci_95" in cis
    assert "ci_99" in cis
    assert cis["ci_95"][0] < cis["ci_95"][1]
