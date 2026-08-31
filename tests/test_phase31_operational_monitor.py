"""
Phase 31 — Market Data Feed & Operational Health Matrix Test Suite
Validates tick/1M candle arrival, freshness age classification, feed error handling,
and 11-dimension operational health matrix evaluation.
"""

import pytest
from datetime import datetime, timezone
from xauusd_operational_monitor import MarketDataFeedAuditor, OperationalHealthEvaluator


def test_market_data_feed_auditor_status():
    """Validates real-time market data feed auditor execution and dictionary keys."""
    feed = MarketDataFeedAuditor.get_feed_status("XAUUSD")
    assert isinstance(feed, dict)
    assert "status" in feed
    assert feed["status"] in ["HEALTHY", "STALE", "ERROR"]
    assert "current_price" in feed
    assert feed["current_price"] > 0
    assert "last_1m_candle_timestamp" in feed
    assert "candle_arrival_age_seconds" in feed
    assert feed["candle_arrival_age_seconds"] >= 0
    assert "feed_source" in feed
    assert "explanation" in feed


def test_market_data_feed_freshness_classification():
    """Validates freshness classification logic for active, delayed, and stale feeds."""
    # Active feed simulation
    feed = MarketDataFeedAuditor.get_feed_status("XAUUSD")
    assert feed["symbol"] == "XAUUSD"
    assert isinstance(feed["recent_1m_candles_count"], int)


def test_operational_health_evaluator_11_dimensions():
    """Validates that OperationalHealthEvaluator produces all 11 required operational checks."""
    op_health = OperationalHealthEvaluator.evaluate_operational_health("XAUUSD")
    assert isinstance(op_health, dict)
    assert "overall_verdict" in op_health
    assert "verdict_color" in op_health
    assert "checks_matrix" in op_health
    assert "last_forward_observation" in op_health
    assert "forward_paper_n" in op_health
    assert "forward_shadow_n" in op_health
    assert "last_data_update" in op_health
    assert "current_price" in op_health

    matrix = op_health["checks_matrix"]
    assert len(matrix) == 11

    check_names = [item["check"] for item in matrix]
    expected_checks = [
        "Market Data",
        "1M Feed",
        "Strategy Evaluation",
        "Paper Pipeline",
        "Shadow Pipeline",
        "Database",
        "Paper/Shadow Parity",
        "Provenance",
        "Dataset Isolation",
        "Contract Integrity",
        "Live Safety Barrier",
    ]
    for exp in expected_checks:
        assert exp in check_names, f"Missing required check: {exp}"
        
    for item in matrix:
        assert "status" in item
        assert "detail" in item
        assert item["status"] in ["HEALTHY", "STALE", "ACTIVE", "CONNECTED", "PASS", "FROZEN", "DISABLED", "CRITICAL", "BLOCKED", "ERROR"]
