"""
Tests for Phase 29 Execution Stress & Event Attribution.
Verifies hypothetical microstructure stress calculations and separation of Strategy vs Execution failures.
"""

import pytest
from xauusd_forward_execution_stress import ExecutionStressAuditor, ForwardOutcomeAttributor


def test_execution_stress_auditor_scenarios():
    res = ExecutionStressAuditor.run_execution_stress_analysis(mode="PAPER")
    
    assert "current_expectancy_r" in res
    assert "Hypothetical stress analyses only" in res["disclaimer"]
    assert len(res["slippage_stress"]) == 4  # 0p, 1p, 2p, 3p
    assert len(res["spread_stress"]) == 4    # 0p, 1p, 2p, 3p
    assert len(res["fill_stress"]) == 4      # 0%, -5%, -10%, -20%

    # Check stress degradation logic
    slip_0 = res["slippage_stress"][0]
    slip_3 = res["slippage_stress"][3]
    assert slip_3["stressed_expectancy_r"] < slip_0["stressed_expectancy_r"]
    assert slip_3["expectancy_loss_r"] > 0


def test_forward_outcome_attributor():
    attr = ForwardOutcomeAttributor.attribute_outcomes(mode="PAPER")
    
    assert "items" in attr
    categories = {item["category"] for item in attr["items"]}
    assert "VALID TRADE — WIN" in categories
    assert "VALID TRADE — LOSS" in categories
    assert "MISSED ENTRY — LIMIT TIMEOUT" in categories
    
    # Must separate strategy failure from execution miss
    assert "strictly separated" in attr["core_separation_principle"].lower()
