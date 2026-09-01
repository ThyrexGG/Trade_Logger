"""
Test Suite: Phase 56 Factor Conflict Detector
=============================================
Validates structural divergence detection between Technicals, Macro,
Positioning (COT), and Seasonality.
"""

from macro_intelligence_engine import FactorConflictDetector


def test_technical_vs_macro_conflict():
    """Verifies detection of bullish technicals vs bearish macro."""
    res = FactorConflictDetector.evaluate_conflicts(
        symbol="XAUUSD",
        technical_score=80.0,
        macro_score=-45.0,
        positioning_score=30.0,
        seasonality_score=10.0
    )
    assert res["has_conflict"] is True
    assert res["conflict_count"] >= 1
    types = [c["type"] for c in res["conflicts"]]
    assert "TECHNICAL_VS_MACRO" in types


def test_unified_factor_alignment():
    """Verifies clean alignment when technicals and macro agree."""
    res = FactorConflictDetector.evaluate_conflicts(
        symbol="XAUUSD",
        technical_score=75.0,
        macro_score=50.0,
        positioning_score=40.0,
        seasonality_score=20.0
    )
    assert res["has_conflict"] is False
    assert res["agreement_pct"] == 100.0
