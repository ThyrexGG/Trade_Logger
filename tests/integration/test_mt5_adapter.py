"""
Real Broker Integration Tests for MetaTrader 5 Adapter (Phase 12B)
Safe, read-only verification checks.
If MT5 terminal or credentials are not reachable, marks test as BLOCKED with clear reason.
NEVER places real trades automatically.
"""

import pytest
from broker_adapter import MT5Adapter


def test_mt5_real_connection_and_read_only_checks():
    """
    Executes safe read-only checks against MT5:
    1. Health check & latency ping
    2. Account state query (balance, equity, margin)
    3. Open positions list
    """
    adapter = MT5Adapter()
    health = adapter.health_check()

    if not health.connected:
        pytest.skip(
            f"BLOCKED: MT5 live integration check blocked because MT5 terminal is disconnected or unavailable: {health.error_message}"
        )

    # If connected, verify authoritative account state
    account = adapter.get_account_state()
    assert account.status == "HEALTHY", f"MT5 account state status: {account.status}"
    assert account.balance >= 0.0
    assert account.equity >= 0.0

    # Verify positions retrieval
    positions = adapter.get_open_positions()
    assert isinstance(positions, list)
