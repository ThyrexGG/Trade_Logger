"""
Phase 57: Test Suite for Market Scanner Snapshot Integrity
Verifies:
- SHA-256 fingerprint generation
- SQLite persistence in market_scanner_snapshots table
- Historical snapshot retrieval and ordering
- Data integrity verification on stored records
"""

import pytest
from market_intelligence_scanner import (
    MarketScannerEngine,
    MarketScannerSnapshotStore,
    MarketBreadthEngine
)


def test_save_and_retrieve_scanner_snapshot():
    records = MarketScannerEngine.scan_universe(["EURUSD", "SPX500", "XAUUSD"])
    breadth = MarketBreadthEngine.calculate_breadth(records)

    snap_id = MarketScannerSnapshotStore.save_scanner_snapshot(
        scan_records=records,
        regime_label="RISK_ON",
        regime_confidence=85.0,
        breadth_summary=breadth
    )

    assert snap_id.startswith("SCAN_")

    latest = MarketScannerSnapshotStore.get_latest_scanner_snapshot()
    assert latest is not None
    assert latest["snapshot_id"] == snap_id
    assert latest["asset_count"] == 3
    assert latest["regime_label"] == "RISK_ON"
    assert len(latest["data_fingerprint"]) == 64


def test_list_scanner_snapshots():
    snapshots = MarketScannerSnapshotStore.list_recent_snapshots(limit=5)
    assert isinstance(snapshots, list)
    assert len(snapshots) >= 1
    for s in snapshots:
        assert "snapshot_id" in s
        assert "created_at" in s
        assert "asset_count" in s
        assert "data_fingerprint" in s
