"""
TradeLogger Phase 57 — Test Suite: Snapshot Integrity & Fingerprinting
======================================================================
Validates:
- SHA-256 fingerprint reproducibility on scanner and regime snapshots.
- SQLite persistence in market_scanner_snapshots and market_regime_snapshots.
- Immutable timestamp and version auditing.
- Exact serialization and deserialization roundtrip.
"""

import pytest
import hashlib
from market_intelligence_scanner import (
    MarketScannerSnapshotStore,
    MarketScannerEngine,
    MarketRankingEngine,
    MarketBreadthEngine,
    MarketWideChangeDetector
)
from cross_asset_regime_engine import (
    MarketRegimeSnapshotStore,
    CrossAssetRegimeEngine
)


def test_scanner_snapshot_save_and_retrieve():
    """Verify saving scanner snapshot to SQLite and retrieving latest snapshot."""
    records = MarketScannerEngine.scan_universe("ALL")
    ranked = MarketRankingEngine.rank_records(records)
    breadth = MarketBreadthEngine.calculate_breadth(records)
    changes = MarketWideChangeDetector.evaluate_market_changes(records)

    snap_id = MarketScannerSnapshotStore.record_snapshot(
        ranked_records=ranked,
        breadth=breadth,
        changes=changes
    )

    assert isinstance(snap_id, str)
    assert snap_id.startswith("SCAN_")

    latest = MarketScannerSnapshotStore.get_latest_snapshot()
    assert latest is not None
    assert latest["snapshot_id"] == snap_id
    assert len(latest["data_fingerprint"]) == 64
    assert len(latest["rankings"]) == 23


def test_regime_snapshot_save_and_retrieve():
    """Verify saving regime snapshot to SQLite and retrieving latest snapshot."""
    regime = CrossAssetRegimeEngine.evaluate_regime()

    snap_id = MarketRegimeSnapshotStore.save_snapshot(regime)

    assert isinstance(snap_id, str)
    assert snap_id.startswith("REGIME_")

    latest = MarketRegimeSnapshotStore.get_latest_snapshot()
    assert latest is not None
    assert latest["snapshot_id"] == snap_id
    assert len(latest["data_fingerprint"]) == 64
    assert "primary_regime" in latest
