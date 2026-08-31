"""
Phase 36 — Honest News Attribution & Small-Sample Protections Test Suite
Validates that N < 10 subgroups trigger INSUFFICIENT DATA and non-causal language.
"""

import pytest
from datetime import date
from xauusd_news_reliability import HistoricalNewsAuditEngine


def test_insufficient_data_tag_for_small_samples():
    """Validates that small historical trade samples (<10) are marked as INSUFFICIENT DATA."""
    # Pick a date with 0 or few trades
    audit = HistoricalNewsAuditEngine.audit_historical_date(date(2026, 8, 1))
    if audit["forward_trades_count"] < 10:
        assert audit["attribution_tag"] == "INSUFFICIENT DATA"
    assert "non-causal" in audit["explanation"].lower()
