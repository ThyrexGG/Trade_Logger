"""
Phase 53 — Tests for MTF Context Hierarchy Component
"""

import pytest
from trading_workspace_cockpit import TradingWorkspaceCockpit


def test_mtf_context_all_layers_present():
    layers = ["1D", "4H", "1H", "15M", "5M", "1M"]
    xau_res = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("XAUUSD")
    for l in layers:
        assert l in xau_res
        assert isinstance(xau_res[l], str)
        assert len(xau_res[l]) > 0
