"""
Phase 55 — Tests for Seasonality Factor & Sample Disclaimers
"""

import pytest
from datetime import datetime, timezone
from asset_edge_intelligence import SeasonalityFactorEngine


def test_seasonality_evaluation_with_sample_lookback():
    dt_jan = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    res_jan = SeasonalityFactorEngine.evaluate("XAUUSD", as_of=dt_jan)
    assert res_jan["score"] > 0
    assert "sample_lookback" in res_jan
    assert "15 Years" in res_jan["sample_lookback"]
