"""
Real Broker Integration Tests for Capital.com Adapter (Phase 12B)
Safe, read-only verification checks.
If Capital.com API session or credentials are not reachable, marks test as BLOCKED with clear reason.
NEVER places real trades automatically.
"""

import pytest
from broker_adapter import CapitalComAdapter


def test_capitalcom_real_connection_and_read_only_checks():
    """
    Executes safe read-only checks against Capital.com:
    1. Health check & latency ping
    2. Account state query (balance, equity, free margin)
    3. Open positions list
    """
    adapter = CapitalComAdapter()
    health = adapter.health_check()

    if not health.connected:
        pytest.skip(
            f"BLOCKED: Capital.com live integration check blocked because API session is inactive or unreachable: {health.error_message}"
        )

    # If connected, verify authoritative account state
    account = adapter.get_account_state()
    assert account.status == "HEALTHY", f"Capital.com account state status: {account.status}"
    assert account.balance >= 0.0
    assert account.equity >= 0.0

    # Verify positions retrieval
    positions = adapter.get_open_positions()
    assert isinstance(positions, list)
