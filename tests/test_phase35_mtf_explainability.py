"""
Phase 35 — Live Multi-Timeframe Strategy Context & Setup Explainability Test Suite
Validates 5-layer MTF breakdown (1D Macro, 4H DOL, 15M Setup, 5M Confirmation, 1M Precision FVG Entry)
and "Why is there / isn't there a setup?" plain-language reasoning.
"""

import pytest
from xauusd_daily_command_center import SetupExplainabilityEngine


def test_setup_explainability_engine_structure():
    """Validates that SetupExplainabilityEngine explains the current multi-timeframe strategy state."""
    exp = SetupExplainabilityEngine.explain_current_setup("XAUUSD")
    assert isinstance(exp, dict)
    assert exp["symbol"] == "XAUUSD"
    assert "headline" in exp
    assert "is_setup_approved" in exp
    assert "master_state" in exp
    assert "explanation" in exp
    assert "strategy_action" in exp
    assert "layers_breakdown" in exp
    assert len(exp["layers_breakdown"]) == 5

    expected_tfs = ["1D", "4H", "15M", "5M", "1M"]
    for idx, tf in enumerate(expected_tfs):
        layer = exp["layers_breakdown"][idx]
        assert layer["timeframe"] == tf
        assert "purpose" in layer
        assert "status" in layer
        assert layer["status"] in ["PASS", "WAITING", "BLOCKED"]
        assert "detail" in layer
        assert "waiting_for" in layer
