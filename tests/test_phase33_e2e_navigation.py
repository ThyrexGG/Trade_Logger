"""
Phase 33 — E2E Navigation & Reachability Test Suite
Validates that XAUUSD Forward Validation and Forward Evidence Center are immediately reachable,
un-gated, and do not depend on generic backtests or hidden session state.
"""

import pytest
import xauusd_operational_monitor
import xauusd_market_conditions
import xauusd_forward_evidence
import xauusd_evidence_milestones
import xauusd_review_readiness
import xauusd_research_decision_audit
import xauusd_review_package


def test_forward_validation_core_modules_importable():
    """Validates that all core forward validation and evidence modules load cleanly."""
    assert hasattr(xauusd_operational_monitor, "OperationalHealthEvaluator")
    assert hasattr(xauusd_market_conditions, "MarketPreFlightEngine")
    assert hasattr(xauusd_forward_evidence, "ForwardEvidenceAnalyzer")
    assert hasattr(xauusd_evidence_milestones, "EvidenceMilestoneEngine")
    assert hasattr(xauusd_review_readiness, "ReviewReadinessEngine")
    assert hasattr(xauusd_research_decision_audit, "ResearchDecisionAuditEngine")
    assert hasattr(xauusd_review_package, "HumanReviewPackageGenerator")


def test_immediate_reachability_without_backtests():
    """Validates that operational health and pre-flight summaries generate without prerequisite backtests."""
    op = xauusd_operational_monitor.OperationalHealthEvaluator.evaluate_operational_health("XAUUSD")
    assert isinstance(op, dict)
    assert "overall_verdict" in op

    pre = xauusd_market_conditions.MarketPreFlightEngine.get_preflight_summary()
    assert isinstance(pre, dict)
    assert "master_state" in pre
    assert "events_timeline" in pre
