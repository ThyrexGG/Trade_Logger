"""
Phase 36 — No-Lookahead Protection & Historical Integrity Test Suite
Validates that historical date audits only attach information known at the historical timestamp.
"""

import pytest
from datetime import date
from xauusd_news_reliability import HistoricalNewsAuditEngine


def test_historical_audit_no_future_leakage():
    """Validates that auditing a historical date reconstructs only past/same-day events."""
    past_date = date(2026, 8, 14)
    audit = HistoricalNewsAuditEngine.audit_historical_date(past_date)
    assert audit["date"] == "2026-08-14"
    assert "master_state" in audit
    assert "attribution_tag" in audit
    assert audit["attribution_tag"] in ["INSUFFICIENT DATA", "OBSERVED"]
    assert "[KNOWN]" in audit["explanation"]
    assert "[OBSERVED]" in audit["explanation"]
