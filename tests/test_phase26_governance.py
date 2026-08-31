"""
Unit tests for Phase 26 — Governance, Research Health Matrix, Watchdogs, and Safety Barriers.
"""

import pytest
from xauusd_research_governance import (
    XAUUSDParityWatchdog,
    XAUUSDDataIntegrityWatchdog,
    ResearchHealthMatrix,
    WatchNextAdvisor,
    LiveTradingSafetyBarrier
)
from xauusd_alert_engine import XAUUSDAlertEngine


def test_parity_watchdog_clean_state():
    res = XAUUSDParityWatchdog.audit_parity()
    assert res["is_parity_clean"] is True
    assert res["status"] == "100% PARITY"
    assert len(res["mismatches"]) == 0


def test_parity_watchdog_detects_mismatch():
    paper_sig = {"symbol": "XAUUSD", "bias_1d": "BULLISH", "requested_entry": 2400.0, "stop_loss": 2390.0, "take_profit": 2430.0}
    shadow_sig = {"symbol": "XAUUSD", "bias_1d": "BEARISH", "requested_entry": 2400.0, "stop_loss": 2390.0, "take_profit": 2430.0}
    
    res = XAUUSDParityWatchdog.audit_parity(paper_sig, shadow_sig)
    assert res["is_parity_clean"] is False
    assert res["status"] == "PARITY BREACH"
    assert len(res["mismatches"]) > 0

    # Ensure a CRITICAL alert was logged to XAUUSDAlertEngine
    events = XAUUSDAlertEngine.get_events(severity_filter="CRITICAL")
    assert any(e["event_type"] == "PAPER_SHADOW_DESYNC" for e in events)


def test_data_integrity_watchdog():
    res = XAUUSDDataIntegrityWatchdog.audit_data_integrity()
    assert "is_clean" in res
    assert res["status"] in ["PASS", "DATA INTEGRITY WARNING"]
    assert "feed_status" in res


def test_research_health_matrix_structure():
    pillars = ResearchHealthMatrix.evaluate_research_health("PAPER")
    assert len(pillars) == 8
    components = [p["component"] for p in pillars]
    assert "Data Integrity" in components
    assert "Strategy Integrity" in components
    assert "Dataset Isolation" in components
    assert "Paper/Shadow Parity" in components
    assert "Statistical Reliability" in components
    assert "Execution Quality" in components
    assert "Distribution Stability" in components
    assert "Drawdown Health" in components


def test_live_trading_safety_barrier_remains_blocked():
    with pytest.raises(Exception) as exc_info:
        LiveTradingSafetyBarrier.assert_live_automation_disabled()
    assert "CRITICAL GOVERNANCE VIOLATION" in str(exc_info.value)
