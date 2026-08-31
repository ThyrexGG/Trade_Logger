"""
Phase 38 — News Snapshot Store & Mutation Versioning Test Suite
Validates immutable snapshot storage, SHA-256 fingerprinting, and mutation detection without overwriting baseline data.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_news_snapshot_store import NewsSnapshotStore, CalendarMutationDetector


def test_store_and_retrieve_snapshot():
    """Validates storing an immutable snapshot and retrieving it by target date."""
    target_dt = date(2026, 9, 1)
    res = NewsSnapshotStore.store_snapshot(target_dt)

    assert isinstance(res, dict)
    assert res["status"] in ["SNAPSHOT_STORED", "EXISTING_UNMODIFIED"]
    assert "snapshot_id" in res
    assert "fingerprint" in res
    assert len(res["fingerprint"]) == 64

    # Retrieve snapshots
    snaps = NewsSnapshotStore.get_snapshots_for_date(target_dt)
    assert len(snaps) >= 1
    assert any(s["snapshot_id"] == res["snapshot_id"] for s in snaps)


def test_unmodified_calendar_mutation_check():
    """Validates that unchanged calendar data reports CALENDAR DATA UNCHANGED."""
    target_dt = date(2026, 9, 2)
    
    # Store initial baseline
    NewsSnapshotStore.store_snapshot(target_dt)

    from xauusd_news_history_audit import HistoricalContextReconstructor
    events = HistoricalContextReconstructor._reconstruct_events(target_dt, datetime.now(timezone.utc))

    mut_res = CalendarMutationDetector.detect_mutations(target_dt, events)
    assert isinstance(mut_res, dict)
    assert mut_res["mutation_detected"] is False
    assert mut_res["status"] == "CALENDAR DATA UNCHANGED"


def test_calendar_mutation_detected_upon_change():
    """Validates that altered event data triggers CALENDAR SNAPSHOT CHANGED."""
    target_dt = date(2026, 9, 3)
    
    # Store initial baseline
    NewsSnapshotStore.store_snapshot(target_dt)
    
    # Modified event payload
    mutated_events = [
        {
            "event_id": "EVT_MUTATED_001",
            "event_name": "Altered Release Data",
            "currency": "USD",
            "impact": "HIGH",
            "scheduled_timestamp": "2026-09-03T12:30:00Z",
            "forecast": "150K",
            "previous": "175K",
            "actual": "220K"
        }
    ]

    mut_res = CalendarMutationDetector.detect_mutations(target_dt, mutated_events)
    assert mut_res["mutation_detected"] is True
    assert mut_res["status"] == "CALENDAR SNAPSHOT CHANGED"
    assert len(mut_res["mutations"]) >= 1
