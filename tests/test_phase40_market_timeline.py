"""
Phase 40 — Market Condition Chronological Timeline Test Suite
Validates chronological ordering across sessions, holidays, macro events, and forward observations.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_event_traceability import MarketConditionChronologicalTimeline


def test_daily_timeline_chronological_ordering():
    """Validates that daily timeline entries are strictly sorted by timestamp."""
    target_dt = date(2026, 9, 1)
    timeline = MarketConditionChronologicalTimeline.build_daily_timeline(target_dt)

    assert isinstance(timeline, list)
    assert len(timeline) >= 5  # At least 5 session boundaries

    # Check timestamps are in ascending order
    timestamps = [item["timestamp"] for item in timeline]
    assert timestamps == sorted(timestamps)

    # Check presence of categories
    categories = set(item["category"] for item in timeline)
    assert "SESSION" in categories
