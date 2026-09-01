"""
Phase 55 — Tests for Factor Conflict Detection
"""

import pytest
from asset_edge_intelligence import FactorConflictDetector


def test_conflict_detection_reduces_confidence():
    factors = [
        {"factor_name": "Technicals", "score": 60.0, "direction": "BULLISH"},
        {"factor_name": "SMC", "score": 40.0, "direction": "BULLISH"},
        {"factor_name": "Macro", "score": -50.0, "direction": "BEARISH"},
        {"factor_name": "Dollar", "score": -40.0, "direction": "BEARISH"}
    ]
    res = FactorConflictDetector.analyze_conflicts(factors)
    assert res["has_conflict"] is True
    assert res["confidence_multiplier"] < 1.0
    assert len(res["conflict_pairs"]) > 0


def test_unified_factors_full_confidence():
    factors = [
        {"factor_name": "Technicals", "score": 60.0, "direction": "BULLISH"},
        {"factor_name": "SMC", "score": 40.0, "direction": "BULLISH"},
        {"factor_name": "Macro", "score": 30.0, "direction": "BULLISH"}
    ]
    res = FactorConflictDetector.analyze_conflicts(factors)
    assert res["has_conflict"] is False
    assert res["confidence_multiplier"] == 1.0
    assert res["factor_agreement_pct"] == 100.0
