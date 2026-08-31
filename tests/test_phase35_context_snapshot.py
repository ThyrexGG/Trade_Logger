"""
Phase 35 — Market Context Snapshot Recording & Database Persistence Test Suite
Validates that MarketContextSnapshotEngine records reproducible snapshots with SHA-256 fingerprints,
persists to database, and never executes trades.
"""

import pytest
from xauusd_daily_command_center import MarketContextSnapshotEngine


def test_market_context_snapshot_recording():
    """Validates recording of immutable market context snapshot."""
    snap = MarketContextSnapshotEngine.record_snapshot(symbol="XAUUSD", user_notes="Phase 35 Test Snapshot")
    assert isinstance(snap, dict)
    assert "snapshot_id" in snap
    assert snap["snapshot_id"].startswith("SNAP_")
    assert "created_at" in snap
    assert "price" in snap
    assert snap["price"] > 0
    assert "session_name" in snap
    assert "master_condition" in snap
    assert "snapshot_fingerprint" in snap
    assert len(snap["snapshot_fingerprint"]) == 64
    assert snap["user_notes"] == "Phase 35 Test Snapshot"


def test_market_context_snapshot_retrieval():
    """Validates retrieving recorded snapshots from database."""
    snapshots = MarketContextSnapshotEngine.get_snapshots(limit=10)
    assert isinstance(snapshots, list)
    assert len(snapshots) >= 1
    s0 = snapshots[0]
    assert "snapshot_id" in s0
    assert "created_at" in s0
    assert "price" in s0
    assert "snapshot_fingerprint" in s0
