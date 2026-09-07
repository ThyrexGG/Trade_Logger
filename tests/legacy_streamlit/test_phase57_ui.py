"""
TradeLogger Phase 57 — Test Suite: Market Intelligence UI Suite
================================================================
Validates:
- Import integrity and syntax of market_intelligence_ui.py.
- Safe HTML helper sanitization (render_html) across UI components.
- Main entry point callable and dispatch integrity.
"""

import pytest
import inspect
import market_intelligence_ui
from market_intelligence_scanner import MarketScannerEngine, MarketBreadthEngine
from cross_asset_regime_engine import CrossAssetRegimeEngine


def test_ui_module_exports():
    """Verify UI render entry point exists and is callable."""
    assert hasattr(market_intelligence_ui, "render_market_intelligence_suite")
    assert inspect.isfunction(market_intelligence_ui.render_market_intelligence_suite)


def test_ui_source_sanitization():
    """Verify that all multiline HTML outputs in market_intelligence_ui use render_html to prevent indentation bugs."""
    with open("market_intelligence_ui.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Verify render_html is imported from ui_components
    assert "render_html" in content
    # Verify no dangerous raw markdown with triple quotes and unsafe_allow_html directly
    assert 'st.markdown("""<div' not in content
    assert 'st.markdown("""\n<div' not in content


def test_hero_bar_data_structures():
    """Verify data structures passed into hero bar contain required metrics."""
    records = MarketScannerEngine.scan_universe("ALL")
    breadth = MarketBreadthEngine.calculate_breadth(records)
    regime = CrossAssetRegimeEngine.evaluate_regime()

    assert regime.primary_regime is not None
    assert breadth["pct_bullish"] >= 0.0
    assert breadth["pct_aligned"] >= 0.0
    assert breadth["avg_data_quality"] >= 0.0
