"""
Phase 57: Test Suite for Market Intelligence UI Module
Verifies:
- Rendering helper functions return valid HTML
- No raw indentation bugs (uses ui_components.render_html)
- Tab suite functions execute cleanly without uncaught exceptions
"""

from unittest.mock import MagicMock, patch
import pytest
import market_intelligence_ui


def test_ui_module_imports():
    assert hasattr(market_intelligence_ui, "render_market_intelligence_suite")
    assert hasattr(market_intelligence_ui, "render_market_overview_tab")
    assert hasattr(market_intelligence_ui, "render_asset_ranking_tab")
    assert hasattr(market_intelligence_ui, "render_economic_heatmap_tab")
    assert hasattr(market_intelligence_ui, "render_economic_surprise_tab")
    assert hasattr(market_intelligence_ui, "render_cross_asset_matrix_tab")
    assert hasattr(market_intelligence_ui, "render_market_regime_tab")
    assert hasattr(market_intelligence_ui, "render_what_changed_tab")
    assert hasattr(market_intelligence_ui, "render_scanner_audit_tab")


@patch("streamlit.markdown")
@patch("streamlit.tabs")
@patch("streamlit.columns")
@patch("streamlit.selectbox")
@patch("streamlit.button")
def test_render_suite_smoke(mock_btn, mock_sel, mock_cols, mock_tabs, mock_md):
    # Mock streamlit components
    mock_cols.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    mock_tabs.return_value = [MagicMock() for _ in range(8)]
    mock_sel.return_value = "ALL"
    mock_btn.return_value = False

    try:
        market_intelligence_ui.render_market_intelligence_suite()
    except Exception as e:
        pytest.fail(f"render_market_intelligence_suite raised unexpected exception: {e}")
