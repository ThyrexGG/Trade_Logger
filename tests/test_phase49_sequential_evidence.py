"""
Phase 49 — Tests for Sequential Evidence Governance & Immutable Milestone Snapshots
"""

import pytest
from xauusd_forward_statistical_monitoring import (
    SequentialEvidenceGovernanceEngine,
    init_phase49_database,
)


def test_milestone_snapshot_persistence():
    """Validates immutable snapshot creation and persistence."""
    init_phase49_database()
    snap = SequentialEvidenceGovernanceEngine.record_milestone_snapshot(
        milestone_n=0,
        actual_n=0,
        metrics={"trades_n": 0, "expectancy_r": 0.0, "win_rate_pct": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0},
        decision_state="INSUFFICIENT EVIDENCE (N = 0)",
        alpha_state="INSUFFICIENT FORWARD EVIDENCE (N = 0)",
        dataset_fp="TEST_FP_HASH_123"
    )
    assert snap["status"] == "RECORDED"
    assert "snapshot_id" in snap
    assert "snapshot_fingerprint" in snap

    history = SequentialEvidenceGovernanceEngine.get_milestone_snapshots(limit=5)
    assert len(history) >= 1
    assert any(s["snapshot_id"] == snap["snapshot_id"] for s in history)
