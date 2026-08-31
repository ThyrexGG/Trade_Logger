"""
Phase 41 — Daily Snapshot & Delta Engine Test Suite
Validates immutable snapshot storage, SHA-256 fingerprinting, and delta calculation between days.
"""

from datetime import datetime, timezone, date, timedelta
import pytest
from xauusd_evidence_reproducibility import (
    ImmutableDailySnapshotStore,
    SnapshotDeltaEngine,
)


def test_create_and_retrieve_daily_snapshot():
    """Validates creation, fingerprinting, and persistence of daily snapshots."""
    target_dt = date(2026, 9, 1)
    res = ImmutableDailySnapshotStore.create_and_store_snapshot(target_dt)

    assert isinstance(res, dict)
    assert "snapshot_id" in res
    assert len(res["snapshot_fingerprint"]) == 64
    assert res["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"

    # Retrieve
    retrieved = ImmutableDailySnapshotStore.get_snapshot(target_dt)
    assert retrieved is not None
    assert retrieved["snapshot_fingerprint"] == res["snapshot_fingerprint"]


def test_snapshot_delta_engine_comparison():
    """Validates comparison across sequential snapshots."""
    snap1 = {
        "snapshot_date": "2026-09-01",
        "snapshot_fingerprint": "AAA_FP",
        "payload": {"paper_observations_count": 5, "data_quality_report": {"average_quality_score": 90.0}}
    }
    snap2 = {
        "snapshot_date": "2026-09-02",
        "snapshot_fingerprint": "BBB_FP",
        "payload": {"paper_observations_count": 8, "data_quality_report": {"average_quality_score": 95.0}}
    }

    delta = SnapshotDeltaEngine.compare_snapshots(snap1, snap2)
    assert delta["observation_delta"] == 3
    assert delta["quality_delta"] == 5.0
    assert delta["fingerprint_changed"] is True
    assert delta["verdict"] == "DATASET EXPANDED"
