"""
Phase 57: Test Suite for Factor Alignment Engine
Verifies:
- Agreement percentage calculation
- Supporting, neutral, and conflicting factor counts
- Conflict state categorization (ALIGNED, MIXED, CONFLICTING)
- Conflict score range [0, 100]
"""

import pytest
from market_intelligence_scanner import FactorAlignmentEngine


def test_perfect_alignment():
    factors = [
        {"factor_name": "Technical Momentum", "score": 60.0},
        {"factor_name": "Macro Regime", "score": 45.0},
        {"factor_name": "Positioning Flow", "score": 30.0},
        {"factor_name": "Seasonality Profile", "score": 25.0},
    ]
    res = FactorAlignmentEngine.evaluate_alignment(composite_score=50.0, factor_breakdown=factors)
    assert res["conflict_state"] == "ALIGNED"
    assert res["supporting_factors_count"] == 4
    assert res["conflicting_factors_count"] == 0
    assert res["agreement_pct"] == 100.0
    assert res["conflict_score"] == 0.0


def test_conflicting_divergence():
    factors = [
        {"factor_name": "Technical Momentum", "score": 70.0},
        {"factor_name": "Macro Regime", "score": -60.0},
        {"factor_name": "Positioning Flow", "score": -45.0},
        {"factor_name": "Seasonality Profile", "score": -30.0},
    ]
    res = FactorAlignmentEngine.evaluate_alignment(composite_score=40.0, factor_breakdown=factors)
    assert res["conflict_state"] == "CONFLICTING"
    assert res["conflicting_factors_count"] >= 2
    assert res["conflict_score"] > 40.0
    assert res["agreement_pct"] < 50.0


def test_neutral_factors_handling():
    factors = [
        {"factor_name": "Technical Momentum", "score": 5.0},
        {"factor_name": "Macro Regime", "score": -2.0},
        {"factor_name": "Positioning Flow", "score": 0.0},
        {"factor_name": "Seasonality Profile", "score": 4.0},
    ]
    res = FactorAlignmentEngine.evaluate_alignment(composite_score=2.0, factor_breakdown=factors)
    assert res["conflict_state"] == "NEUTRAL"
    assert res["neutral_factors_count"] == 4
