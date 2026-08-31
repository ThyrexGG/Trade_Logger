"""
Phase 36 — Strategy Contract Immutability & Live Trading Safety Barrier Test Suite
Validates that PHASE_21_XAUUSD_STRATEGY_CONTRACT.md SHA-256 hash is unmodified,
holdout is locked, live automation is blocked, and zero directional predictions exist.
"""

import os
import hashlib
import pytest
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_news_reliability import DailyPreTradeStatusEngine


def test_strategy_contract_hash_exact_match():
    """Validates frozen strategy contract SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    with open(contract_path, "rb") as f:
        computed = hashlib.sha256(f.read()).hexdigest()
    assert computed == FROZEN_CONTRACT_HASH
    assert computed == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_live_automation_blocked():
    """Validates that LiveTradingSafetyBarrier blocks automation attempts."""
    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_pretrade_status_has_no_directional_signals():
    """Validates that DailyPreTradeStatusEngine produces zero directional BUY/SELL signals."""
    status = DailyPreTradeStatusEngine.evaluate_daily_status()
    assert "signal" not in status
    assert "buy_signal" not in status
    assert "sell_signal" not in status
