"""
Phase 58 — Tests for Command Center UI Rendering
"""

import pytest
from market_intelligence_command_center import (
    UnifiedMarketIntelligenceAggregator,
    MarketIntelligenceCommandCenterUI
)


def test_command_center_ui_render_methods():
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()

    # Verify rendering helper functions execute without exception
    MarketIntelligenceCommandCenterUI._render_3s_hero_bar(snap)
    MarketIntelligenceCommandCenterUI._render_what_matters_panel(snap.what_matters)
    MarketIntelligenceCommandCenterUI._render_economic_heatmap_view(snap)
    MarketIntelligenceCommandCenterUI._render_cross_asset_correlations(snap.correlation_matrices)
    MarketIntelligenceCommandCenterUI._render_regime_timeline_view(snap.regime_snapshot)
    MarketIntelligenceCommandCenterUI._render_data_health_and_governance(snap)
