"""
Phase 38 — Multi-Provider Comparison & Truthfulness Test Suite
Validates provider comparison across primary, secondary, and fallback sources,
ensuring truthful reporting when Forex Factory live API is unavailable.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_news_snapshot_store import MultiProviderComparator


def test_multi_provider_comparison_structure():
    """Validates multi-provider comparison payload and source classification."""
    target_dt = date(2026, 9, 1)
    res = MultiProviderComparator.compare_providers_for_date(target_dt)

    assert isinstance(res, dict)
    assert res["target_date"] == "2026-09-01"
    assert "providers" in res
    assert len(res["providers"]) == 3
    assert "agreement_verdict" in res
    assert res["agreement_verdict"] in [
        "PROVIDER AGREEMENT",
        "MINOR DISCREPANCY",
        "SIGNIFICANT DISCREPANCY",
        "PROVIDER UNAVAILABLE"
    ]


def test_forex_factory_truthful_unavailability():
    """Confirms Forex Factory live status is reported truthfully as UNAVAILABLE without fabrication."""
    target_dt = date(2026, 9, 1)
    res = MultiProviderComparator.compare_providers_for_date(target_dt)

    assert res["forex_factory_live_status"] == "UNAVAILABLE"
    assert "truthfulness_note" in res
    ff_provider = [p for p in res["providers"] if "FOREX_FACTORY" in p["provider_label"]][0]
    assert "UNAVAILABLE" in ff_provider["status"]


def test_secondary_and_fallback_provider_availability():
    """Validates that secondary macro feed provides verified scheduled releases."""
    target_dt = date(2026, 9, 1)
    res = MultiProviderComparator.compare_providers_for_date(target_dt)

    sec_provider = [p for p in res["providers"] if "SECONDARY" in p["provider_label"]][0]
    assert sec_provider["is_available"] is True
    assert sec_provider["events_count"] >= 1
