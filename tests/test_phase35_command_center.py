"""
Phase 35 — Daily Trading Command Center Integration Test Suite
Validates master command center payload ("What do I need to know RIGHT NOW?"),
10-point pre-trade checklist, session status, and daily summary generation.
"""

import pytest
from xauusd_daily_command_center import DailyTradingCommandEngine, DailyTradingSummaryEngine


def test_command_center_payload_structure():
    """Validates that DailyTradingCommandEngine returns complete operational state."""
    cmd = DailyTradingCommandEngine.get_command_center_payload("XAUUSD")
    assert isinstance(cmd, dict)
    assert cmd["symbol"] == "XAUUSD"
    assert "current_session" in cmd
    assert "market_day_type" in cmd
    assert "master_condition" in cmd
    assert "holiday_status" in cmd
    assert "has_bank_holiday" in cmd
    assert "what_this_means" in cmd
    assert "strategy_status" in cmd
    assert "UNCHANGED" in cmd["strategy_status"]
    assert "contract_hash" in cmd
    assert "market_data" in cmd
    assert "checklist" in cmd
    assert len(cmd["checklist"]) == 10
    assert "setup_explainability" in cmd
    assert "live_mtf" in cmd
    assert "operational_health" in cmd


def test_daily_trading_summary_engine():
    """Validates that DailyTradingSummaryEngine computes objective daily metrics."""
    summary = DailyTradingSummaryEngine.generate_daily_summary()
    assert isinstance(summary, dict)
    assert "date" in summary
    assert "market_day_type" in summary
    assert "forward_observations_count" in summary
    assert "strategy_setups_approved" in summary
    assert "timeouts_count" in summary
    assert "net_realized_r" in summary
    assert "notes" in summary
