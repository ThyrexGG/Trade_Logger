"""
Phase 30 — End-to-End Integration & Forward Validation Pipeline Verification
Validates the complete data flow: trade observation logging, telemetry generation,
evidence scoring, milestone evaluation, audit synthesis, review packaging, and health matrix.
"""

import pytest
import pandas as pd
from xauusd_forward_validator import XAUUSDForwardJournal
from xauusd_forward_monitor import XAUUSDForwardMonitor
from xauusd_continuous_monitor import XAUUSDContinuousMonitor
from xauusd_execution_quality import XAUUSDExecutionDiagnostics
from xauusd_drift_detector import XAUUSDDriftDetector
from xauusd_validation_gate import XAUUSDValidationGate
from xauusd_research_governance import ResearchIntegrityAuditor, WatchNextAdvisor, ResearchHealthMatrix
from xauusd_forward_evidence import ForwardEvidenceScorer, ResearchDecisionStateClassifier
from xauusd_evidence_milestones import EvidenceMilestoneEngine
from xauusd_review_readiness import ReviewReadinessEngine
from xauusd_research_decision_audit import ResearchDecisionAuditEngine
from xauusd_review_package import HumanReviewPackageGenerator
from xauusd_live_state_engine import XAUUSDLiveMTFStateEngine
import xauusd_forward_regime_coverage
import xauusd_forward_stability
import xauusd_forward_execution_stress
import xauusd_forward_drawdown_audit
import xauusd_forward_reproducibility


def test_complete_forward_validation_pipeline():
    """Validates that all Phase 20-29 engines execute in sequence without exceptions."""
    # 1. Summary & Telemetry
    fwd_summary = XAUUSDForwardMonitor.get_forward_summary(mode="PAPER")
    assert isinstance(fwd_summary, dict)

    cont_telemetry = XAUUSDContinuousMonitor.get_full_monitoring_telemetry(mode="PAPER")
    assert "cusum" in cont_telemetry

    # 2. Execution & Drift
    exec_quality = XAUUSDExecutionDiagnostics.run_execution_diagnostics(mode="PAPER")
    assert "fill_rate_pct" in exec_quality

    dist_drift = XAUUSDDriftDetector.evaluate_distribution_drift(mode="PAPER")
    assert "distribution_status" in dist_drift

    # 3. Gate & Integrity
    val_gate = XAUUSDValidationGate.evaluate_gate(mode="PAPER")
    assert "status" in val_gate

    integrity = ResearchIntegrityAuditor.evaluate_integrity()
    assert "all_passed" in integrity

    health = ResearchHealthMatrix.evaluate_research_health(mode="PAPER")
    assert len(health) >= 5

    # 4. Evidence & Milestones
    score = ForwardEvidenceScorer.calculate_evidence_score(mode="PAPER")
    assert 0.0 <= score["total_score"] <= 100.0

    state = ResearchDecisionStateClassifier.classify_state(mode="PAPER")
    assert "state" in state

    milestones = EvidenceMilestoneEngine.evaluate_milestones(fwd_summary.get("trades_N", 0))
    assert "current_tier" in milestones

    # 5. Readiness & Review Package
    readiness = ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
    assert "verdict" in readiness

    audit_decision = ResearchDecisionAuditEngine.synthesize_current_decision(mode="PAPER")
    assert "decision_state" in audit_decision

    review_pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    assert "package_id" in review_pkg
    assert "sections" in review_pkg
    assert len(review_pkg["sections"]) >= 20

    report_md = HumanReviewPackageGenerator.export_markdown_report(review_pkg)
    assert "# XAUUSD True MTF Strategy" in report_md

    # 6. Live MTF State
    live_mtf = XAUUSDLiveMTFStateEngine.get_complete_live_market_state("XAUUSD")
    assert "decision" in live_mtf
    assert "layer_1d" in live_mtf

    # 7. Regimes, Stability, Stress, Drawdown, Reproducibility
    paper_returns = [1.5, -1.0, 2.0, 0.5, -0.8]
    regime_cov = xauusd_forward_regime_coverage.RegimeCoverageEngine.evaluate_regime_coverage(mode="PAPER")
    assert "sessions" in regime_cov

    rolling_stab = xauusd_forward_stability.RollingStabilityEngine.evaluate_rolling_stability(paper_returns)
    assert "windows" in rolling_stab

    time_split = xauusd_forward_stability.RollingStabilityEngine.evaluate_time_split_stability(paper_returns)
    assert "periods" in time_split

    exec_stress = xauusd_forward_execution_stress.ExecutionStressAuditor.run_execution_stress_analysis(mode="PAPER")
    assert "slippage_stress" in exec_stress

    outcome_attr = xauusd_forward_execution_stress.ForwardOutcomeAttributor.attribute_outcomes(mode="PAPER")
    assert "items" in outcome_attr

    dd_audit = xauusd_forward_drawdown_audit.ForwardDrawdownAuditor.audit_drawdown(paper_returns)
    assert "current_drawdown_r" in dd_audit

    reprod_audit = xauusd_forward_reproducibility.ForwardReproducibilityAuditor.audit_reproducibility(mode="PAPER")
    assert "verdict" in reprod_audit

    fingerprint = xauusd_forward_reproducibility.ForwardDatasetFingerprinter.generate_fingerprint(mode="PAPER")
    assert "dataset_sha256" in fingerprint
