"""
Unit tests for Phase 28 Evidence Milestone Engine.
Verifies milestone progression, remaining trade calculations, and reliability tiers.
"""

from xauusd_evidence_milestones import EvidenceMilestoneEngine


def test_milestone_progression_calculations():
    # Test N = 10
    res_10 = EvidenceMilestoneEngine.evaluate_milestones(current_n=10)
    assert res_10["current_tier"] == "INSUFFICIENT DATA"
    assert res_10["next_milestone_target"] == 30
    assert res_10["next_milestone_remaining"] == 20
    assert "Stage 1" in res_10["next_milestone_stage"]

    # Test N = 35
    res_35 = EvidenceMilestoneEngine.evaluate_milestones(current_n=35)
    assert res_35["current_tier"] == "LIMITED SAMPLE"
    assert res_35["next_milestone_target"] == 50
    assert res_35["next_milestone_remaining"] == 15
    assert "Stage 2" in res_35["next_milestone_stage"]

    # Test N = 67
    res_67 = EvidenceMilestoneEngine.evaluate_milestones(current_n=67)
    assert res_67["current_tier"] == "MODERATE SAMPLE"
    assert res_67["next_milestone_target"] == 75
    assert res_67["next_milestone_remaining"] == 8

    # Test N = 100
    res_100 = EvidenceMilestoneEngine.evaluate_milestones(current_n=100)
    assert res_100["current_tier"] == "STRONG EVIDENCE"
    assert res_100["next_milestone_target"] == 125
    assert res_100["next_milestone_remaining"] == 25


def test_all_milestones_have_unknowns_and_meaning():
    res = EvidenceMilestoneEngine.evaluate_milestones(current_n=42)
    for m in res["milestones"]:
        assert len(m["what_remains_unknown"]) > 10
        assert len(m["human_meaning"]) > 10
        assert m["pct_completion"] >= 0.0
        assert "target_n" in m
