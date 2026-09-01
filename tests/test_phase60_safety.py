# -*- coding: utf-8 -*-
"""
Phase 60 - Test Safety Invariants, Live Barriers & Dataset Isolation
"""
import pytest
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_forward_statistical_monitoring import HISTORICAL_BASELINE, FROZEN_CONTRACT_HASH as MON_HASH
import database


def test_strategy_contract_hash_unbroken():
    """Verify that all subsystems reference the byte-exact immutable contract hash."""
    expected_hash = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert FROZEN_CONTRACT_HASH == expected_hash
    assert MON_HASH == expected_hash


def test_historical_holdout_baseline_integrity():
    """Verify that holdout benchmark N=82 is preserved without pooling or mutation."""
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52


def test_live_execution_fail_closed():
    """Verify that live execution is permanently blocked and automation is disabled."""
    live_auto = database.get_setting("LIVE_AUTOMATION_ENABLED", "0")
    assert str(live_auto).lower() in ["0", "false", "off", "none", ""]
