"""
Phase 35 — Safety Invariants, Immutability & Live Trading Lock Test Suite
Validates that Strategy Contract SHA-256 hash is unchanged, historical holdout remains locked,
live automation is disabled permanently, and zero BUY/SELL predictions are generated.
"""

import os
import hashlib
import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_daily_command_center import DailyTradingCommandEngine
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def test_strategy_contract_hash_exact_match():
    """Validates that PHASE_21_XAUUSD_STRATEGY_CONTRACT.md matches exact frozen SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)

    with open(contract_path, "rb") as f:
        computed_hash = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()

    assert computed_hash == FROZEN_CONTRACT_HASH
    assert computed_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_live_automation_permanently_blocked():
    """Validates that live trading barrier raises LiveAutomationBlockedException on breach attempt."""
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_command_center_has_no_directional_buy_sell_signals():
    """Validates that DailyTradingCommandEngine produces zero directional trade recommendations."""
    cmd = DailyTradingCommandEngine.get_command_center_payload("XAUUSD")
    assert "signal" not in cmd
    assert "buy_signal" not in cmd
    assert "sell_signal" not in cmd
    summary = cmd["what_this_means"].lower()
    assert "buy gold" not in summary
    assert "sell gold" not in summary
    assert "go long" not in summary
    assert "go short" not in summary
