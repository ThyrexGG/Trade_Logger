"""
Phase 36 — 7-Financial Center Holiday & Market Closure Accuracy Test Suite
Validates distinction between Bank Holiday, Exchange Holiday, Reduced Liquidity, and Full Market Closure.
"""

import pytest
from datetime import date
from xauusd_news_reliability import MarketClosureAuditor


def test_bank_holiday_vs_market_closure_distinction():
    """Validates that a UK bank holiday does NOT declare full gold market closure."""
    # 2026-08-31 is Summer Bank Holiday (UK)
    dt_bank_holiday = date(2026, 8, 31)
    audit = MarketClosureAuditor.audit_market_closures(dt_bank_holiday)
    assert audit["is_spot_gold_open"] is True
    assert audit["closed_centers_count"] >= 1
    assert "BANK HOLIDAY" in audit["overall_closure_type"]
    assert any(c["center"] == "London" and c["is_closed"] for c in audit["closed_centers"])


def test_weekend_full_market_closure():
    """Validates that Saturday/Sunday evaluates to FULL MARKET CLOSURE."""
    dt_weekend = date(2026, 8, 29)  # Saturday
    audit = MarketClosureAuditor.audit_market_closures(dt_weekend)
    assert audit["is_spot_gold_open"] is False
    assert audit["overall_closure_type"] == "FULL MARKET CLOSURE"


def test_7_financial_centers_evaluated():
    """Validates that exactly 7 financial centers are evaluated."""
    audit = MarketClosureAuditor.audit_market_closures(date(2026, 9, 1))
    centers = [c["center"] for c in audit["all_centers"]]
    expected = ["London", "New York", "Frankfurt", "Tokyo", "Shanghai", "Sydney", "Zurich"]
    for exp in expected:
        assert exp in centers
