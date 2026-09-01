"""
Test Suite: Phase 56 Macro Change Detector ("What Changed?")
============================================================
Validates snapshot delta calculation, shift tracking, executive bullet generation,
and regime transition detection.
"""

from macro_intelligence_engine import MacroIntelligenceEngine
from macro_change_detector import MacroChangeDetector


def test_what_changed_baseline():
    """Verifies change detector with baseline snapshot."""
    current_snap = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")
    res = MacroChangeDetector.evaluate_changes(current_snapshot=current_snap)

    assert "executive_bullets" in res
    assert len(res["executive_bullets"]) >= 3
    assert "structured_deltas" in res
    assert isinstance(res["regime_shift_detected"], bool)


def test_what_changed_with_previous_snapshot():
    """Verifies change detector with explicit previous snapshot."""
    current_snap = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")
    prev_snap = dict(current_snap)
    prev_snap["macro_score"] = current_snap["macro_score"] - 15.0
    prev_snap["economic_strength"] = current_snap["economic_strength"] + 10.0

    res = MacroChangeDetector.evaluate_changes(
        current_snapshot=current_snap,
        previous_snapshot=prev_snap
    )
    assert res["macro_delta"] == 15.0
    assert any(d["factor"] == "Macro Score" for d in res["structured_deltas"])
