"""
Phase 39 — Forward Observation Quality Engine Test Suite
Validates comprehensive observation identity, temporal checks, pricing checks, context completeness,
and 0-100 evidence quality index.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_forward_observation_quality import (
    ForwardObservationQualityEngine,
    ObservationEvidenceQualityScorer,
    DailyForwardDataQualityReporter,
)


def test_valid_observation_quality_audit():
    """Validates that a complete observation receives COMPLETE classification."""
    valid_obs = {
        "signal_id": "SIG_VALID_001",
        "execution_mode": "PAPER",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requested_entry": 2400.50,
        "stop_loss": 2390.00,
        "take_profit": 2420.00,
        "mtf_layers": {"1d": "BULLISH", "4h": "BULLISH", "15m": "CONFIRMED"},
        "session": "LONDON",
        "nearest_event_name": "US CPI",
        "news_proximity": "POST_EVENT"
    }

    res = ForwardObservationQualityEngine.audit_observation(valid_obs)
    assert res["is_valid"] is True
    assert res["classification"] == "COMPLETE"
    assert res["errors_count"] == 0
    assert len(res["fingerprint"]) == 64


def test_future_timestamp_detected_and_quarantined():
    """Validates that observations with future timestamps trigger quarantine."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    invalid_obs = {
        "signal_id": "SIG_FUTURE_001",
        "execution_mode": "PAPER",
        "timestamp": future_time,
        "requested_entry": 2400.50,
    }

    res = ForwardObservationQualityEngine.audit_observation(invalid_obs)
    assert res["is_valid"] is False
    assert res["classification"] == "QUARANTINED"
    assert any("FUTURE_TIMESTAMP" in e for e in res["errors"])


def test_missing_price_detected():
    """Validates that missing or zero price triggers validation error."""
    invalid_obs = {
        "signal_id": "SIG_NO_PRICE_001",
        "execution_mode": "PAPER",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requested_entry": 0.0,
    }

    res = ForwardObservationQualityEngine.audit_observation(invalid_obs)
    assert res["is_valid"] is False
    assert any("INVALID_ENTRY_PRICE" in e for e in res["errors"])


def test_observation_evidence_quality_scorer_ten_dimensions():
    """Validates 0-100 evidence quality score breakdown across 10 dimensions."""
    sample_obs = {
        "signal_id": "SIG_SCORE_001",
        "execution_mode": "PAPER",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requested_entry": 2400.50,
        "stop_loss": 2390.00,
        "take_profit": 2420.00,
        "mtf_layers": {"1d": "BULLISH"},
        "session": "NEW_YORK",
        "nearest_event_name": "US NFP"
    }

    score_res = ObservationEvidenceQualityScorer.calculate_observation_quality_score(sample_obs)
    assert isinstance(score_res, dict)
    assert 0 <= score_res["total_score"] <= 100
    assert score_res["max_score"] == 100
    assert len(score_res["breakdown"]) == 10


def test_daily_forward_data_quality_report():
    """Validates daily forward data quality report generation."""
    target_dt = date(2026, 9, 1)
    rep = DailyForwardDataQualityReporter.generate_daily_quality_report(target_dt)

    assert isinstance(rep, dict)
    assert "verdict" in rep
    assert rep["verdict"] in ["CLEAN", "REVIEW REQUIRED", "DATA INCOMPLETE", "CRITICAL INTEGRITY ISSUE"]
    assert "average_quality_score" in rep
    assert rep["live_automation"] == "DISABLED_PERMANENTLY"
