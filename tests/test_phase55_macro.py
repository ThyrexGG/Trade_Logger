"""
Phase 55 — Tests for Macroeconomic Factor & Event Proximity
"""

import pytest
from datetime import datetime, timezone
from asset_edge_intelligence import MacroeconomicFactorEngine


def test_macro_factor_evaluation():
    res = MacroeconomicFactorEngine.evaluate("XAUUSD")
    assert -100.0 <= res["score"] <= 100.0
    assert "source" in res
    assert res["data_available"] is True


def test_macro_lookahead_safety():
    # Calling evaluate with a fixed timestamp must not leak future timestamps
    dt = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
    res = MacroeconomicFactorEngine.evaluate("XAUUSD", as_of=dt)
    assert res["source"]["timestamp"] == dt.isoformat()
