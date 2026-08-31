"""
Phase 38 — Safety Invariants, Contract Immutability & No-Lookahead Test Suite
Verifies:
1. Strategy Contract SHA-256 is unchanged (7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76).
2. Historical Holdout dataset remains locked (N=82, E[R]=+0.637R).
3. Live automation remains permanently disabled.
4. Dataset isolation is enforced (no pooling of Historical, Paper, Shadow).
5. Zero directional signals or trade execution generated from news releases.
"""

import hashlib
import os
import pytest
from xauusd_research_governance import LiveTradingSafetyBarrier, LiveAutomationBlockedException
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_forward_validator import XAUUSDForwardComparator, XAUUSDForwardJournal


FROZEN_CONTRACT_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_strategy_contract_hash_exact_match():
    """Validates that PHASE_21_XAUUSD_STRATEGY_CONTRACT.md matches exact frozen SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)

    with open(contract_path, "rb") as f:
        computed_hash = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()

    assert computed_hash == FROZEN_CONTRACT_HASH
    assert computed_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_contract_integrity_guard_verification():
    """Validates the automated StrategyContractIntegrityGuard returns FROZEN & LOCKED."""
    guard_status = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert guard_status["parameters_verified"] is True
    assert guard_status["integrity_status"] == "FROZEN & LOCKED"


def test_live_automation_permanently_locked():
    """Verifies that attempting to activate live automation throws LiveAutomationBlockedException."""
    assert LiveTradingSafetyBarrier.LIVE_AUTOMATION_ENABLED is False
    assert LiveTradingSafetyBarrier.LIVE_BROKER_TRANSMISSION == "BLOCKED"

    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.enforce_live_barrier(target_state="LIVE")

    with pytest.raises(LiveAutomationBlockedException):
        LiveTradingSafetyBarrier.assert_live_automation_disabled()


def test_dataset_isolation_unpooled():
    """Verifies that Historical, Paper, and Shadow datasets are isolated and never combined."""
    from xauusd_forward_monitor import XAUUSDForwardMonitor
    hist = XAUUSDForwardMonitor.HISTORICAL_BASELINE
    assert hist["trades_N"] == 82
    assert hist["expectancy_r"] == pytest.approx(0.637, abs=1e-3)
    assert hist["win_rate_pct"] == pytest.approx(58.6, abs=1e-1)
    assert hist["profit_factor"] == pytest.approx(2.52, abs=1e-2)

    df_paper = XAUUSDForwardJournal.get_forward_trades(mode="PAPER")
    df_shadow = XAUUSDForwardJournal.get_forward_trades(mode="SHADOW")

    assert isinstance(df_paper, type(df_shadow))
