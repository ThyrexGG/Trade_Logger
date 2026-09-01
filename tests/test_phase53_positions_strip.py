"""
Phase 53 — Tests for Persistent Active Positions & Excursion (MAE / MFE) Strip
"""

import pytest
import pandas as pd
from trading_workspace_cockpit import TradingWorkspaceCockpit


def test_empty_positions_strip_handling():
    empty_df = pd.DataFrame()
    # Must not raise exceptions
    TradingWorkspaceCockpit.render_active_positions_strip(empty_df)


def test_positions_with_excursion_data():
    df_test = pd.DataFrame([{
        "position_id": "TEST_POS_001",
        "symbol": "XAUUSD",
        "direction": "BUY",
        "volume": 0.10,
        "entry_price": 2400.0,
        "current_price": 2410.0,
        "sl": 2395.0,
        "tp": 2415.0,
        "floating_pnl": 100.0,
        "account_id": "PAPER"
    }])
    # R-multiple: (2410 - 2400) / (2400 - 2395) = +2.00R
    TradingWorkspaceCockpit.render_active_positions_strip(df_test)
