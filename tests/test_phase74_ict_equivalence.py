# -*- coding: utf-8 -*-
"""
Phase 74 §33 — equivalence of the optimized SMC detectors.

``detect_mss`` / ``detect_liquidity_sweep`` were rewritten to read per-DataFrame
numpy column arrays (``smc_utils._cols``) instead of doing ~10 ``.iloc`` scalar
reads per call. This module pins the new implementations to the pre-Phase-74
``.iloc`` reference logic (reproduced verbatim below) so any future edit that
changes a signal is caught.
"""
import numpy as np
import pandas as pd
import pytest

from strategies import smc_utils


# --- pre-Phase-74 reference implementations (git 531d534), verbatim ----------
def _ref_detect_liquidity_sweep(df, current_index, lookback=50):
    if current_index < lookback:
        return {"sweep": None}
    row = df.iloc[current_index]
    pools = []
    if 'PWH' in df.columns:
        pwh = df['PWH'].iloc[current_index - 1]
        pwl = df['PWL'].iloc[current_index - 1]
        if pd.notna(pwh) and row['High'] > pwh and row['Close'] < pwh:
            pools.append({"sweep": "BSL", "level": pwh, "type": "PWH"})
        if pd.notna(pwl) and row['Low'] < pwl and row['Close'] > pwl:
            pools.append({"sweep": "SSL", "level": pwl, "type": "PWL"})
    if 'PDH' in df.columns:
        pdh = df['PDH'].iloc[current_index - 1]
        pdl = df['PDL'].iloc[current_index - 1]
        if pd.notna(pdh) and row['High'] > pdh and row['Close'] < pdh:
            pools.append({"sweep": "BSL", "level": pdh, "type": "PDH"})
        if pd.notna(pdl) and row['Low'] < pdl and row['Close'] > pdl:
            pools.append({"sweep": "SSL", "level": pdl, "type": "PDL"})
    if 'asian_high' in df.columns:
        ash = df['asian_high'].iloc[current_index - 1]
        asl = df['asian_low'].iloc[current_index - 1]
        if pd.notna(ash) and row['High'] > ash and row['Close'] < ash:
            pools.append({"sweep": "BSL", "level": ash, "type": "ASIAN_HIGH"})
        if pd.notna(asl) and row['Low'] < asl and row['Close'] > asl:
            pools.append({"sweep": "SSL", "level": asl, "type": "ASIAN_LOW"})
    if 'last_eqh' in df.columns:
        last_eqh = df['last_eqh'].iloc[current_index - 1]
        last_eql = df['last_eql'].iloc[current_index - 1]
        if pd.notna(last_eqh) and row['High'] > last_eqh and row['Close'] < last_eqh:
            pools.append({"sweep": "BSL", "level": last_eqh, "type": "EQH"})
        if pd.notna(last_eql) and row['Low'] < last_eql and row['Close'] > last_eql:
            pools.append({"sweep": "SSL", "level": last_eql, "type": "EQL"})
    if 'last_swing_high' in df.columns:
        last_sh = df['last_swing_high'].iloc[current_index - 1]
        last_sl = df['last_swing_low'].iloc[current_index - 1]
        if pd.notna(last_sh) and row['High'] > last_sh and row['Close'] < last_sh:
            pools.append({"sweep": "BSL", "level": last_sh, "type": "SWING_HIGH"})
        if pd.notna(last_sl) and row['Low'] < last_sl and row['Close'] > last_sl:
            pools.append({"sweep": "SSL", "level": last_sl, "type": "SWING_LOW"})
    if pools:
        return pools[0]
    return {"sweep": None, "level": None, "type": None}


def _ref_detect_mss(df, current_index, lookback=20):
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


# --- fixtures ---------------------------------------------------------------
def _synthetic_frame(n=2400, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    steps = rng.normal(0, 1.5, n).cumsum()
    close = 2000.0 + steps
    high = close + rng.uniform(0.2, 3.0, n)
    low = close - rng.uniform(0.2, 3.0, n)
    open_ = close - rng.normal(0, 1.0, n)
    df = pd.DataFrame({"Open": open_, "High": np.maximum.reduce([open_, high, close]),
                       "Low": np.minimum.reduce([open_, low, close]), "Close": close,
                       "Volume": rng.integers(50, 500, n)}, index=idx)
    return smc_utils.add_smc_features(df)


@pytest.fixture(autouse=True)
def _clear_cache():
    smc_utils.invalidate_col_cache()
    yield
    smc_utils.invalidate_col_cache()


def _real_frame():
    """Real ingested MT5 XAUUSD 15m if present — otherwise None."""
    try:
        import historical_data_store as store
        rows = store.get_candles("XAUUSD", "15m")
        if not rows or len(rows) < 3000:
            return None
        df = pd.DataFrame(rows)
        df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("ts")[["open", "high", "low", "close", "volume"]]
        df = df.tail(20000)
        return smc_utils.add_smc_features(df)
    except Exception:
        return None


# --- tests ----------------------------------------------------------------
def test_detect_mss_matches_reference_synthetic():
    df = _synthetic_frame()
    mism = [i for i in range(len(df))
            if smc_utils.detect_mss(df, i) != _ref_detect_mss(df, i)]
    assert not mism, f"{len(mism)} MSS mismatches, first at {mism[:5]}"


def test_detect_liquidity_sweep_matches_reference_synthetic():
    df = _synthetic_frame()
    mism = []
    for i in range(len(df)):
        a = smc_utils.detect_liquidity_sweep(df, i)
        b = _ref_detect_liquidity_sweep(df, i)
        if a.get("sweep") != b.get("sweep") or a.get("type") != b.get("type"):
            mism.append(i)
    assert not mism, f"{len(mism)} sweep mismatches, first at {mism[:5]}"


def test_cache_key_changes_with_frame():
    df1 = _synthetic_frame(n=1200, seed=1)
    df2 = _synthetic_frame(n=1400, seed=2)
    _ = smc_utils.detect_mss(df1, 500)
    _ = smc_utils.detect_mss(df2, 500)
    # both frames cached independently, no cross-contamination
    assert smc_utils.detect_mss(df1, 500) == _ref_detect_mss(df1, 500)
    assert smc_utils.detect_mss(df2, 500) == _ref_detect_mss(df2, 500)


def test_cache_is_bounded():
    for k in range(12):
        smc_utils.detect_mss(_synthetic_frame(n=300 + k, seed=k), 100)
    assert len(smc_utils._COL_CACHE) <= 9


def test_detectors_match_reference_on_real_mt5_data():
    df = _real_frame()
    if df is None:
        pytest.skip("MT5 XAUUSD 15m not ingested / DB unreachable")
    step = max(1, len(df) // 8000)  # sample; full pass is slow but covered by synthetic
    idxs = range(60, len(df), step)
    mss_mism = [i for i in idxs if smc_utils.detect_mss(df, i) != _ref_detect_mss(df, i)]
    swp_mism = [i for i in idxs
                if smc_utils.detect_liquidity_sweep(df, i).get("type")
                != _ref_detect_liquidity_sweep(df, i).get("type")]
    assert not mss_mism and not swp_mism
