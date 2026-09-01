"""
Phase 54 — Tests for Frozen Strategy Contract & Live Automation Lock
"""

import os
import hashlib
import pytest
from xauusd_forward_statistical_monitoring import FROZEN_CONTRACT_HASH


def test_frozen_strategy_contract_hash_phase54():
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)
    with open(contract_path, "rb") as f:
        content = f.read().replace(b"\r\n", b"\n")
        computed = hashlib.sha256(content).hexdigest()
    assert computed == FROZEN_CONTRACT_HASH
    assert computed == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
