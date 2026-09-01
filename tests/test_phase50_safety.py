"""
Phase 50 — Tests for Safety Invariants & Immutability
"""

import hashlib
import os
import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_forward_end_to_end_proof import Phase50SafetyBarrier
from xauusd_forward_statistical_monitoring import HISTORICAL_BASELINE


def test_strategy_contract_hash_exact_match():
    """Validates byte-for-byte immutability of Strategy Contract SHA-256."""
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    if os.path.exists(contract_path):
        with open(contract_path, "rb") as f:
            content = f.read().replace(b"\r\n", b"\n")
            actual_hash = hashlib.sha256(content).hexdigest()
        assert actual_hash == FROZEN_CONTRACT_HASH
        assert actual_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_historical_baseline_locked():
    """Validates that historical baseline constants are immutable."""
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52
    assert HISTORICAL_BASELINE["max_drawdown_r"] == 4.00


def test_safety_barrier_fail_closed():
    """Validates that live broker transmission is permanently blocked."""
    safety = Phase50SafetyBarrier.verify_safety_barrier()
    assert safety["live_automation_enabled"] is False
    assert safety["broker_transmission"] == "BLOCKED"
