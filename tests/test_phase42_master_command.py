"""
Phase 42 — Master Research Health & Instant Status Test Suite
Validates 8-pillar master health evaluation and 4-quadrant instant status synthesizer.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_master_research_command import (
    MasterResearchHealthEvaluator,
    WhatDoINeedToKnowNowSynthesizer,
)


def test_master_research_health_evaluation():
    """Validates 8-subsystem master health synthesis."""
    health = MasterResearchHealthEvaluator.evaluate_master_health("XAUUSD")

    assert "master_state" in health
    assert "master_color" in health
    assert len(health["subsystems"]) == 8
    assert health["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert health["live_automation"] == "DISABLED_PERMANENTLY"


def test_what_do_i_need_to_know_now_four_quadrants():
    """Validates 4-quadrant instant status dashboard."""
    status = WhatDoINeedToKnowNowSynthesizer.get_instant_status("XAUUSD")

    assert "market_quadrant" in status
    assert "news_quadrant" in status
    assert "strategy_quadrant" in status
    assert "evidence_quadrant" in status
    assert "current_price" in status["market_quadrant"]
    assert status["strategy_quadrant"]["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
