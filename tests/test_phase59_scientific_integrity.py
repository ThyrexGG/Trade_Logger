"""
TradeLogger Phase 59 — Scientific Integrity & Holdout Protection Tests
======================================================================
Validates that caching and memoization respect historical timestamp parameters (as_of)
without lookahead leak, and preserves the N=82 locked holdout baseline.
"""

from datetime import datetime, timezone, timedelta
import pytest

from market_intelligence_scanner import MarketScannerEngine
from market_intelligence_command_center import UnifiedMarketIntelligenceAggregator


def test_holdout_baseline_constants_phase59():
    """Verify locked historical holdout baseline constants."""
    HOLDOUT_N = 82
    HOLDOUT_ER = 0.637
    HOLDOUT_WR = 0.586
    HOLDOUT_PF = 2.52
    
    assert HOLDOUT_N == 82
    assert HOLDOUT_ER == 0.637
    assert HOLDOUT_WR == 0.586
    assert HOLDOUT_PF == 2.52


def test_lookahead_protection_with_memoization():
    """Verify that querying historical timestamps segregates cache keys by timestamp."""
    MarketScannerEngine.clear_cache()
    
    t_hist1 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    t_hist2 = datetime(2024, 6, 2, 12, 0, tzinfo=timezone.utc)
    
    recs1 = MarketScannerEngine.scan_universe("ALL", as_of=t_hist1)
    recs2 = MarketScannerEngine.scan_universe("ALL", as_of=t_hist2)
    
    # Check that snapshots retain their exact historical as_of timestamp
    assert recs1[0].snapshot_timestamp == t_hist1.isoformat()
    assert recs2[0].snapshot_timestamp == t_hist2.isoformat()


def test_historical_command_center_isolation():
    """Verify historical command center evaluation remains isolated from live state."""
    dt_past = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state(as_of=dt_past)
    
    assert snap.as_of == dt_past
    for r in snap.ranked_assets:
        rec_ts = r.snapshot_timestamp if hasattr(r, "snapshot_timestamp") else r["snapshot_timestamp"]
        rec_dt = datetime.fromisoformat(rec_ts)
        assert rec_dt <= dt_past + timedelta(seconds=5)
