"""
Phase 58 — Tests for Command Center Cryptographic Snapshot Ledger
"""

import pytest
from datetime import datetime, timezone
from cross_asset_regime_engine import MarketRegimeSnapshot
from market_intelligence_command_center import (
    CommandCenterSnapshotStore,
    UnifiedMarketIntelligenceAggregator
)


def test_command_center_snapshot_recording():
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    snap_id = CommandCenterSnapshotStore.record_snapshot(
        regime_snap=snap.regime_snapshot,
        breadth=snap.market_breadth,
        ranked_assets=snap.ranked_assets,
        what_matters=snap.what_matters,
        usd_strength=snap.macro_environment.get("usd_strength_score", 0.0),
        data_quality=snap.data_health.get("overall_quality_score", 90)
    )

    assert snap_id.startswith("CMD_SNAP_")

    history = CommandCenterSnapshotStore.get_recent_snapshots(limit=5)
    assert len(history) > 0
    latest = history[0]
    assert latest["snapshot_id"] == snap_id
    assert len(latest["payload_fingerprint"]) == 64
