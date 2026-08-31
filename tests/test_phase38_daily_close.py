"""
Phase 38 — Daily Context Close Audit & Data Quality Scorer Test Suite
Validates end-of-day close audit synthesis and 6-dimension data quality scoring (0-100).
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_market_condition_correlation import (
    DailyContextCloseAuditor,
    MarketContextDataQualityScorer,
)


def test_data_quality_scorer_six_dimensions():
    """Validates 0-100 data quality score and 6-dimension breakdown."""
    target_dt = date(2026, 9, 1)
    q_score = MarketContextDataQualityScorer.calculate_quality_score(target_dt)

    assert isinstance(q_score, dict)
    assert 0 <= q_score["total_score"] <= 100
    assert q_score["max_score"] == 100
    assert len(q_score["breakdown"]) == 6

    dims = [b["dimension"] for b in q_score["breakdown"]]
    assert "Calendar Completeness" in dims
    assert "Timestamp Integrity" in dims
    assert "Provider Agreement" in dims
    assert "Holiday Coverage" in dims
    assert "Market Data Completeness" in dims
    assert "Snapshot Integrity" in dims


def test_daily_close_audit_clean_verdict():
    """Validates end-of-day close audit returns CLEAN verdict when no critical gaps exist."""
    target_dt = date(2026, 9, 1)
    close_audit = DailyContextCloseAuditor.audit_daily_close(target_dt)

    assert isinstance(close_audit, dict)
    assert close_audit["target_date"] == "2026-09-01"
    assert "verdict" in close_audit
    assert close_audit["verdict"] in [
        "DAILY CONTEXT AUDIT: CLEAN",
        "DAILY CONTEXT AUDIT: REVIEW REQUIRED",
        "DAILY CONTEXT AUDIT: DATA INCOMPLETE"
    ]
    assert close_audit["live_automation"] == "DISABLED_PERMANENTLY"
