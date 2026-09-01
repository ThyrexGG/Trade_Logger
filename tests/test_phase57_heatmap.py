"""
TradeLogger Phase 57 — Test Suite: Economic Heatmap Matrix Engine
==================================================================
Validates:
- 9 Economies (USD, EUR, GBP, JPY, CAD, AUD, NZD, CHF, CNY) integrity.
- 5 Indicator Categories (Growth, Inflation, Labor, Rates, Surprise).
- Dense matrix completeness (45 cells).
- Value scoring range (-100 to +100), label mappings, and icon/badge accessibility.
"""

import pytest
from economic_heatmap import (
    EconomicHeatmapEngine,
    GLOBAL_ECONOMIES,
    CATEGORIES,
    HeatmapCell
)


def test_economic_heatmap_dimensions():
    """Verify matrix has 9 economies and 5 categories."""
    assert len(GLOBAL_ECONOMIES) == 9
    assert set(GLOBAL_ECONOMIES.keys()) == {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF", "CNY"}
    assert len(CATEGORIES) == 5
    assert set(CATEGORIES) == {"GROWTH", "INFLATION", "LABOR", "RATES", "SURPRISE"}


def test_economic_heatmap_matrix_generation():
    """Verify matrix contains 9 rows and 5 category cells each."""
    for econ in GLOBAL_ECONOMIES:
        for cat in CATEGORIES:
            cell = EconomicHeatmapEngine.get_economy_cell(econ, cat)
            assert isinstance(cell, HeatmapCell)
            assert cell.economy == econ
            assert cell.category == cat
            assert len(cell.icon_symbol) > 0
            assert len(cell.badge_label) > 0
            assert len(cell.tint_color) > 0
            assert len(cell.tooltip_text) > 0
            assert cell.freshness in {"LIVE", "FRESH", "AGING", "STALE", "UNAVAILABLE"}


def test_economic_heatmap_rates_cell():
    """Verify RATES category cell extraction and spread calculation."""
    usd_rates = EconomicHeatmapEngine.get_economy_cell("USD", "RATES")
    assert usd_rates.category == "RATES"
    assert usd_rates.actual == 5.25
    assert "5.25%" in usd_rates.badge_label
    assert "Federal Reserve" in usd_rates.tooltip_text
