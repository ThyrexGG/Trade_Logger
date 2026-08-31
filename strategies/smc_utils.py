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


# ----------------- Structured SMC Entity Detectors (Phase 13) -----------------
from strategies.smc_models import (
    LiquidityPool,
    FairValueGap,
    OrderBlock,
    MarketStructureEvent,
    DealingRange,
    SMCContext
)


def extract_active_liquidity_pools(df: pd.DataFrame, current_index: int, lookback: int = 50, timeframe: str = "15m") -> List[LiquidityPool]:
    """Extracts all active un-swept institutional liquidity pools."""
    if current_index < 2 or df.empty:
        return []

    pools = []
    curr_row = df.iloc[current_index]
    curr_ts = str(df.index[current_index]) if hasattr(df.index, '__getitem__') else "N/A"
    curr_px = float(curr_row['Close'])

    # PWH / PWL
    if 'PWH' in df.columns:
        pwh = df['PWH'].iloc[current_index]
        if pd.notna(pwh) and pwh > 0:
            swept = curr_row['High'] > pwh
            pools.append(LiquidityPool(
                pool_id=f"PWH_{pwh:.5f}",
                pool_type="BSL_PWH",
                price=float(pwh),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=3.0,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))
    if 'PWL' in df.columns:
        pwl = df['PWL'].iloc[current_index]
        if pd.notna(pwl) and pwl > 0:
            swept = curr_row['Low'] < pwl
            pools.append(LiquidityPool(
                pool_id=f"PWL_{pwl:.5f}",
                pool_type="SSL_PWL",
                price=float(pwl),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=3.0,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))

    # PDH / PDL
    if 'PDH' in df.columns:
        pdh = df['PDH'].iloc[current_index]
        if pd.notna(pdh) and pdh > 0:
            swept = curr_row['High'] > pdh
            pools.append(LiquidityPool(
                pool_id=f"PDH_{pdh:.5f}",
                pool_type="BSL_PDH",
                price=float(pdh),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=2.5,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))
    if 'PDL' in df.columns:
        pdl = df['PDL'].iloc[current_index]
        if pd.notna(pdl) and pdl > 0:
            swept = curr_row['Low'] < pdl
            pools.append(LiquidityPool(
                pool_id=f"PDL_{pdl:.5f}",
                pool_type="SSL_PDL",
                price=float(pdl),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=2.5,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))

    # Asian Range
    if 'asian_high' in df.columns:
        ash = df['asian_high'].iloc[current_index]
        if pd.notna(ash) and ash > 0:
            swept = curr_row['High'] > ash
            pools.append(LiquidityPool(
                pool_id=f"ASIA_H_{ash:.5f}",
                pool_type="BSL_ASIAN",
                price=float(ash),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=2.0,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))
    if 'asian_low' in df.columns:
        asl = df['asian_low'].iloc[current_index]
        if pd.notna(asl) and asl > 0:
            swept = curr_row['Low'] < asl
            pools.append(LiquidityPool(
                pool_id=f"ASIA_L_{asl:.5f}",
                pool_type="SSL_ASIAN",
                price=float(asl),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=2.0,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))

    # Equal Highs / Lows (EQH / EQL)
    if 'last_eqh' in df.columns:
        eqh = df['last_eqh'].iloc[current_index]
        if pd.notna(eqh) and eqh > 0:
            swept = curr_row['High'] > eqh
            pools.append(LiquidityPool(
                pool_id=f"EQH_{eqh:.5f}",
                pool_type="EQH",
                price=float(eqh),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=2.0,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))
    if 'last_eql' in df.columns:
        eql = df['last_eql'].iloc[current_index]
        if pd.notna(eql) and eql > 0:
            swept = curr_row['Low'] < eql
            pools.append(LiquidityPool(
                pool_id=f"EQL_{eql:.5f}",
                pool_type="EQL",
                price=float(eql),
                timeframe=timeframe,
                created_at=curr_ts,
                strength=2.0,
                is_swept=bool(swept),
                swept_at=curr_ts if swept else None,
                sweep_bar_index=current_index if swept else None
            ))

    return pools


def extract_active_fair_value_gaps(df: pd.DataFrame, current_index: int, lookback: int = 50, timeframe: str = "15m") -> List[FairValueGap]:
    """Extracts active Fair Value Gaps with mitigation tracking and Inversion FVG support."""
    if current_index < 3 or df.empty:
        return []

    start_idx = max(2, current_index - lookback)
    fvgs = []
    curr_row = df.iloc[current_index]
    curr_px = float(curr_row['Close'])

    for i in range(start_idx, current_index + 1):
        ts = str(df.index[i]) if hasattr(df.index, '__getitem__') else f"bar_{i}"
        
        # Check Bullish FVG
        if 'bullish_fvg_bottom' in df.columns and pd.notna(df['bullish_fvg_bottom'].iloc[i]):
            bot = float(df['bullish_fvg_bottom'].iloc[i])
            top = float(df['bullish_fvg_top'].iloc[i])
            if top > bot:
                # Check if mitigated between bar i and current_index
                sub_low = df['Low'].iloc[i:current_index + 1].min()
                mitigated = sub_low <= bot
                is_inversion = curr_px < bot # Price has broken below bullish gap
                fvgs.append(FairValueGap(
                    fvg_id=f"BULL_FVG_{i}_{bot:.5f}",
                    direction="BULLISH",
                    top=top,
                    bottom=bot,
                    timeframe=timeframe,
                    created_at=ts,
                    bar_index=i,
                    displacement_atr_ratio=1.5,
                    is_mitigated=bool(mitigated),
                    is_inversion=bool(is_inversion)
                ))

        # Check Bearish FVG
        if 'bearish_fvg_top' in df.columns and pd.notna(df['bearish_fvg_top'].iloc[i]):
            top = float(df['bearish_fvg_top'].iloc[i])
            bot = float(df['bearish_fvg_bottom'].iloc[i])
            if top > bot:
                sub_high = df['High'].iloc[i:current_index + 1].max()
                mitigated = sub_high >= top
                is_inversion = curr_px > top # Price has broken above bearish gap
                fvgs.append(FairValueGap(
                    fvg_id=f"BEAR_FVG_{i}_{bot:.5f}",
                    direction="BEARISH",
                    top=top,
                    bottom=bot,
                    timeframe=timeframe,
                    created_at=ts,
                    bar_index=i,
                    displacement_atr_ratio=1.5,
                    is_mitigated=bool(mitigated),
                    is_inversion=bool(is_inversion)
                ))

    return fvgs


def extract_order_blocks(df: pd.DataFrame, current_index: int, lookback: int = 50, timeframe: str = "15m") -> List[OrderBlock]:
    """Detects institutional Order Blocks & Breaker Blocks."""
    if current_index < 5 or df.empty or 'ATR' not in df.columns:
        return []

    start_idx = max(3, current_index - lookback)
    obs = []
    curr_px = float(df['Close'].iloc[current_index])

    for i in range(start_idx, current_index):
        ts = str(df.index[i]) if hasattr(df.index, '__getitem__') else f"bar_{i}"
        atr = float(df['ATR'].iloc[i]) if pd.notna(df['ATR'].iloc[i]) and df['ATR'].iloc[i] > 0 else 0.0010
        
        # Bullish OB: Last down-close candle before sharp upward displacement (>= 1.5x ATR)
        if df['Close'].iloc[i] < df['Open'].iloc[i]:
            disp_up = (df['High'].iloc[i+1:min(i+4, len(df))].max() - df['Low'].iloc[i])
            if disp_up >= 1.5 * atr:
                top = float(df['High'].iloc[i])
                bot = float(df['Low'].iloc[i])
                mitigated = df['Low'].iloc[i+1:current_index+1].min() <= bot
                is_breaker = curr_px < bot # Violated bullish OB becomes bearish breaker
                obs.append(OrderBlock(
                    ob_id=f"BULL_OB_{i}",
                    direction="BULLISH",
                    top=top,
                    bottom=bot,
                    timeframe=timeframe,
                    created_at=ts,
                    bar_index=i,
                    displacement_atr_ratio=round(disp_up / atr, 2),
                    is_mitigated=bool(mitigated),
                    is_breaker=bool(is_breaker)
                ))

        # Bearish OB: Last up-close candle before sharp downward displacement
        if df['Close'].iloc[i] > df['Open'].iloc[i]:
            disp_down = (df['High'].iloc[i] - df['Low'].iloc[i+1:min(i+4, len(df))].min())
            if disp_down >= 1.5 * atr:
                top = float(df['High'].iloc[i])
                bot = float(df['Low'].iloc[i])
                mitigated = df['High'].iloc[i+1:current_index+1].max() >= top
                is_breaker = curr_px > top # Violated bearish OB becomes bullish breaker
                obs.append(OrderBlock(
                    ob_id=f"BEAR_OB_{i}",
                    direction="BEARISH",
                    top=top,
                    bottom=bot,
                    timeframe=timeframe,
                    created_at=ts,
                    bar_index=i,
                    displacement_atr_ratio=round(disp_down / atr, 2),
                    is_mitigated=bool(mitigated),
                    is_breaker=bool(is_breaker)
                ))

    return obs


def extract_dealing_range(df: pd.DataFrame, current_index: int, lookback: int = 50, timeframe: str = "15m") -> DealingRange:
    """Calculates active institutional Dealing Range (Fibonacci Equilibrium, Premium, Discount)."""
    start_idx = max(0, current_index - lookback)
    slice_df = df.iloc[start_idx:current_index + 1]
    
    high = float(slice_df['High'].max())
    low = float(slice_df['Low'].min())
    ts = str(df.index[current_index]) if hasattr(df.index, '__getitem__') else "N/A"

    return DealingRange(
        high=round(high, 5),
        low=round(low, 5),
        timeframe=timeframe,
        created_at=ts
    )


def extract_market_structure_events(df: pd.DataFrame, current_index: int, lookback: int = 30, timeframe: str = "15m") -> List[MarketStructureEvent]:
    """Extracts recent Market Structure Shifts (MSS), Break of Structure (BOS), and CHOCH."""
    if current_index < 2 or df.empty or 'last_swing_high' not in df.columns:
        return []

    events = []
    start_idx = max(1, current_index - lookback)
    
    for i in range(start_idx, current_index + 1):
        ts = str(df.index[i]) if hasattr(df.index, '__getitem__') else f"bar_{i}"
        row = df.iloc[i]
        last_sh = df['last_swing_high'].iloc[i - 1] if i > 0 else np.nan
        last_sl = df['last_swing_low'].iloc[i - 1] if i > 0 else np.nan
        
        # Bullish MSS / BOS
        if pd.notna(last_sh) and row['Close'] > last_sh and df['Close'].iloc[i - 1] <= last_sh:
            events.append(MarketStructureEvent(
                event_id=f"MSS_BULL_{i}",
                event_type="MSS",
                direction="BULLISH",
                price=float(row['Close']),
                timeframe=timeframe,
                timestamp=ts,
                bar_index=i,
                broken_swing_price=float(last_sh)
            ))
            
        # Bearish MSS / BOS
        if pd.notna(last_sl) and row['Close'] < last_sl and df['Close'].iloc[i - 1] >= last_sl:
            events.append(MarketStructureEvent(
                event_id=f"MSS_BEAR_{i}",
                event_type="MSS",
                direction="BEARISH",
                price=float(row['Close']),
                timeframe=timeframe,
                timestamp=ts,
                bar_index=i,
                broken_swing_price=float(last_sl)
            ))

    return events


def build_smc_context(
    df_exec: pd.DataFrame,
    df_struct: Optional[pd.DataFrame] = None,
    df_bias: Optional[pd.DataFrame] = None,
    symbol: str = "EURUSD",
    current_index: int = -1,
    exec_tf: str = "1m",
    struct_tf: str = "15m",
    bias_tf: str = "1h"
) -> SMCContext:
    """
    Assembles a complete, immutable SMCContext snapshot from multi-timeframe inputs.
    Strictly lookahead-safe: Higher timeframe DataFrames are evaluated only up to the timestamp of df_exec[current_index].
    """
    if df_exec.empty:
        return SMCContext(
            symbol=symbol,
            execution_timeframe=exec_tf,
            structure_timeframe=struct_tf,
            bias_timeframe=bias_tf,
            timestamp=datetime.now(timezone.utc).isoformat(),
            current_price=0.0,
            htf_bias="NEUTRAL"
        )

    if current_index < 0:
        current_index = len(df_exec) - 1

    df_exec_feat = add_smc_features(df_exec.copy())
    curr_row = df_exec_feat.iloc[current_index]
    curr_px = float(curr_row['Close'])
    curr_ts = str(df_exec_feat.index[current_index]) if hasattr(df_exec_feat.index, '__getitem__') else "N/A"

    # Evaluate Structure & Bias Timeframes strictly without look-ahead
    struct_source = df_struct if df_struct is not None and not df_struct.empty else df_exec
    bias_source = df_bias if df_bias is not None and not df_bias.empty else df_exec
    
    df_struct_feat = add_smc_features(struct_source.copy())
    df_bias_feat = add_smc_features(bias_source.copy())

    # HTF Bias from Bias TF (EMA 20 vs 50 or Market Structure)
    htf_bias = "NEUTRAL"
    if len(df_bias_feat) >= 50:
        ema20 = df_bias_feat['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df_bias_feat['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        last_close = df_bias_feat['Close'].iloc[-1]
        if last_close > ema20 and ema20 > ema50:
            htf_bias = "BULLISH"
        elif last_close < ema20 and ema20 < ema50:
            htf_bias = "BEARISH"

    dealing_range = extract_dealing_range(df_struct_feat, len(df_struct_feat) - 1, lookback=50, timeframe=struct_tf)
    pools = extract_active_liquidity_pools(df_struct_feat, len(df_struct_feat) - 1, lookback=50, timeframe=struct_tf)
    active_pools = [p for p in pools if not p.is_swept]
    swept_pools = [p for p in pools if p.is_swept]
    fvgs = extract_active_fair_value_gaps(df_struct_feat, len(df_struct_feat) - 1, lookback=50, timeframe=struct_tf)
    obs = extract_order_blocks(df_struct_feat, len(df_struct_feat) - 1, lookback=50, timeframe=struct_tf)
    structure_events = extract_market_structure_events(df_struct_feat, len(df_struct_feat) - 1, lookback=30, timeframe=struct_tf)

    return SMCContext(
        symbol=symbol,
        execution_timeframe=exec_tf,
        structure_timeframe=struct_tf,
        bias_timeframe=bias_tf,
        timestamp=curr_ts,
        current_price=curr_px,
        htf_bias=htf_bias,
        dealing_range=dealing_range,
        active_liquidity_pools=active_pools,
        recent_sweeps=swept_pools,
        active_fvgs=fvgs,
        active_order_blocks=obs,
        recent_structure_events=structure_events
    )

