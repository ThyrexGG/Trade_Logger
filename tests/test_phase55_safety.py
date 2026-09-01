"""
Phase 55 — Tests for Strategy Contract Immutability & Fail-Closed Safety
"""

import os
import hashlib
import pytest
from xauusd_market_conditions import FROZEN_CONTRACT_HASH


def test_strategy_contract_hash_phase55():
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)
    with open(contract_path, "rb") as f:
        content = f.read().replace(b"\r\n", b"\n")
        computed = hashlib.sha256(content).hexdigest()
    assert computed == FROZEN_CONTRACT_HASH
    assert computed == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
