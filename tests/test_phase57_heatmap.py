"""
Phase 57: Test Suite for Economic Heatmap Engine
Verifies:
- 9 Economies (USD, EUR, GBP, JPY, CAD, AUD, NZD, CHF, CNY)
- 5 Categories (GROWTH, INFLATION, LABOR, RATES, SURPRISE)
- Dense matrix completeness (45 cells total)
- Accessible badge and state generation
"""

import pytest
from economic_heatmap import EconomicHeatmapEngine, SUPPORTED_ECONOMIES, SUPPORTED_CATEGORIES


def test_matrix_dimensions():
    grid = EconomicHeatmapEngine.generate_heatmap_grid()
    assert len(grid) == 9
    assert set(grid.keys()) == set(SUPPORTED_ECONOMIES)

    total_cells = 0
    for econ, cat_map in grid.items():
        assert len(cat_map) == 5
        assert set(cat_map.keys()) == set(SUPPORTED_CATEGORIES)
        for cat, cell in cat_map.items():
            total_cells += 1
            assert "score" in cell
            assert "state" in cell
            assert "color" in cell
            assert "badge" in cell
            assert "indicator" in cell
            assert -100 <= cell["score"] <= 100
    assert total_cells == 45


def test_accessible_indicator_presence():
    grid = EconomicHeatmapEngine.generate_heatmap_grid()
    for econ in grid:
        for cat in grid[econ]:
            cell = grid[econ][cat]
            # Must have accessible icon/badge and descriptive label
            assert cell["badge"] in ("🟢 HOT", "🟡 NEU", "🔴 COOL", "⚪ N/A")
            assert cell["indicator"] in ("▲", "▼", "◆", "—")


def test_economy_summary_generation():
    summaries = EconomicHeatmapEngine.get_economy_summaries()
    assert len(summaries) == 9
    for s in summaries:
        assert "economy" in s
        assert "name" in s
        assert "overall_score" in s
        assert "dominant_driver" in s
        assert "primary_risk" in s
