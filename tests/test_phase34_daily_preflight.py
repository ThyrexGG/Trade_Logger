"""
Phase 34 — Daily Market Pre-Flight & 10-Point Checklist Test Suite
Validates master pre-flight evaluation, 10-point verification checklist,
proximity countdowns, and non-directional research guidance.
"""

import pytest
from datetime import date
from xauusd_daily_preflight import DailyPreFlightEngine, DailyPreFlightChecklist


def test_daily_preflight_master_state_structure():
    """Validates that DailyPreFlightEngine generates complete pre-flight summary."""
    pf = DailyPreFlightEngine.get_daily_preflight()
    assert isinstance(pf, dict)
    assert "master_state" in pf
    assert pf["master_state"] in [
        "NORMAL DAY", "CAUTION", "HIGH-IMPACT NEWS DAY", "HOLIDAY / REDUCED LIQUIDITY", "MAJOR MARKET CLOSURE", "NEWS DATA UNAVAILABLE"
    ]
    assert "state_color" in pf
    assert "reason" in pf
    assert "research_meaning" in pf
    assert "research_guidance" in pf
    assert "strategy_status" in pf
    assert "UNCHANGED" in pf["strategy_status"]
    assert "next_high_impact_event" in pf
    assert "time_until_event" in pf
    assert "checklist" in pf
    assert len(pf["checklist"]) == 10


def test_ten_point_preflight_checklist_items():
    """Validates that all 10 verification checklist items are evaluated."""
    chk = DailyPreFlightChecklist.evaluate_checklist()
    assert isinstance(chk, dict)
    assert "checklist_items" in chk
    items = chk["checklist_items"]
    assert len(items) == 10
    
    expected_prefixes = [
        "1. Calendar Source Available",
        "2. Timezone & Clock Synchronization",
        "3. Financial Center Bank Holidays",
        "4. Major Session Operating Window",
        "5. High-Impact Event Proximity",
        "6. Market Data Feed Freshness",
        "7. Strategy Contract SHA-256 Immutability",
        "8. Historical Holdout Dataset Isolation",
        "9. Paper / Shadow Parity Integrity",
        "10. Live Trading Safety Barrier"
    ]
    
    for idx, prefix in enumerate(expected_prefixes):
        assert items[idx]["item"].startswith(prefix[:15])
        assert items[idx]["status"] in ["PASS", "WARNING", "CRITICAL"]
        assert len(items[idx]["detail"]) > 0


def test_preflight_guidance_contains_no_directional_advice():
    """Validates that pre-flight research guidance is purely risk/context oriented and never gives BUY/SELL advice."""
    pf = DailyPreFlightEngine.get_daily_preflight()
    guidance = pf["research_guidance"].lower()
    assert "buy" not in guidance
    assert "sell" not in guidance
    assert "long" not in guidance
    assert "short" not in guidance
