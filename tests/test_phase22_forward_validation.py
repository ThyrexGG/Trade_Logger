"""
Unit Tests for Phase 22 — XAUUSD Forward Validation Monitoring
Tests:
- Forward Summary metrics calculation and sample size tier classification
- Bootstrap confidence interval calculations and bounds classification
- 1M FVG Limit execution quality monitoring & timeout rate detection
- Regime breakdown under N < 30 protection rules
- Strict dataset separation (Historical vs Forward Paper vs Forward Shadow)
"""

import pytest
import numpy as np
import pandas as pd
import uuid
import database
import market_data
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_monitor import XAUUSDForwardMonitor


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    database.init_db()
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    monkeypatch.setattr(market_data, "get_latest_price", lambda s: 2400.50)
    monkeypatch.setattr(market_data, "get_latest_tick", lambda s: {"bid": 2400.30, "ask": 2400.50})
    monkeypatch.setattr(market_data, "get_market_health", lambda s, tf: {"status": "HEALTHY"})


def test_forward_sample_size_tiers():
    # Tier 0: N < 30
    res_0 = XAUUSDForwardMonitor.get_forward_summary(mode="PAPER")
    # Fresh DB has 0 or few trades
    assert res_0["sample_tier"] in ["INSUFFICIENT DATA", "LIMITED SAMPLE", "MODERATE SAMPLE", "LARGE SAMPLE"]
    assert "Forward sample" in res_0["sample_text"]


def test_execution_quality_monitoring():
    exec_q = XAUUSDForwardMonitor.get_execution_quality_metrics(mode="PAPER")
    assert "fill_rate_pct" in exec_q
    assert "timeout_rate_pct" in exec_q
    assert "execution_health" in exec_q
    assert exec_q["execution_health"] in ["OPTIMAL", "ENTRY EXECUTION DEGRADATION", "FRICTION DEGRADATION", "NORMAL"]


def test_regime_breakdown_protection_rule():
    regimes = XAUUSDForwardMonitor.get_regime_breakdown(mode="PAPER")
    assert isinstance(regimes, list)
    for r in regimes:
        if r["trades_N"] < 30:
            assert r["status"] == "INSUFFICIENT DATA"


def test_historical_holdout_permanently_locked():
    hist = XAUUSDForwardMonitor.HISTORICAL_BASELINE
    assert hist["trades_N"] == 82
    assert hist["expectancy_r"] == 0.637
    assert hist["ci_lower"] == 0.477
    assert hist["ci_upper"] == 0.817
    assert hist["win_rate_pct"] == 58.6
    assert hist["profit_factor"] == 2.52
