# -*- coding: utf-8 -*-
"""
Phase 61 - Test Safety Barriers, Live Execution Gates & Dataset Isolation
"""
import pytest
import database
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_forward_statistical_monitoring import HISTORICAL_BASELINE


def test_frozen_contract_hash_integrity():
    """Verify byte-exact immutability of strategy contract hash."""
    expected = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert FROZEN_CONTRACT_HASH == expected


def test_live_automation_blocked_setting():
    """Verify database setting for live automation is disabled/blocked."""
    auto_val = database.get_setting("LIVE_AUTOMATION_ENABLED", "0")
    assert str(auto_val).lower() in ["0", "false", "off", "none", ""]


def test_holdout_baseline_integrity():
    """Verify locked historical holdout constants."""
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52
