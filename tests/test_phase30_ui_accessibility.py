"""
Phase 30 — UI Accessibility & Ungated Research Lab Tests
Validates that the XAUUSD Forward Validation Center is reachable directly
without requiring any generic backtest execution, renders gracefully in low-data states,
and provides clear explainable metrics.
"""

import pandas as pd
import pytest
from xauusd_forward_monitor import XAUUSDForwardMonitor
from xauusd_evidence_milestones import EvidenceMilestoneEngine
from xauusd_review_readiness import ReviewReadinessEngine
from xauusd_research_decision_audit import ResearchDecisionAuditEngine
from xauusd_forward_evidence import (
    ForwardEvidenceAnalyzer,
    ForwardHistoricalComparator,
    ForwardEvidenceScorer,
    ResearchDecisionStateClassifier
)


def test_forward_validation_runs_independently():
    """Confirms forward validation telemetry generates without requiring generic edge audit."""
    summary = XAUUSDForwardMonitor.get_forward_summary(mode="PAPER")
    assert isinstance(summary, dict)
    assert "trades_N" in summary
    assert "expectancy_r" in summary
    assert "max_drawdown_r" in summary
    assert "sample_tier" in summary
    assert XAUUSDForwardMonitor.HISTORICAL_BASELINE["expectancy_r"] == pytest.approx(0.637, abs=1e-3)


def test_empty_and_low_data_state_handling():
    """Confirms low-data states (<30 observations) return honest uncertainty messaging."""
    # Test with 0 observations
    empty_stats = ForwardEvidenceAnalyzer.calculate_core_statistics([])
    assert empty_stats["trades_n"] == 0
    assert empty_stats["expectancy_r"] == 0.0
    assert empty_stats["evidence_tier"] == "INSUFFICIENT DATA"

    # Test milestone engine at N=0
    milestones = EvidenceMilestoneEngine.evaluate_milestones(0)
    assert milestones["current_tier"] == "INSUFFICIENT DATA"
    assert milestones["next_milestone_target"] == 30
    assert milestones["next_milestone_remaining"] == 30

    # Test review readiness at low N
    readiness = ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
    assert readiness["total_items"] == 18
    assert "checklist" in readiness
    assert "verdict" in readiness


def test_research_decision_synthesis_accessibility():
    """Confirms active research decision synthesis is immediately callable."""
    dec = ResearchDecisionAuditEngine.synthesize_current_decision(mode="PAPER")
    assert isinstance(dec, dict)
    assert "decision_state" in dec
    assert "current_stage" in dec
    assert "reasons" in dec
    assert len(dec["reasons"]) >= 1
    assert "unresolved_uncertainties" in dec
    assert "recommended_next_action" in dec


def test_historical_comparator_isolation():
    """Confirms ForwardHistoricalComparator isolates holdout baseline without pooling."""
    core_stats = ForwardEvidenceAnalyzer.calculate_core_statistics([0.5, 1.2, -1.0, 3.0])
    comp = ForwardHistoricalComparator.compare_against_holdout(core_stats)

    assert comp["hist_expectancy"] == pytest.approx(0.637, abs=1e-3)
    assert "consistency_band" in comp
    assert "explanation" in comp
