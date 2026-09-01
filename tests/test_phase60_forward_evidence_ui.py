# -*- coding: utf-8 -*-
"""
Phase 60 - Test Forward Evidence & Governance Cockpit UI Layering
"""
import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit
from xauusd_forward_statistical_monitoring import (
    HISTORICAL_BASELINE,
    FROZEN_CONTRACT_HASH
)


def test_forward_evidence_cockpit_state_payload():
    """Verify that cockpit state payload loads both Phase 49 and Phase 50 canonical outputs."""
    state = ForwardEvidenceCockpit.load_cockpit_state()
    assert state is not None
    assert "p49" in state
    assert "p50" in state
    assert "evaluated_at" in state


def test_locked_historical_baseline_constants():
    """Verify that the historical baseline constants are mathematically locked and unpooled."""
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52


def test_strategy_contract_hash_preservation():
    """Verify that the immutable Strategy Contract SHA-256 hash is preserved byte-exact."""
    expected_hash = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert FROZEN_CONTRACT_HASH == expected_hash
