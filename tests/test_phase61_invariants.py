# -*- coding: utf-8 -*-
"""
Phase 61 - Test System Invariants: Dataset Isolation, Unpooled Baselines & Non-Causal Attribution
"""
import pytest
from xauusd_forward_statistical_monitoring import (
    FROZEN_CONTRACT_HASH,
    HISTORICAL_BASELINE
)
from xauusd_market_conditions import FROZEN_CONTRACT_HASH as COND_HASH


def test_dual_contract_hash_agreement():
    """Verify agreement across contract monitoring modules."""
    assert FROZEN_CONTRACT_HASH == COND_HASH
    assert len(FROZEN_CONTRACT_HASH) == 64


def test_unpooled_historical_holdout_values():
    """Verify historical benchmark metrics are exact and unmutated."""
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52
