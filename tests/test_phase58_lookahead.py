"""
Phase 58 — Tests for Lookahead Protection in Command Center
"""

import pytest
from datetime import datetime, timezone, timedelta
from market_intelligence_command_center import UnifiedMarketIntelligenceAggregator


def test_command_center_respects_as_of():
    dt_past = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state(as_of=dt_past)

    assert snap.as_of == dt_past
    # All records evaluated at as_of
    for r in snap.ranked_assets:
        rec_ts = r.get("snapshot_timestamp") if isinstance(r, dict) else r.snapshot_timestamp
        rec_dt = datetime.fromisoformat(rec_ts)
        assert rec_dt <= dt_past + timedelta(seconds=5)
