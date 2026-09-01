# -*- coding: utf-8 -*-
"""
Phase 61 - Test Active Positions Strip, Excursion Metrics & Empty State
"""
import pytest
import pandas as pd
import streamlit as st
from trading_workspace_cockpit import TradingWorkspaceCockpit


def test_active_positions_empty_state(monkeypatch):
    """Verify empty DataFrame renders intentional empty state."""
    called = []
    def fake_markdown(content, unsafe_allow_html=False):
        called.append(content)

    monkeypatch.setattr(st, "markdown", fake_markdown)
    empty_df = pd.DataFrame()
    TradingWorkspaceCockpit.render_active_positions_strip(empty_df)

    assert len(called) >= 1
    combined = "".join(called)
    assert "NO ACTIVE POSITIONS" in combined
    assert "tl-empty-state" in combined
