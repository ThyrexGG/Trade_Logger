"""
TradeLogger Phase 57 — Test Suite: Economic Surprise Heatmap Engine
====================================================================
Validates:
- Economic surprise index calculation based on actual vs expectation.
- Z-score deviation momentum scoring.
- Release evaluation across economies.
"""

import pytest
from economic_heatmap import EconomicHeatmapEngine, GLOBAL_ECONOMIES, HeatmapCell
from macro_intelligence_engine import EconomicSurpriseEngine, EconomicDataRegistry


def test_surprise_cell_generation():
    """Verify surprise cell generation for all 9 economies."""
    for econ in GLOBAL_ECONOMIES:
        cell = EconomicHeatmapEngine.get_economy_cell(econ, "SURPRISE")
        assert isinstance(cell, HeatmapCell)
        assert cell.category == "SURPRISE"
        assert cell.economy == econ
        assert len(cell.badge_label) > 0
        assert "σ" in cell.badge_label


def test_statistical_surprise_engine_integration():
    """Verify EconomicSurpriseEngine integrates properly with EconomicDataRegistry."""
    releases = EconomicDataRegistry.get_releases_as_of(country="USD")
    assert len(releases) > 0

    for r in releases[:5]:
        s = EconomicSurpriseEngine.evaluate_release_surprise(r)
        assert "z_score" in s
        assert "direction" in s
        assert "raw_surprise" in s
