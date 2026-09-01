"""
TradeLogger Phase 59 — Safety & Fail-Closed Invariant Tests
===========================================================
Validates that performance optimizations did NOT alter the frozen strategy contract hash,
did NOT enable live execution, and maintain non-directional contextual outputs.
"""

import os
import hashlib
import pytest
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from market_intelligence_scanner import MarketScannerEngine
from cross_asset_regime_engine import CrossAssetRegimeEngine
from market_intelligence_command_center import UnifiedMarketIntelligenceAggregator


def test_frozen_strategy_contract_hash_phase59():
    """Verify byte-exact strategy contract hash."""
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)
    with open(contract_path, "rb") as f:
        content = f.read().replace(b"\r\n", b"\n")
        computed = hashlib.sha256(content).hexdigest()
    EXPECTED_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert FROZEN_CONTRACT_HASH == EXPECTED_HASH
    assert computed == EXPECTED_HASH


def test_live_execution_fail_closed_phase59():
    """Verify live trading and broker transmission cannot be invoked from intelligence snapshots."""
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    assert not hasattr(snap, "execute_live_order")
    assert not hasattr(snap, "send_broker_order")
    assert not hasattr(snap, "place_order")


def test_contextual_only_outputs_phase59():
    """Verify optimized engines never emit execution commands."""
    forbidden_terms = {"BUY", "SELL", "LONG", "SHORT", "ENTRY", "TRADE NOW"}
    
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    
    # Check regime
    assert snap.regime_snapshot.primary_regime not in forbidden_terms
    assert snap.regime_snapshot.secondary_regime not in forbidden_terms
    
    # Check ranked assets
    for r in snap.ranked_assets:
        ctx_state = r.get("context_state") if isinstance(r, dict) else r.context_state
        assert ctx_state not in forbidden_terms
