import pandas as pd
import numpy as np

def add_smc_features(df: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
    """
    Computes SMC (Smart Money Concepts) features on a DataFrame in a vectorized manner 
    to avoid lookahead bias and speed up backtesting.
    
    Args:
        df: DataFrame with Open, High, Low, Close
        swing_length: Number of bars on the left and right to define a swing point.
        
    Returns:
        DataFrame with added columns for SMC features.
    """
    # Normalize column names: always rename lowercase/mixed OHLC keys to exact Title Case
    # This handles MT5 ('open','high','low','close'), Binance and yfinance ('Open','High',...) uniformly
    rename_map = {col: col.capitalize() for col in df.columns if col.lower() in ('open', 'high', 'low', 'close', 'volume')}
    df = df.rename(columns=rename_map)

    # Calculate ATR for Displacement Validation
    if 'ATR' not in df.columns:
        df['prev_close'] = df['Close'].shift(1)
        df['tr0'] = abs(df['High'] - df['Low'])
        df['tr1'] = abs(df['High'] - df['prev_close'])
        df['tr2'] = abs(df['Low'] - df['prev_close'])
        df['TR'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        df.drop(columns=['prev_close', 'tr0', 'tr1', 'tr2', 'TR'], inplace=True)

    # 1. Swing Highs and Lows (Strictly avoiding look-ahead bias)
    # A swing high is confirmed at index `i` if `i - swing_length` is the highest of the window `i - 2*swing_length` to `i`.
    window_size = 2 * swing_length + 1
    
    # We use rolling max/min, but we must shift it so that at index i, we evaluate the past `window_size` bars.
    rolling_high = df['High'].rolling(window=window_size).max()
    rolling_low = df['Low'].rolling(window=window_size).min()
    
    # The actual peak was `swing_length` bars ago. 
    # At index i, if the rolling max equals the High at `i - swing_length`, then `i - swing_length` is a confirmed Swing High.
    # Note: We record the swing level at the bar it is CONFIRMED, not the bar it occurred, to prevent look-ahead bias in the strategy.
    
    peak_highs_ago = df['High'].shift(swing_length)
    peak_lows_ago = df['Low'].shift(swing_length)
    
    df['is_swing_high_confirmed'] = (rolling_high == peak_highs_ago)
    df['is_swing_low_confirmed'] = (rolling_low == peak_lows_ago)
    
    df['swing_high_price'] = np.where(df['is_swing_high_confirmed'], peak_highs_ago, np.nan)
    df['swing_low_price'] = np.where(df['is_swing_low_confirmed'], peak_lows_ago, np.nan)
    
    # Equal Highs / Lows (EQH / EQL)
    # Detect if the newly confirmed swing is very close to the *previous* confirmed swing.
    eq_threshold = 0.0005 # 0.05%
    prev_swing_high = df['swing_high_price'].ffill().shift(1)
    prev_swing_low = df['swing_low_price'].ffill().shift(1)
    
    df['is_eqh'] = df['is_swing_high_confirmed'] & (abs(df['swing_high_price'] - prev_swing_high) / prev_swing_high <= eq_threshold)
    df['is_eql'] = df['is_swing_low_confirmed'] & (abs(df['swing_low_price'] - prev_swing_low) / prev_swing_low <= eq_threshold)
    
    # Forward fill the last known swing levels
    df['last_swing_high'] = df['swing_high_price'].ffill()
    df['last_swing_low'] = df['swing_low_price'].ffill()
    df['last_eqh'] = np.where(df['is_eqh'], df['swing_high_price'], np.nan)
    df['last_eql'] = np.where(df['is_eql'], df['swing_low_price'], np.nan)
    df['last_eqh'] = df['last_eqh'].ffill()
    df['last_eql'] = df['last_eql'].ffill()
    
    # 2. Fair Value Gaps (FVGs) with Displacement Validation
    # A Bullish FVG occurs at bar (t-1) when Low(t) > High(t-2). It is confirmed at bar t.
    # We mark it on bar t if the displacement candle (t-1) is greater than 1.5 * ATR(t-2).
    displacement_bullish = (df['High'].shift(1) - df['Low'].shift(1)) > (1.5 * df['ATR'].shift(2))
    bullish_fvg_cond = (df['Low'] > df['High'].shift(2)) & displacement_bullish
    df['bullish_fvg_bottom'] = np.where(bullish_fvg_cond, df['High'].shift(2), np.nan)
    df['bullish_fvg_top'] = np.where(bullish_fvg_cond, df['Low'], np.nan)
    
    displacement_bearish = (df['High'].shift(1) - df['Low'].shift(1)) > (1.5 * df['ATR'].shift(2))
    bearish_fvg_cond = (df['High'] < df['Low'].shift(2)) & displacement_bearish
    df['bearish_fvg_top'] = np.where(bearish_fvg_cond, df['Low'].shift(2), np.nan)
    df['bearish_fvg_bottom'] = np.where(bearish_fvg_cond, df['High'], np.nan)
    
    # 3. Institutional Context (Sessions & PDH/PDL)
    if not df.empty and hasattr(df.index, 'hour'):
        df['hour'] = df.index.hour
        df['date'] = df.index.floor('D')
        
        # Session Flags (UTC)
        df['is_asia'] = (df['hour'] >= 0) & (df['hour'] < 6)
        df['is_london'] = (df['hour'] >= 7) & (df['hour'] < 16)
        df['is_ny'] = (df['hour'] >= 12) & (df['hour'] < 20)
        
        # PDH / PDL (Previous Day High/Low)
        daily_highs = df['High'].resample('D').max()
        daily_lows = df['Low'].resample('D').min()
        df['PDH'] = df['date'].map(daily_highs.shift(1))
        df['PDL'] = df['date'].map(daily_lows.shift(1))
        
        # PWH / PWL (Previous Week High/Low)
        # Using W-SUN ensures the week corresponds to Monday-Sunday, indexed to the Sunday of that week.
        weekly_highs = df['High'].resample('W-SUN').max()
        weekly_lows = df['Low'].resample('W-SUN').min()
        df['week_end'] = df.index.to_period('W-SUN').end_time.normalize()
        df['PWH'] = df['week_end'].map(weekly_highs.shift(1))
        df['PWL'] = df['week_end'].map(weekly_lows.shift(1))
        
        # Asian Range High/Low (Safeguarded against look-ahead bias)
        asian_df = df[df['is_asia']]
        asian_highs = asian_df['High'].resample('D').max()
        asian_lows = asian_df['Low'].resample('D').min()
        
        df['asian_high_today'] = df['date'].map(asian_highs)
        df['asian_low_today'] = df['date'].map(asian_lows)
        df['asian_high_yest'] = df['date'].map(asian_highs.shift(1))
        df['asian_low_yest'] = df['date'].map(asian_lows.shift(1))
        
        # We only know today's Asian Range High/Low AFTER Asia closes (hour >= 6).
        # Otherwise, we use yesterday's Asian Range High/Low.
        after_asia = df['hour'] >= 6
        df['asian_high'] = np.where(after_asia, df['asian_high_today'], df['asian_high_yest'])
        df['asian_low'] = np.where(after_asia, df['asian_low_today'], df['asian_low_yest'])
        
        # Clean up temp columns
        df.drop(columns=['date', 'week_end', 'asian_high_today', 'asian_low_today', 'asian_high_yest', 'asian_low_yest'], inplace=True, errors='ignore')
    
    return df

def detect_liquidity_sweep(df: pd.DataFrame, current_index: int, lookback: int = 50) -> dict:
    """
    Checks if the recent price action swept a major swing point (Liquidity).
    A sweep happens when price pierces a swing level but closes back inside it.
    """
    if current_index < lookback:
        return {"sweep": None}
        
    row = df.iloc[current_index]
    # In a live scenario, a sweep is detected if the *current* candle wicks beyond the last swing, 
    # but the previous candle might have also swept it. For strictness, we check if the High/Low went beyond the last known swing level.
    
    last_sh = df['last_swing_high'].iloc[current_index - 1]
    last_sl = df['last_swing_low'].iloc[current_index - 1]
    
    # Check multiple liquidity pools
    # We prioritize higher timeframe / session liquidity over fractal swings
    pools = []
    
    # PWH / PWL (Highest timeframe liquidity)
    if 'PWH' in df.columns:
        pwh = df['PWH'].iloc[current_index - 1]
        pwl = df['PWL'].iloc[current_index - 1]
        if pd.notna(pwh) and row['High'] > pwh and row['Close'] < pwh:
            pools.append({"sweep": "BSL", "level": pwh, "type": "PWH"})
        if pd.notna(pwl) and row['Low'] < pwl and row['Close'] > pwl:
            pools.append({"sweep": "SSL", "level": pwl, "type": "PWL"})

    # PDH / PDL
    if 'PDH' in df.columns:
        pdh = df['PDH'].iloc[current_index - 1]
        pdl = df['PDL'].iloc[current_index - 1]
        if pd.notna(pdh) and row['High'] > pdh and row['Close'] < pdh:
            pools.append({"sweep": "BSL", "level": pdh, "type": "PDH"})
        if pd.notna(pdl) and row['Low'] < pdl and row['Close'] > pdl:
            pools.append({"sweep": "SSL", "level": pdl, "type": "PDL"})
            
    # Asian Range
    if 'asian_high' in df.columns:
        ash = df['asian_high'].iloc[current_index - 1]
        asl = df['asian_low'].iloc[current_index - 1]
        if pd.notna(ash) and row['High'] > ash and row['Close'] < ash:
            pools.append({"sweep": "BSL", "level": ash, "type": "ASIAN_HIGH"})
        if pd.notna(asl) and row['Low'] < asl and row['Close'] > asl:
            pools.append({"sweep": "SSL", "level": asl, "type": "ASIAN_LOW"})
            
    # Equal Highs / Lows (EQH / EQL)
    if 'last_eqh' in df.columns:
        last_eqh = df['last_eqh'].iloc[current_index - 1]
        last_eql = df['last_eql'].iloc[current_index - 1]
        if pd.notna(last_eqh) and row['High'] > last_eqh and row['Close'] < last_eqh:
            pools.append({"sweep": "BSL", "level": last_eqh, "type": "EQH"})
        if pd.notna(last_eql) and row['Low'] < last_eql and row['Close'] > last_eql:
            pools.append({"sweep": "SSL", "level": last_eql, "type": "EQL"})

    # Fractal Swings
    if 'last_swing_high' in df.columns:
        last_sh = df['last_swing_high'].iloc[current_index - 1]
        last_sl = df['last_swing_low'].iloc[current_index - 1]
        
        if pd.notna(last_sh) and row['High'] > last_sh and row['Close'] < last_sh:
            pools.append({"sweep": "BSL", "level": last_sh, "type": "SWING_HIGH"})
        if pd.notna(last_sl) and row['Low'] < last_sl and row['Close'] > last_sl:
            pools.append({"sweep": "SSL", "level": last_sl, "type": "SWING_LOW"})
            
    if pools:
        # Return the most significant pool swept (first in list based on priority)
        return pools[0]
        
    return {"sweep": None, "level": None, "type": None}

def detect_mss(df: pd.DataFrame, current_index: int, lookback: int = 20) -> str:
    """
    Detects a Market Structure Shift (MSS).
    Returns "BULLISH" if price closes above the last swing high.
    Returns "BEARISH" if price closes below the last swing low.
    """
    if current_index < 1:
        return None
        
    row = df.iloc[current_index]
    last_sh = df['last_swing_high'].iloc[current_index - 1]
    last_sl = df['last_swing_low'].iloc[current_index - 1]
    
    if pd.notna(last_sh) and row['Close'] > last_sh:
        return "BULLISH"
    
    if pd.notna(last_sl) and row['Close'] < last_sl:
        return "BEARISH"
        
    return None
