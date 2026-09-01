"""
Phase 48 — Tests for SQLite Data Integrity & Clean Production Schema
"""

import pytest
from xauusd_forward_lifecycle import ForwardLifecycleReconciliationAudit, ForwardMorningAwaySummaryClassifier


def test_sqlite_integrity_clean_baseline():
    audit = ForwardLifecycleReconciliationAudit.audit_database_integrity()
    assert audit["dataset_isolation_clean"] is True
    assert audit["duplicate_signal_ids"] == 0
    assert audit["invalid_price_records"] == 0


def test_morning_away_summary_classification():
    summary = ForwardMorningAwaySummaryClassifier.classify_away_reality()
    assert isinstance(summary, dict)
    assert "category" in summary
    assert "title" in summary
    assert "explanation" in summary
    assert "color" in summary
    assert summary["category"] in [
        "NO_SETUP_DETECTED", "SETUP_DETECTED_REJECTED", "SETUP_QUARANTINED",
        "GENUINE_OBSERVATION_CAPTURED", "EXECUTION_RECORDED", "OUTCOME_COMPLETED",
        "DATA_INTEGRITY_ANOMALY", "MARKET_CLOSED_HOLIDAY"
    ]
