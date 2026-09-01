"""
Phase 49 — Tests for Safety Invariants & Immutability
"""

import hashlib
import os
import pytest
from xauusd_forward_statistical_monitoring import (
    FROZEN_CONTRACT_HASH,
    HISTORICAL_BASELINE,
    Phase49MonitoringFacade,
)


def test_strategy_contract_hash_exact_match():
    """Validates byte-for-byte immutability of Strategy Contract SHA-256."""
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    if os.path.exists(contract_path):
        with open(contract_path, "rb") as f:
            content = f.read().replace(b"\r\n", b"\n")
            actual_hash = hashlib.sha256(content).hexdigest()
        assert actual_hash == FROZEN_CONTRACT_HASH
        assert actual_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_historical_baseline_immutability():
    """Validates that historical baseline is permanently locked."""
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52
    assert HISTORICAL_BASELINE["max_drawdown_r"] == 4.00
    assert HISTORICAL_BASELINE["ci_95"] == [0.477, 0.817]


def test_live_automation_barrier():
    """Validates that live automation is permanently disabled and broker transmission is blocked."""
    state = Phase49MonitoringFacade.evaluate_full_forward_state()
    barrier = state["live_automation_barrier"]
    assert barrier["live_automation_enabled"] is False
    assert "BLOCKED" in barrier["broker_transmission"]
