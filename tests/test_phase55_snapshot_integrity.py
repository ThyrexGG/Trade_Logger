"""
Phase 55 — Tests for Immutable Edge Snapshot Database & SHA-256 Fingerprints
"""

import pytest
from datetime import datetime, timezone
from asset_edge_intelligence import AssetEdgeIntelligenceEngine


def test_record_and_retrieve_edge_snapshot():
    snapshot = AssetEdgeIntelligenceEngine.evaluate_asset_edge("XAUUSD")
    snap_id = AssetEdgeIntelligenceEngine.record_snapshot(snapshot)
    assert snap_id == snapshot["snapshot_id"]

    history = AssetEdgeIntelligenceEngine.get_historical_snapshots("XAUUSD", limit=5)
    assert len(history) > 0
    latest = history[0]
    assert latest["snapshot_id"] == snap_id
    assert latest["symbol"] == "XAUUSD"
    assert latest["payload_fingerprint"] == snapshot["payload_fingerprint"]
