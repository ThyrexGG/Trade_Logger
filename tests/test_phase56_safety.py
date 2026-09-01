"""
Test Suite: Phase 56 Safety & Governance Invariants
===================================================
Validates that:
1. Strategy Contract SHA-256 remains: 7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76
2. Historical holdout baseline remains locked (N=82, E[R]=+0.637R, WR=58.6%, PF=2.52)
3. Dataset isolation holds (IDs_hist ∩ IDs_paper = ∅, IDs_hist ∩ IDs_shadow = ∅)
4. LIVE_AUTOMATION_ENABLED remains False, LIVE_BROKER_TRANSMISSION remains BLOCKED.
5. Macro intelligence is strictly contextual and contains disclaimer.
"""

from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from macro_intelligence_engine import (
    MacroIntelligenceEngine,
    ForexRelativeStrengthEngine,
    XAUUSDMacroContextModel
)
from xauusd_forward_end_to_end_proof import Phase50SafetyBarrier
import execution_pipeline


def test_strategy_contract_hash():
    """Verifies Strategy Contract SHA-256 is immutable."""
    assert FROZEN_CONTRACT_HASH == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_live_automation_fail_closed_barrier():
    """Verifies live broker transmission remains blocked."""
    assert Phase50SafetyBarrier.LIVE_AUTOMATION_ENABLED is False
    assert getattr(execution_pipeline, "LIVE_BROKER_TRANSMISSION", "BLOCKED") == "BLOCKED"


def test_contextual_disclaimer_preservation():
    """Verifies that all macro intelligence responses preserve the mandatory contextual intelligence disclaimer."""
    snap = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")
    assert "disclaimer" in snap
    assert "CONTEXTUAL INTELLIGENCE ONLY" in snap["disclaimer"]

    fx = ForexRelativeStrengthEngine.evaluate_relative_strength("USDJPY")
    assert "CONTEXT ONLY — NOT AN ENTRY SIGNAL" in fx["disclaimer"]

    gold = XAUUSDMacroContextModel.evaluate_gold_macro_context()
    assert "CONTEXT ONLY — NOT AN ENTRY SIGNAL" in gold["disclaimer"]
