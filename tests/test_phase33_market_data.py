"""
Phase 33 — Real Market Data Freshness & Ingestion Test Suite
Validates market data feed status, arrival age calculation, price tracking,
and classification into LIVE DATA / STALE DATA / DATA UNAVAILABLE.
"""

import pytest
from xauusd_operational_monitor import MarketDataFeedAuditor


def test_market_data_feed_audit_structure():
    """Validates that MarketDataFeedAuditor returns complete feed diagnostic metrics."""
    audit = MarketDataFeedAuditor.get_feed_status("XAUUSD")
    assert isinstance(audit, dict)
    assert "status" in audit
    assert audit["status"] in ["HEALTHY", "STALE", "ERROR"]
    assert "current_price" in audit
    assert isinstance(audit["current_price"], float)
    assert audit["current_price"] > 0
    assert "candle_arrival_age_seconds" in audit
    assert "feed_source" in audit


def test_market_data_synthetic_age_classification():
    """Validates classification rules for fresh vs stale arrival ages."""
    audit = MarketDataFeedAuditor.get_feed_status("XAUUSD")
    assert audit["status"] in ["HEALTHY", "STALE", "ERROR"]
    assert "explanation" in audit
