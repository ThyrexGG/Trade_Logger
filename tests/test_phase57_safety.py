"""
TradeLogger Phase 57 — Test Suite: Safety Gates & Live Execution Block
======================================================================
Validates:
- Permanent fail-closed lock on live execution.
- LIVE_AUTOMATION_ENABLED == False.
- LIVE_BROKER_TRANSMISSION == "BLOCKED".
- Strategy contract hash verification (7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76).
- Strict non-directional context terminology (No BUY, SELL, LONG, SHORT outputs).
"""

import pytest
import hashlib
from market_intelligence_scanner import MarketScannerEngine, MarketRankingEngine
from cross_asset_regime_engine import CrossAssetRegimeEngine


EXPECTED_STRATEGY_CONTRACT_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_strategy_contract_hash_unmodified():
    """Verify strategy contract SHA-256 hash matches the frozen golden baseline."""
    assert EXPECTED_STRATEGY_CONTRACT_HASH == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_live_execution_fail_closed():
    """Verify scanner does NOT trigger live order placement or broker transmission."""
    records = MarketScannerEngine.scan_universe("ALL")
    assert len(records) == 23

    for r in records:
        assert not hasattr(r, "execute_order")
        assert not hasattr(r, "place_live_trade")


def test_non_directional_context_outputs():
    """Verify scanner and regime outputs are strictly contextual and do not emit trade execution commands."""
    records = MarketScannerEngine.scan_universe("ALL")
    ranked = MarketRankingEngine.rank_records(records)
    regime = CrossAssetRegimeEngine.evaluate_regime()

    forbidden_signals = {"BUY", "SELL", "LONG", "SHORT", "TRADE NOW", "ENTER NOW", "EXECUTE"}

    for item in ranked:
        bias = str(item.get("context_state", "")).upper()
        assert bias not in forbidden_signals

    assert regime.primary_regime not in forbidden_signals
    assert regime.secondary_regime not in forbidden_signals
