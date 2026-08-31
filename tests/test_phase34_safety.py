"""
Phase 34 — Safety Invariants, Strategy Contract Immutability & No Directional News Filters
Validates that Strategy Contract SHA-256 hash is unmodified, live trading is permanently disabled,
and news engine generates zero BUY/SELL predictions.
"""

import os
import hashlib
import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_daily_preflight import DailyPreFlightEngine
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


def test_daily_preflight_has_no_buy_sell_signals():
    """Validates that DailyPreFlightEngine produces zero directional trade recommendations."""
    pf = DailyPreFlightEngine.get_daily_preflight()
    assert "signal" not in pf
    assert "action_type" not in pf
    assert pf["master_state"] in [
        "NORMAL DAY", "CAUTION", "HIGH-IMPACT NEWS DAY", "HOLIDAY / REDUCED LIQUIDITY", "MAJOR MARKET CLOSURE", "NEWS DATA UNAVAILABLE"
    ]
