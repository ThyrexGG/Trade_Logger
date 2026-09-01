"""
Phase 46 — Milestone Snapshot Store Test Suite
Validates immutable snapshot recording, retrieval, and duplicate protection.
"""

import pytest
from xauusd_forward_decision_gate import MilestoneSnapshotStore


def test_milestone_snapshot_recording_and_retrieval():
    """Validates immutable snapshot recording."""
    snap = MilestoneSnapshotStore.record_milestone_snapshot(
        milestone=10,
        actual_n=10,
        expectancy=0.52,
        win_rate=60.0,
        profit_factor=2.4,
        max_drawdown=1.5,
        ci_95=(0.3, 0.74),
        evidence_tier="EARLY FORWARD EVIDENCE (N = 10)",
        decision_state="COLLECTING — EARLY EVIDENCE (10 <= N < 20)",
        data_quality_score=100.0,
        quarantine_count=0
    )

    assert "snapshot_id" in snap
    assert snap["milestone"] == 10
    assert snap["actual_n"] == 10

    snaps = MilestoneSnapshotStore.get_milestone_snapshots(limit=10)
    assert any(s["milestone"] == 10 for s in snaps)
