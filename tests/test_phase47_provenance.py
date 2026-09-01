"""
Phase 47 — Observation Provenance & Explainer Test Suite
Validates 3-part explainable research narrative ("Why Was This Created?").
"""

import pytest
from xauusd_forward_evidence_collection import WhyWasThisObservationCreatedExplainer


def test_why_was_this_created_explainer_empty():
    """Validates explainer output when dataset is empty."""
    res = WhyWasThisObservationCreatedExplainer.explain_observation(None)
    assert "status" in res
    assert "what_was_known" in res
    assert "what_was_not_known" in res


def test_why_was_this_created_explainer_with_sample():
    """Validates explainer output for a sample observation."""
    obs = {
        "signal_id": "OBS_SAMPLE_1",
        "entry_time": "2026-09-01T10:00:00Z",
        "entry_price": 2500.0,
        "sl": 2495.0,
        "r_multiple": 1.5,
        "session": "LONDON",
        "news_proximity": "30-60m"
    }
    res = WhyWasThisObservationCreatedExplainer.explain_observation(obs)
    assert res["status"] == "EXPLAINED"
    assert "LONDON" in res["why_recorded"]
    assert "2500.0" in res["what_was_known"]
