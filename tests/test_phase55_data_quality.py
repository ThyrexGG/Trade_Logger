"""
Phase 55 — Tests for Data Quality Score & False Precision Prevention
"""

import pytest
from asset_edge_intelligence import DataQualityScoreEvaluator


def test_high_quality_data_scoring():
    factors = [
        {"factor_name": "F1", "data_available": True, "source": {"status": "HEALTHY"}},
        {"factor_name": "F2", "data_available": True, "source": {"status": "HEALTHY"}},
        {"factor_name": "F3", "data_available": True, "source": {"status": "HEALTHY"}},
        {"factor_name": "F4", "data_available": True, "source": {"status": "HEALTHY"}}
    ]
    dq = DataQualityScoreEvaluator.evaluate_data_quality(factors)
    assert dq["score"] == 100
    assert dq["status"] == "HEALTHY"
    assert dq["is_decision_grade"] is True


def test_insufficient_data_scoring_prevents_false_precision():
    factors = [
        {"factor_name": "F1", "data_available": False, "source": {"status": "UNAVAILABLE"}},
        {"factor_name": "F2", "data_available": False, "source": {"status": "UNAVAILABLE"}},
        {"factor_name": "F3", "data_available": False, "source": {"status": "UNAVAILABLE"}},
        {"factor_name": "F4", "data_available": True, "source": {"status": "HEALTHY"}}
    ]
    dq = DataQualityScoreEvaluator.evaluate_data_quality(factors)
    assert dq["score"] < 40
    assert dq["status"] == "UNAVAILABLE"
    assert dq["is_decision_grade"] is False
