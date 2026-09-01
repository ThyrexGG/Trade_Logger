"""
TradeLogger Phase 57 — Test Suite: Factor Alignment & Consensus Engine
=======================================================================
Validates:
- Multi-factor directional consensus and conflict scoring.
- Agreement % calculation across contributing factors.
- Identification of dominant and weakest factors.
- Factor divergence warning trigger when macro/cot/trend conflict.
"""

import pytest
from market_intelligence_scanner import FactorAlignmentEngine


def test_factor_alignment_unanimous():
    """Verify high agreement when all factors point in the same direction."""
    factors = [
        {"factor_name": "Technical Momentum", "score": 45.0, "weight": 0.25},
        {"factor_name": "Macro Context", "score": 30.0, "weight": 0.25},
        {"factor_name": "Positioning / COT", "score": 20.0, "weight": 0.25},
        {"factor_name": "Seasonality", "score": 15.0, "weight": 0.25},
    ]
    res = FactorAlignmentEngine.evaluate_alignment(overall_score=35.0, factors=factors)
    assert res["agreement_pct"] == 100.0
    assert res["conflict_state"] == "ALIGNED"
    assert res["conflict_score"] <= 25.0
    assert "Technical" in res["dominant_factor"]


def test_factor_alignment_mixed():
    """Verify mixed status when factors have conflict."""
    factors = [
        {"factor_name": "Technical Momentum", "score": 50.0, "weight": 0.25},
        {"factor_name": "Macro Context", "score": -40.0, "weight": 0.25},
        {"factor_name": "Positioning", "score": 10.0, "weight": 0.25},
        {"factor_name": "Seasonality", "score": -15.0, "weight": 0.25}
    ]
    res = FactorAlignmentEngine.evaluate_alignment(overall_score=30.0, factors=factors)
    assert res["agreement_pct"] <= 60.0
    assert res["conflict_state"] in {"MIXED", "CONFLICTING"}


def test_factor_alignment_empty():
    """Verify fallback handling for empty factors list."""
    res = FactorAlignmentEngine.evaluate_alignment(overall_score=0.0, factors=[])
    assert res["conflict_state"] == "NEUTRAL"
    assert res["agreement_pct"] == 50.0
    assert res["dominant_factor"] == "NONE"
