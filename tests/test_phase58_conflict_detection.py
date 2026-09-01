"""
Phase 58 — Tests for Factor Conflict Detection in Command Center Profiles
"""

import pytest
from market_intelligence_command_center import AssetContextProfileEngine


def test_conflict_detection_gold_profile():
    prof = AssetContextProfileEngine.build_asset_profile("XAUUSD")
    conf = prof["conflict_analysis"]

    assert "factor_agreement_pct" in conf
    assert "has_conflict" in conf
    assert "conflict_summary" in conf
    assert 0.0 <= conf["factor_agreement_pct"] <= 100.0
