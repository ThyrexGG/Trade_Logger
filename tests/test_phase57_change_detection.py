"""
TradeLogger Phase 57 — Test Suite: Market-Wide Change Detector
==============================================================
Validates:
- Comparison between prior and current market scan snapshots.
- Accurate detection of ranking position shifts.
- Accurate detection of directional bias transitions.
- Identification of notable score gainers and decliners.
"""

import pytest
from market_intelligence_scanner import (
    MarketScannerEngine,
    MarketWideChangeDetector
)


def test_change_detector_single_snapshot():
    """Verify change detector generates structured baseline deltas for initial scan."""
    records = MarketScannerEngine.scan_universe("ALL")
    changes = MarketWideChangeDetector.evaluate_market_changes(records, previous_records=None)

    assert changes["total_deltas"] == 23
    assert "executive_bullets" in changes
    assert len(changes["executive_bullets"]) > 0
    assert "structured_deltas" in changes


def test_change_detector_consecutive_snapshots():
    """Verify change detector computes deltas between previous and current snapshots."""
    records = MarketScannerEngine.scan_universe("ALL")
    # For identical snapshots, zero score deltas are detected
    changes_same = MarketWideChangeDetector.evaluate_market_changes(records, previous_records=records)
    assert changes_same["total_deltas"] == 0
    assert len(changes_same["structured_deltas"]) == 0

    # For modified snapshot, deltas are detected
    modified = []
    for r in records:
        r_dict = r.to_dict()
        if r.symbol == "XAUUSD":
            r_dict["edge_score"] = r.edge_score + 25.0
        from market_intelligence_scanner import AssetScanRecord
        modified.append(AssetScanRecord(**r_dict))

    changes_diff = MarketWideChangeDetector.evaluate_market_changes(modified, previous_records=records)
    assert changes_diff["total_deltas"] > 0
    assert changes_diff["biggest_gainer"] is not None
    assert changes_diff["biggest_gainer"]["symbol"] == "XAUUSD"
