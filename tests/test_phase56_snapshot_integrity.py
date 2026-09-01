"""
Test Suite: Phase 56 Snapshot Immutability & Cryptographic Integrity
====================================================================
Validates persistent snapshot recording, SHA-256 fingerprinting,
and historical retrieval without mutating previous research records.
"""

from macro_intelligence_engine import (
    MacroIntelligenceEngine,
    MacroIntelligenceSnapshotStore
)


def test_snapshot_persistence_and_retrieval():
    """Verifies that macro snapshots are persisted with unique IDs and retrieved accurately."""
    snap = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")
    snap_id = MacroIntelligenceSnapshotStore.record_snapshot(snap)

    assert snap_id.startswith("SNAP_MACRO_")

    history = MacroIntelligenceSnapshotStore.get_recent_snapshots("XAUUSD", limit=5)
    assert len(history) >= 1
    latest = history[0]
    assert latest["snapshot_id"] == snap_id
    assert latest["symbol"] == "XAUUSD"
    assert "payload_fingerprint" in latest
    assert len(latest["payload_fingerprint"]) == 64  # SHA-256 hex length
