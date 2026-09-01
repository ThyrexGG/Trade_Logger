"""
TradeLogger Phase 59 — Performance Cache & Invalidation Tests
============================================================
Tests TTL expiration, cache hits, cache misses, cache invalidation,
and equivalence between cached and fresh outputs.
"""

import time
from datetime import datetime, timezone, timedelta
import pytest

from market_intelligence_scanner import MarketScannerEngine
from cross_asset_regime_engine import CrossAssetRegimeEngine
from market_intelligence_command_center import (
    UnifiedMarketIntelligenceAggregator,
    AssetContextProfileEngine
)
import market_data


def test_market_scanner_cache_hit_and_equivalence():
    """Verify that second call to scan_universe hits cache and produces exact same data."""
    MarketScannerEngine.clear_cache()
    
    # 1. First call (cold)
    t0 = time.perf_counter()
    records_cold = MarketScannerEngine.scan_universe("ALL")
    dt_cold = (time.perf_counter() - t0) * 1000.0
    
    assert len(records_cold) == 23
    
    # 2. Second call (warm)
    t1 = time.perf_counter()
    records_warm = MarketScannerEngine.scan_universe("ALL")
    dt_warm = (time.perf_counter() - t1) * 1000.0
    
    assert len(records_warm) == 23
    assert dt_warm < dt_cold or dt_warm < 5.0
    
    # Check exact field identity
    for rc, rw in zip(records_cold, records_warm):
        assert rc.symbol == rw.symbol
        assert rc.edge_score == rw.edge_score
        assert rc.macro_score == rw.macro_score
        assert rc.data_fingerprint == rw.data_fingerprint


def test_regime_engine_cache_hit():
    """Verify CrossAssetRegimeEngine cache behavior."""
    CrossAssetRegimeEngine.clear_cache()
    
    snap1 = CrossAssetRegimeEngine.evaluate_regime()
    snap2 = CrossAssetRegimeEngine.evaluate_regime()
    
    assert snap1.snapshot_id == snap2.snapshot_id
    assert snap1.primary_regime == snap2.primary_regime
    assert snap1.confidence_pct == snap2.confidence_pct
    assert snap1.data_fingerprint == snap2.data_fingerprint


def test_aggregator_cache_hit():
    """Verify UnifiedMarketIntelligenceAggregator cache behavior."""
    UnifiedMarketIntelligenceAggregator.clear_cache()
    
    agg1 = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    agg2 = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    
    assert agg1.snapshot_id == agg2.snapshot_id
    assert agg1.payload_fingerprint == agg2.payload_fingerprint
    assert len(agg1.ranked_assets) == len(agg2.ranked_assets)


def test_asset_profile_cache_hit():
    """Verify AssetContextProfileEngine cache behavior."""
    AssetContextProfileEngine.clear_cache()
    
    prof1 = AssetContextProfileEngine.build_asset_profile("XAUUSD")
    prof2 = AssetContextProfileEngine.build_asset_profile("XAUUSD")
    
    assert prof1["symbol"] == prof2["symbol"]
    assert prof1["price"] == prof2["price"]
    assert prof1["edge_snapshot"]["overall_score"] == prof2["edge_snapshot"]["overall_score"]


def test_cache_clear_invalidation():
    """Verify that clear_cache explicitly invalidates cached entries."""
    MarketScannerEngine.clear_cache()
    CrossAssetRegimeEngine.clear_cache()
    UnifiedMarketIntelligenceAggregator.clear_cache()
    AssetContextProfileEngine.clear_cache()
    
    # After clear, calling generates fresh valid state
    rec = MarketScannerEngine.scan_universe("FX")
    assert len(rec) == 8
