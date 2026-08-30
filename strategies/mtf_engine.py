import pandas as pd
import numpy as np

def calculate_htf_bias(df_htf: pd.DataFrame) -> str:
    """
    Calculates deterministic Trend Bias based on EMAs and Structure for a given timeframe.
    Returns "BULLISH", "BEARISH", or "NEUTRAL".
    """
    if len(df_htf) < 50:
        return "NEUTRAL"
        
    df = df_htf.copy()
    
    # Normalize column names: always rename lowercase/mixed OHLC keys to exact Title Case
    rename_map = {col: col.capitalize() for col in df.columns if col.lower() in ('open', 'high', 'low', 'close', 'volume')}
    df = df.rename(columns=rename_map)
    
    # Calculate EMAs
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    ema50 = df['Close'].ewm(span=50, adjust=False).mean()
    ema200 = df['Close'].ewm(span=200, adjust=False).mean() if len(df) >= 200 else ema50
    
    current_close = df['Close'].iloc[-1]
    current_ema20 = ema20.iloc[-1]
    current_ema50 = ema50.iloc[-1]
    current_ema200 = ema200.iloc[-1]
    
    # Determine basic EMA alignment
    if current_close > current_ema20 and current_ema20 > current_ema50:
        bias = "BULLISH"
    elif current_close < current_ema20 and current_ema20 < current_ema50:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
        
    # Check Structure if SMC features exist
    if 'last_swing_high' in df.columns and 'last_swing_low' in df.columns:
        last_sh = df['last_swing_high'].iloc[-1]
        last_sl = df['last_swing_low'].iloc[-1]
        
        # We can refine bias based on recent closes relative to structure
        if bias == "BULLISH" and pd.notna(last_sl) and current_close < last_sl:
            bias = "NEUTRAL" # Bearish MSS overrides EMA bullishness
        elif bias == "BEARISH" and pd.notna(last_sh) and current_close > last_sh:
            bias = "NEUTRAL" # Bullish MSS overrides EMA bearishness
            
    return bias

def align_htf_to_ltf(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, htf_suffix: str, htf_offset: str) -> pd.DataFrame:
    """
    Strictly aligns Higher Timeframe (HTF) data onto a Lower Timeframe (LTF) dataframe
    without look-ahead bias.
    
    For an LTF candle at time T, it merges the HTF candle that was COMPLETED at or before time T.
    
    Args:
        df_ltf: The execution timeframe dataframe (index must be datetime).
        df_htf: The higher timeframe dataframe (index must be datetime).
        htf_suffix: Suffix to append to HTF columns (e.g. '_1H').
        htf_offset: Pandas frequency string for the HTF (e.g. '1h', '4h', '1d').
    """
    if df_ltf.empty or df_htf.empty:
        return df_ltf

    # Ensure indices are timezone-aware and match
    if df_ltf.index.tz is None and getattr(df_htf.index, 'tz', None) is not None:
        df_ltf.index = df_ltf.index.tz_localize('UTC')
    elif getattr(df_ltf.index, 'tz', None) is not None and getattr(df_htf.index, 'tz', None) is None:
        df_htf.index = df_htf.index.tz_localize('UTC')
        
    df_ltf = df_ltf.copy()
    
    # We must find the start time of the LAST COMPLETED HTF candle for each LTF candle.
    # df_ltf.index represents the START time of the LTF candle.
    freq_map = {'1m': '1min', '5m': '5min', '15m': '15min', '15min': '15min', '1h': '1h', '1H': '1h', '4h': '4h', '4H': '4h', '1d': '1D', '1D': '1D'}
    floor_freq = freq_map.get(htf_offset, htf_offset)
    
    try:
        current_htf_start = df_ltf.index.floor(floor_freq)
        last_completed_htf_start = current_htf_start - pd.to_timedelta(htf_offset)
    except ValueError:
        return df_ltf
        
    df_ltf['__ref_htf_time'] = last_completed_htf_start
    
    df_htf_copy = df_htf.copy()
    ema20 = df_htf_copy['Close'].ewm(span=20, adjust=False).mean()
    ema50 = df_htf_copy['Close'].ewm(span=50, adjust=False).mean()
    
    bias_series = pd.Series("NEUTRAL", index=df_htf_copy.index)
    bullish_mask = (df_htf_copy['Close'] > ema20) & (ema20 > ema50)
    bearish_mask = (df_htf_copy['Close'] < ema20) & (ema20 < ema50)
    bias_series[bullish_mask] = "BULLISH"
    bias_series[bearish_mask] = "BEARISH"
    df_htf_copy['HTF_Bias'] = bias_series
    
    # Columns to merge from HTF
    cols_to_merge = ['Close', 'HTF_Bias', 'last_swing_high', 'last_swing_low', 'bullish_fvg_bottom', 'bullish_fvg_top', 'bearish_fvg_top', 'bearish_fvg_bottom']
    available_cols = [c for c in cols_to_merge if c in df_htf_copy.columns]
    
    df_htf_subset = df_htf_copy[available_cols].add_suffix(htf_suffix)
    
    # Merge using left join on the calculated reference time
    merged = df_ltf.merge(df_htf_subset, left_on='__ref_htf_time', right_index=True, how='left')
    merged.drop(columns=['__ref_htf_time'], inplace=True)
    
    return merged
