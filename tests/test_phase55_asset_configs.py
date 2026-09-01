"""
Phase 55 — Tests for Asset Configuration Dictionary
"""

import pytest
from asset_edge_intelligence import ASSET_EDGE_CONFIG


def test_asset_configs_weight_sums():
    # Verify weights for all 10 instruments sum approximately to 1.0 (or normalized)
    for sym, cfg in ASSET_EDGE_CONFIG.items():
        weights = cfg["weights"]
        total_w = sum(weights.values())
        assert 0.85 <= total_w <= 1.05
        assert "display_name" in cfg
        assert "asset_class" in cfg
