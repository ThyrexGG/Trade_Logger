import pytest
import pandas as pd
import numpy as np
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.mtf_engine import align_htf_to_ltf, calculate_htf_bias
from strategies.smc_utils import add_smc_features
from strategies.ict_2022_model import ICT2022Model
from backtester import run_backtest

def create_synthetic_data(freq, start, end):
    dates = pd.date_range(start, end, freq=freq, tz='UTC')
    df = pd.DataFrame({
        "Open": np.random.rand(len(dates)) * 100 + 10,
        "High": np.random.rand(len(dates)) * 100 + 20,
        "Low": np.random.rand(len(dates)) * 100,
        "Close": np.random.rand(len(dates)) * 100 + 10,
        "Volume": np.random.randint(100, 1000, size=len(dates))
    }, index=dates)
    return df

def test_mtf_look_ahead_proof():
    """
    Test that a 15M candle at 10:15 cannot see a 1H candle that is still forming (09:00 - 10:00).
    Wait, a 1H candle starting at 09:00 is completed at 10:00. So at 10:15, the 09:00 candle IS completed.
    But the 1H candle starting at 10:00 is NOT completed at 10:15, 10:30, or 10:45.
    We must ensure 10:15 only sees the 09:00 candle.
    """
    df_15m = create_synthetic_data("15min", "2023-01-01 09:00:00", "2023-01-01 12:00:00")
    df_1h = create_synthetic_data("1h", "2023-01-01 08:00:00", "2023-01-01 12:00:00")
    
    # Inject malicious extreme price into the 10:00 1H candle
    malicious_time = pd.Timestamp("2023-01-01 10:00:00", tz='UTC')
    df_1h.loc[malicious_time, "Close"] = 999999.0
    
    merged = align_htf_to_ltf(df_15m, df_1h, "_1H", "1h")
    
    # Verify 10:15, 10:30, 10:45 do NOT contain 999999.0
    for m in [15, 30, 45]:
        test_time = pd.Timestamp(f"2023-01-01 10:{m}:00", tz='UTC')
        if test_time in merged.index:
            assert merged.loc[test_time, "Close_1H"] != 999999.0, f"Lookahead Leakage at {test_time}!"
            # It should instead see the 09:00 candle close
            expected_close = df_1h.loc[pd.Timestamp("2023-01-01 09:00:00", tz='UTC'), "Close"]
            assert merged.loc[test_time, "Close_1H"] == expected_close

def test_future_candle_mutation():
    """
    Run strategy on original data, save setup at T.
    Mutate T+1 onwards with extreme prices.
    Run strategy again. Setup at T must be IDENTICAL.
    """
    df = create_synthetic_data("1h", "2023-01-01 00:00:00", "2023-01-05 00:00:00")
    df = add_smc_features(df)
    
    strat = ICT2022Model()
    t_idx = 50
    setup_original = strat.analyze(df, t_idx, context={})
    
    # Mutate future
    df_mutated = df.copy()
    df_mutated.iloc[t_idx+1:, df_mutated.columns.get_loc('High')] = 999999.0
    df_mutated.iloc[t_idx+1:, df_mutated.columns.get_loc('Low')] = -999999.0
    
    setup_mutated = strat.analyze(df_mutated, t_idx, context={})
    
    assert setup_original == setup_mutated, "Future candle mutation leaked into current setup evaluation!"

def test_htf_fvg_availability():
    """
    Verify FVG formed by candles T-2, T-1, T only becomes available at T (after T closes).
    In our SMC script, FVG is marked on the T-1 candle, but only calculated when T is available.
    Because Pandas vectorized operations apply to the whole series, if we slice up to T, 
    the FVG should exist at T-1.
    """
    df = create_synthetic_data("1h", "2023-01-01 00:00:00", "2023-01-02 10:00:00")
    # Ensure bar 19 High prevents accidental FVG at bar 21
    df.iloc[19, df.columns.get_loc('High')] = 200
    # Force an intentional Bullish FVG spanning indices 20, 21, 22
    df.iloc[20, df.columns.get_loc('High')] = 100
    df.iloc[21, df.columns.get_loc('Low')] = 105
    df.iloc[21, df.columns.get_loc('High')] = 300 # Massive displacement
    df.iloc[22, df.columns.get_loc('Low')] = 110 # Gap between 20's High and 22's Low is 100 to 110.
    df.iloc[22, df.columns.get_loc('Close')] = 115
    df.iloc[21, df.columns.get_loc('Close')] = 108
    df.iloc[20, df.columns.get_loc('Close')] = 90
    
    # Run SMC up to index 21 (Candle 22 hasn't closed yet)
    df_incomplete = add_smc_features(df.iloc[:22].copy())
    assert pd.isna(df_incomplete['bullish_fvg_bottom'].iloc[21]), "FVG appeared before 3rd candle closed!"
    
    # Run SMC up to index 22 (Candle 22 closed)
    df_complete = add_smc_features(df.iloc[:23].copy())
    assert not pd.isna(df_complete['bullish_fvg_bottom'].iloc[22]), "FVG failed to appear after 3rd candle closed!"

def test_mtf_bias_audit():
    df = create_synthetic_data("1h", "2023-01-01", "2023-01-10")
    
    # If < 50 bars, bias is NEUTRAL
    short_df = df.iloc[:40]
    assert calculate_htf_bias(short_df) == "NEUTRAL"
    
    # Force Bullish (Price > EMA20 > EMA50)
    df_bull = df.copy()
    # Mock EMAs isn't possible directly since calculate_htf_bias recalculates them, 
    # so we must make actual prices trend up strongly.
    df_bull['Close'] = np.linspace(10, 1000, len(df_bull))
    assert calculate_htf_bias(df_bull) == "BULLISH"
    
    # Force Bearish
    df_bear = df.copy()
    df_bear['Close'] = np.linspace(1000, 10, len(df_bear))
    assert calculate_htf_bias(df_bear) == "BEARISH"

if __name__ == "__main__":
    pytest.main([__file__])
