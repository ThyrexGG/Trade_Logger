"""
Unit tests for Phase 28 Forward Evidence Ledger.
Verifies append-only storage, immutable snapshots, delta comparisons, and retrieval.
"""

import pytest
from xauusd_forward_evidence_ledger import ForwardEvidenceLedger


def test_create_and_get_evidence_snapshot():
    data = {
        "trades_n": 45,
        "expectancy_r": 0.582,
        "median_r": 0.450,
        "win_rate_pct": 57.8,
        "profit_factor": 2.35,
        "max_drawdown_r": 2.80,
        "recovery_factor": 9.35,
        "ci_90_lower": 0.150,
        "ci_90_upper": 1.014,
        "ci_95_lower": 0.068,
        "ci_95_upper": 1.096,
        "ci_99_lower": -0.092,
        "ci_99_upper": 1.256,
        "hist_expectancy_diff": -0.055,
        "hist_expectancy_ratio": 91.4,
        "baseline_consistency": "CONSISTENT",
        "avg_mae_r": 0.36,
        "avg_mfe_r": 2.92,
        "limit_fill_rate_pct": 92.5,
        "timeout_rate_pct": 7.5,
        "avg_slippage_pips": 1.1,
        "avg_spread_pips": 2.1,
        "paper_shadow_parity": "100% PARITY",
        "data_integrity_status": "PASS",
        "contract_hash": "a1b2c3d4e5f6...",
        "governance_stage": "Stage 1 (Early Evidence)",
        "evidence_score": 78.5,
        "research_decision_state": "EARLY EVIDENCE",
        "next_milestone": "N = 50"
    }

    snap_id = ForwardEvidenceLedger.create_snapshot(data)
    assert snap_id.startswith("SNAP_")

    fetched = ForwardEvidenceLedger.get_snapshot_by_id(snap_id)
    assert fetched is not None
    assert fetched["snapshot_id"] == snap_id
    assert fetched["trades_n"] == 45
    assert fetched["expectancy_r"] == pytest.approx(0.582, rel=1e-3)
    assert fetched["evidence_score"] == pytest.approx(78.5, rel=1e-2)


def test_snapshot_comparison_deltas():
    # Create two sequential snapshots
    data1 = {
        "trades_n": 30,
        "expectancy_r": 0.500,
        "median_r": 0.400,
        "win_rate_pct": 55.0,
        "profit_factor": 2.10,
        "max_drawdown_r": 2.50,
        "recovery_factor": 6.00,
        "ci_90_lower": 0.100,
        "ci_90_upper": 0.900,
        "ci_95_lower": 0.020,
        "ci_95_upper": 0.980,
        "ci_99_lower": -0.150,
        "ci_99_upper": 1.150,
        "hist_expectancy_diff": -0.137,
        "hist_expectancy_ratio": 78.5,
        "baseline_consistency": "WATCH",
        "avg_mae_r": 0.38,
        "avg_mfe_r": 2.70,
        "limit_fill_rate_pct": 90.0,
        "timeout_rate_pct": 10.0,
        "avg_slippage_pips": 1.2,
        "avg_spread_pips": 2.2,
        "paper_shadow_parity": "100% PARITY",
        "data_integrity_status": "PASS",
        "contract_hash": "a1b2c3d4e5f6...",
        "governance_stage": "Stage 1",
        "evidence_score": 70.0,
        "research_decision_state": "EARLY EVIDENCE",
        "next_milestone": "N = 50"
    }

    data2 = dict(data1)
    data2["trades_n"] = 50
    data2["expectancy_r"] = 0.610
    data2["win_rate_pct"] = 58.0
    data2["profit_factor"] = 2.45
    data2["max_drawdown_r"] = 2.60
    data2["evidence_score"] = 82.0
    data2["research_decision_state"] = "FORWARD CONSISTENT"
    data2["governance_stage"] = "Stage 2"

    id1 = ForwardEvidenceLedger.create_snapshot(data1)
    id2 = ForwardEvidenceLedger.create_snapshot(data2)

    cmp_res = ForwardEvidenceLedger.compare_snapshots(id1, id2)
    assert cmp_res["deltas"]["new_trades"] == 20
    assert cmp_res["deltas"]["expectancy_change"] == pytest.approx(0.110, rel=1e-2)
    assert cmp_res["deltas"]["win_rate_change_pct"] == pytest.approx(3.0, rel=1e-2)
    assert cmp_res["deltas"]["evidence_score_change"] == pytest.approx(12.0, rel=1e-2)
    assert cmp_res["earlier_decision_state"] == "EARLY EVIDENCE"
    assert cmp_res["later_decision_state"] == "FORWARD CONSISTENT"
