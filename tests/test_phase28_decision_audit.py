"""
Unit tests for Phase 28 Research Decision Audit Engine.
Verifies immutable decision records, synthesis rationale, and historical logging.
"""

from xauusd_research_decision_audit import ResearchDecisionAuditEngine


def test_synthesize_and_record_decision():
    audit_data = ResearchDecisionAuditEngine.synthesize_current_decision(mode="PAPER")

    assert "decision_state" in audit_data
    assert "current_stage" in audit_data
    assert "reasons" in audit_data
    assert len(audit_data["reasons"]) >= 1
    assert "unresolved_uncertainties" in audit_data
    assert "recommended_next_action" in audit_data

    audit_id = ResearchDecisionAuditEngine.record_audit_decision(audit_data)
    assert audit_id.startswith("AUDIT_")

    history = ResearchDecisionAuditEngine.get_audit_history(limit=5)
    assert len(history) >= 1
    assert history[0]["audit_id"] == audit_id
