# -*- coding: utf-8 -*-
"""
Phase 100 -- Intraday Setup Co-Pilot.

An honest decision-support tool for discretionary intraday trading on the
11-instrument FX + gold 15m / 1h / 4h universe. It is NOT a signal
generator: Phases 70-93 established that there is no systematic intraday
directional edge in this data, so this tool never says "take this trade".
What it does:

  1. SCAN -- sweep the universe and flag named structural CONDITIONS on
     the most recent bar (liquidity sweeps, range extremes, volatility
     expansion / contraction, session opens, failed breakouts, prior-day
     level tests, inside / narrow-range bars, trend state). Conditions,
     never signals.

  2. BASE RATE -- for any condition (or combination) on an instrument /
     timeframe, compute the forward outcome distribution over ~6 years of
     history: how often price went each way, the median and quartile
     forward moves, favourable / adverse excursion. Attach a blunt
     verdict (NEAR_COIN_FLIP / WEAK_SKEW / NOTABLE_SKEW) and a
     multiple-testing caveat. Most conditions come out near a coin flip
     -- seeing that plainly is the point.

  3. JOURNAL + SKILL TRACKER -- log a setup you are considering
     (instrument, direction, entry / stop / target, tag, thesis); it is
     timestamped and scored against the base rate, your own history on
     that tag, and the current macro-blocker status. Log the outcome.
     After ~30 resolved setups the skill report answers the only
     question that matters: does YOUR selection beat the base rate?

  4. EVALUATE -- the interactive card: given a setup you describe, return
     conditions + base rate + reward:risk feasibility + your track record
     + macro status + a blunt summary, for a human to talk through.

Read-only research. No execution, no broker transmission, no order /
position / account-management import, no risk-engine import. The scanner
NEVER emits BUY / SELL / LONG / SHORT / ENTRY as a recommendation -- a
`direction` field is only ever the USER's input being evaluated. Frozen
Phase-74 Gold holdout never read.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76

SCHEMA_VERSION = "phase100.1"
ARTIFACT_KEY = "phase100_intraday_copilot"
_JOURNAL_ARTIFACT = "phase100_setup_journal"

INTRADAY_UNIVERSE: Tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "XAUUSD",
)
TIMEFRAMES: Tuple[str, ...] = ("15m", "1h", "4h")
_FWD_HORIZONS: Tuple[int, ...] = (1, 2, 4, 8)
_MIN_BASE_RATE_N = 40
_LOW_CONF_N = 120
_WARMUP_BARS = 220

# frozen skew thresholds for the base-rate verdict (deviation of up-rate from 0.5)
_COIN_FLIP = 0.04
_WEAK_SKEW = 0.08

DESIGN_NOTE: Dict[str, Any] = {
    "purpose": "decision support for discretionary intraday trading -- conditions + base rates + a "
               "skill tracker; NOT a signal generator",
    "universe": list(INTRADAY_UNIVERSE),
    "timeframes": list(TIMEFRAMES),
    "honesty": "Phases 70-93 found NO systematic intraday directional edge; this tool never recommends "
               "a trade, it only surfaces historical base rates so the user does not fool themselves",
    "base_rate": f"forward outcome distribution over history at horizons {list(_FWD_HORIZONS)} bars; "
                 f"verdict NEAR_COIN_FLIP (|up_rate-0.5|<{_COIN_FLIP}) / WEAK_SKEW / NOTABLE_SKEW; "
                 f"LOW_CONFIDENCE if n<{_LOW_CONF_N}",
    "skill_tracker": "compares the user's realised expectancy on a tag to the base-rate expectancy for "
                     "the same conditions -> SELECTION_ADDS_EDGE / MATCHES_BASE_RATE / WORSE_THAN_BASE_RATE",
    "multiple_testing": "many conditions x instruments x horizons are scanned; treat any single "
                        "NOTABLE_SKEW as a hypothesis, not a finding",
    "holdout": "frozen Phase-74 Gold holdout never read",
}


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


# ==========================================================================
# Named conditions -- frozen pure functions of the load_bars dataframe.
# Each returns a boolean np.ndarray aligned to df rows (causal: row i uses
# only information available at the close of bar i).
# ==========================================================================
def _arr(df: pd.DataFrame, col: str) -> np.ndarray:
    return df[col].to_numpy(float)


def _roll_max(a: np.ndarray, w: int) -> np.ndarray:
    return pd.Series(a).rolling(w, min_periods=w).max().to_numpy()


def _roll_min(a: np.ndarray, w: int) -> np.ndarray:
    return pd.Series(a).rolling(w, min_periods=w).min().to_numpy()


def _cond_sweep_high(df):
    h, c, pdh = _arr(df, "high"), _arr(df, "close"), _arr(df, "pdh")
    prior20_high = np.concatenate([[np.nan], _roll_max(h, 20)[:-1]])
    lvl = np.where(np.isfinite(pdh), pdh, prior20_high)
    return np.isfinite(lvl) & (h > lvl) & (c < lvl)


def _cond_sweep_low(df):
    lo, c, pdl = _arr(df, "low"), _arr(df, "close"), _arr(df, "pdl")
    prior20_low = np.concatenate([[np.nan], _roll_min(lo, 20)[:-1]])
    lvl = np.where(np.isfinite(pdl), pdl, prior20_low)
    return np.isfinite(lvl) & (lo < lvl) & (c > lvl)


def _cond_range_extreme_high(df):
    h, lo, c = _arr(df, "high"), _arr(df, "low"), _arr(df, "close")
    hi20, lo20 = _roll_max(h, 20), _roll_min(lo, 20)
    rng = hi20 - lo20
    pos = np.where(rng > 0, (c - lo20) / rng, np.nan)
    return np.isfinite(pos) & (pos >= 0.85)


def _cond_range_extreme_low(df):
    h, lo, c = _arr(df, "high"), _arr(df, "low"), _arr(df, "close")
    hi20, lo20 = _roll_max(h, 20), _roll_min(lo, 20)
    rng = hi20 - lo20
    pos = np.where(rng > 0, (c - lo20) / rng, np.nan)
    return np.isfinite(pos) & (pos <= 0.15)


def _cond_vol_expansion(df):
    return _arr(df, "tr_atr") >= 1.6


def _cond_vol_contraction(df):
    return _arr(df, "tr_atr") <= 0.55


def _cond_session_open_london(df):
    s = df["session"].to_numpy()
    prev = np.concatenate([["_"], s[:-1]])
    return (s == "LONDON") & (prev != "LONDON")


def _cond_session_open_ny(df):
    s = df["session"].to_numpy()
    prev = np.concatenate([["_"], s[:-1]])
    return np.isin(s, ["LONDON_NY_OVERLAP", "NEW_YORK"]) & ~np.isin(prev, ["LONDON_NY_OVERLAP", "NEW_YORK"])


def _cond_failed_breakout_up(df):
    h, c = _arr(df, "high"), _arr(df, "close")
    hi20_prior = np.concatenate([[np.nan], _roll_max(h, 20)[:-1]])
    broke = h > hi20_prior
    prev_broke = np.concatenate([[False], broke[:-1]])
    return np.isfinite(hi20_prior) & prev_broke & (c < hi20_prior)


def _cond_failed_breakout_down(df):
    lo, c = _arr(df, "low"), _arr(df, "close")
    lo20_prior = np.concatenate([[np.nan], _roll_min(lo, 20)[:-1]])
    broke = lo < lo20_prior
    prev_broke = np.concatenate([[False], broke[:-1]])
    return np.isfinite(lo20_prior) & prev_broke & (c > lo20_prior)


def _cond_pdh_test(df):
    c, pdh, atr = _arr(df, "close"), _arr(df, "pdh"), _arr(df, "atr")
    return np.isfinite(pdh) & np.isfinite(atr) & (atr > 0) & (np.abs(c - pdh) <= 0.25 * atr)


def _cond_pdl_test(df):
    c, pdl, atr = _arr(df, "close"), _arr(df, "pdl"), _arr(df, "atr")
    return np.isfinite(pdl) & np.isfinite(atr) & (atr > 0) & (np.abs(c - pdl) <= 0.25 * atr)


def _cond_inside_bar(df):
    h, lo = _arr(df, "high"), _arr(df, "low")
    ph = np.concatenate([[np.nan], h[:-1]])
    pl = np.concatenate([[np.nan], lo[:-1]])
    return np.isfinite(ph) & (h < ph) & (lo > pl)


def _cond_narrow_range_7(df):
    tr = _arr(df, "tr")
    win = _roll_min(tr, 7)
    return np.isfinite(win) & (tr <= win + 1e-12)


def _cond_trend_up(df):
    c = _arr(df, "close")
    ret20 = c - np.concatenate([np.full(20, np.nan), c[:-20]])
    return (df["regime"].to_numpy() == "TRENDING") & (ret20 > 0)


def _cond_trend_down(df):
    c = _arr(df, "close")
    ret20 = c - np.concatenate([np.full(20, np.nan), c[:-20]])
    return (df["regime"].to_numpy() == "TRENDING") & (ret20 < 0)


CONDITIONS: Dict[str, Any] = {
    "SWEEP_HIGH": _cond_sweep_high, "SWEEP_LOW": _cond_sweep_low,
    "RANGE_EXTREME_HIGH": _cond_range_extreme_high, "RANGE_EXTREME_LOW": _cond_range_extreme_low,
    "VOL_EXPANSION": _cond_vol_expansion, "VOL_CONTRACTION": _cond_vol_contraction,
    "SESSION_OPEN_LONDON": _cond_session_open_london, "SESSION_OPEN_NY": _cond_session_open_ny,
    "FAILED_BREAKOUT_UP": _cond_failed_breakout_up, "FAILED_BREAKOUT_DOWN": _cond_failed_breakout_down,
    "PDH_TEST": _cond_pdh_test, "PDL_TEST": _cond_pdl_test,
    "INSIDE_BAR": _cond_inside_bar, "NARROW_RANGE_7": _cond_narrow_range_7,
    "TREND_UP": _cond_trend_up, "TREND_DOWN": _cond_trend_down,
}
_CONDITION_DESCRIPTIONS = {
    "SWEEP_HIGH": "high pierced prior-day / 20-bar high then closed back below it (liquidity sweep)",
    "SWEEP_LOW": "low pierced prior-day / 20-bar low then closed back above it (liquidity sweep)",
    "RANGE_EXTREME_HIGH": "close in the top 15% of the trailing 20-bar range",
    "RANGE_EXTREME_LOW": "close in the bottom 15% of the trailing 20-bar range",
    "VOL_EXPANSION": "bar true range >= 1.6x ATR(14)",
    "VOL_CONTRACTION": "bar true range <= 0.55x ATR(14)",
    "SESSION_OPEN_LONDON": "first bar of the London session",
    "SESSION_OPEN_NY": "first bar of the London-NY overlap / New York session",
    "FAILED_BREAKOUT_UP": "prior bar broke the 20-bar high; this bar closed back inside",
    "FAILED_BREAKOUT_DOWN": "prior bar broke the 20-bar low; this bar closed back inside",
    "PDH_TEST": "close within 0.25x ATR of the prior-day high",
    "PDL_TEST": "close within 0.25x ATR of the prior-day low",
    "INSIDE_BAR": "bar range fully inside the prior bar's range",
    "NARROW_RANGE_7": "narrowest true range of the last 7 bars",
    "TREND_UP": "regime TRENDING and trailing 20-bar change positive",
    "TREND_DOWN": "regime TRENDING and trailing 20-bar change negative",
}


# ==========================================================================
# Bar loading -- local parquet cache.
#
# The shared OHLCV store is a slow remote Postgres (a full-history intraday
# pull can exceed its statement timeout). So raw candles are cached to
# local parquet under .cache/phase100/ on first use, refreshed
# INCREMENTALLY (only bars newer than what is cached), and augmented in
# memory. Tests monkeypatch ``p76.load_bars`` / ``store.get_candles`` and
# never touch this path.
# ==========================================================================
_BARS_CACHE: Dict[Tuple[str, str], pd.DataFrame] = {}
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "phase100")
_CACHE_MAX_AGE_DAYS = 8
_FETCH_WINDOW_DAYS = 120


def _cache_path(instrument: str, tf: str) -> str:
    return os.path.join(_CACHE_DIR, f"{instrument}_{tf}.parquet")


def _fetch_raw_windowed(instrument: str, tf: str, since: Optional[int]) -> List[Dict[str, Any]]:
    """Pull raw candles from the store in bounded time windows (so no single
    query hits the remote statement timeout) and concatenate."""
    cov = store.get_coverage(instrument, tf)
    if not cov.last_open_time:
        return []
    start = since if since is not None else (cov.first_open_time or 0)
    end = cov.last_open_time
    step = _FETCH_WINDOW_DAYS * 86400
    out: List[Dict[str, Any]] = []
    seen = set()
    cursor = start
    while cursor <= end:
        chunk = store.get_candles(instrument, tf, start=cursor, end=min(cursor + step, end + 1))
        for c in chunk:
            t = int(c["time"])
            if t not in seen:
                seen.add(t)
                out.append(c)
        cursor += step
    out.sort(key=lambda c: c["time"])
    return out


def _raw_cache(instrument: str, tf: str, refresh: bool = False,
               allow_fetch: bool = True) -> List[Dict[str, Any]]:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = _cache_path(instrument, tf)
    cached: List[Dict[str, Any]] = []
    fresh = False
    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
            cached = df.to_dict("records")
            age_days = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(path)) / 86400.0
            fresh = age_days <= _CACHE_MAX_AGE_DAYS
        except Exception:
            cached = []
    if cached and (fresh or not allow_fetch) and not refresh:
        return cached
    if not allow_fetch:
        return cached                       # may be stale or empty; caller handles it
    since = (max(int(c["time"]) for c in cached) + 1) if cached else None
    new = _fetch_raw_windowed(instrument, tf, since)
    merged = {int(c["time"]): c for c in cached}
    for c in new:
        merged[int(c["time"])] = c
    rows = [merged[k] for k in sorted(merged)]
    if rows:
        try:
            pd.DataFrame(rows).to_parquet(path, index=False)
        except Exception:
            pass
    return rows


def load_intraday(instrument: str, tf: str, refresh: bool = False,
                  allow_fetch: bool = True) -> pd.DataFrame:
    key = (instrument, tf)
    if key in _BARS_CACHE and not refresh:
        return _BARS_CACHE[key]
    raw = _raw_cache(instrument, tf, refresh=refresh, allow_fetch=allow_fetch)
    if not raw:
        _BARS_CACHE[key] = pd.DataFrame()
        return _BARS_CACHE[key]
    from unittest import mock
    with mock.patch.object(p76.store, "get_candles", lambda *a, **k: raw):
        df = p76.load_bars(instrument, tf)
    _BARS_CACHE[key] = df
    return df


def refresh_cache(instruments: Tuple[str, ...] = INTRADAY_UNIVERSE,
                  timeframes: Tuple[str, ...] = TIMEFRAMES) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    _BARS_CACHE.clear()
    for inst in instruments:
        for tf in timeframes:
            try:
                rows = _raw_cache(inst, tf, refresh=True)
                out[f"{inst}_{tf}"] = len(rows)
            except Exception as e:  # pragma: no cover
                out[f"{inst}_{tf}"] = f"ERROR: {e!r}"[:160]
    return out


def _condition_matrix(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    return {name: np.asarray(fn(df), dtype=bool) for name, fn in CONDITIONS.items()}


# ==========================================================================
# SCAN
# ==========================================================================
def scan(instrument: str, tf: str, allow_fetch: bool = True) -> Dict[str, Any]:
    df = load_intraday(instrument, tf, allow_fetch=allow_fetch)
    if df.empty or len(df) < _WARMUP_BARS:
        return {"instrument": instrument, "timeframe": tf,
                "state": "CACHE_NOT_BUILT" if not allow_fetch else "INSUFFICIENT_DATA"}
    cm = _condition_matrix(df)
    i = len(df) - 1
    active = [name for name, mask in cm.items() if bool(mask[i])]
    last = df.iloc[i]
    return {
        "instrument": instrument, "timeframe": tf, "state": "OK",
        "bar_time": datetime.fromtimestamp(int(last["t"]), tz=timezone.utc).isoformat(),
        "close": round(float(last["close"]), 6),
        "session": str(last["session"]), "regime": str(last["regime"]),
        "atr": round(float(last["atr"]), 6) if np.isfinite(last["atr"]) else None,
        "tr_atr": round(float(last["tr_atr"]), 3) if np.isfinite(last["tr_atr"]) else None,
        "prior_day_high": round(float(last["pdh"]), 6) if np.isfinite(last["pdh"]) else None,
        "prior_day_low": round(float(last["pdl"]), 6) if np.isfinite(last["pdl"]) else None,
        "active_conditions": active,
        "active_condition_notes": {c: _CONDITION_DESCRIPTIONS[c] for c in active},
    }


def scan_universe(tf: str = "15m", allow_fetch: bool = False) -> Dict[str, Any]:
    rows = [scan(inst, tf, allow_fetch=allow_fetch) for inst in INTRADAY_UNIVERSE]
    by_condition: Dict[str, List[str]] = {}
    for r in rows:
        for c in r.get("active_conditions", []):
            by_condition.setdefault(c, []).append(r["instrument"])
    return {"timeframe": tf, "generated_at": datetime.now(timezone.utc).isoformat(),
            "instruments": rows, "conditions_active_somewhere": by_condition,
            "note": "Conditions are structural descriptions, not trade signals. Look up the base rate "
                    "before acting on any of them."}


# ==========================================================================
# BASE RATE
# ==========================================================================
def _forward_outcomes(df: pd.DataFrame, idx: np.ndarray, horizon: int) -> Dict[str, Any]:
    c = df["close"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    n = len(df)
    idx = idx[(idx >= _WARMUP_BARS) & (idx + horizon < n)]
    if idx.size < 5:
        return {"n": int(idx.size), "state": "INSUFFICIENT_SAMPLE"}
    entry = c[idx]
    exit_ = c[idx + horizon]
    fwd_ret = np.log(exit_ / entry)
    a = atr[idx]
    fwd_ret_atr = np.where(a > 0, (exit_ - entry) / a, np.nan)
    mfe = np.full(idx.size, np.nan)
    mae = np.full(idx.size, np.nan)
    for k, i0 in enumerate(idx):
        seg_h = h[i0 + 1: i0 + horizon + 1]
        seg_l = lo[i0 + 1: i0 + horizon + 1]
        if seg_h.size and a[k] > 0:
            mfe[k] = (seg_h.max() - entry[k]) / a[k]
            mae[k] = (entry[k] - seg_l.min()) / a[k]
    up_rate = float((fwd_ret > 0).mean())
    dev = abs(up_rate - 0.5)
    verdict = ("NOTABLE_SKEW" if dev >= _WEAK_SKEW else "WEAK_SKEW" if dev >= _COIN_FLIP else "NEAR_COIN_FLIP")
    if idx.size < _LOW_CONF_N:
        verdict += "__LOW_CONFIDENCE"
    return {
        "n": int(idx.size), "state": "OK", "horizon_bars": horizon,
        "up_rate": round(up_rate, 4), "down_rate": round(float((fwd_ret < 0).mean()), 4),
        "median_fwd_ret": round(float(np.median(fwd_ret)), 6),
        "mean_fwd_ret": round(float(np.mean(fwd_ret)), 6),
        "p25_fwd_ret": round(float(np.percentile(fwd_ret, 25)), 6),
        "p75_fwd_ret": round(float(np.percentile(fwd_ret, 75)), 6),
        "mean_abs_move_in_atr": round(float(np.nanmean(np.abs(fwd_ret_atr))), 3),
        "mean_mfe_atr": round(float(np.nanmean(mfe)), 3), "mean_mae_atr": round(float(np.nanmean(mae)), 3),
        "verdict": verdict,
    }


def base_rate(instrument: str, tf: str, conditions: Tuple[str, ...],
              horizons: Tuple[int, ...] = _FWD_HORIZONS, allow_fetch: bool = True) -> Dict[str, Any]:
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        return {"state": "UNKNOWN_CONDITION", "unknown": unknown}
    df = load_intraday(instrument, tf, allow_fetch=allow_fetch)
    if df.empty or len(df) < _WARMUP_BARS + max(horizons) + 10:
        return {"state": "CACHE_NOT_BUILT" if not allow_fetch else "INSUFFICIENT_DATA"}
    cm = _condition_matrix(df)
    mask = np.ones(len(df), dtype=bool)
    for cname in conditions:
        mask &= cm[cname]
    idx = np.where(mask)[0]
    out = {
        "instrument": instrument, "timeframe": tf, "conditions": list(conditions),
        "n_occurrences": int(idx.size),
        "history_span": [datetime.fromtimestamp(int(df["t"].iloc[_WARMUP_BARS]), tz=timezone.utc).date().isoformat(),
                         datetime.fromtimestamp(int(df["t"].iloc[-1]), tz=timezone.utc).date().isoformat()],
        "by_horizon": {f"h{h}": _forward_outcomes(df, idx, h) for h in horizons},
        "caveat": "Many conditions x instruments x horizons are scanned. Treat a single NOTABLE_SKEW as "
                  "a hypothesis to test, not an edge. The unconditional research (Phases 70-93) found no "
                  "systematic intraday directional edge.",
    }
    if idx.size < _MIN_BASE_RATE_N:
        out["state"] = "TOO_FEW_OCCURRENCES"
    else:
        out["state"] = "OK"
    return out


def rr_feasibility(base_rate_result: Dict[str, Any], direction: str, reward_risk: float,
                   horizon: int = 4) -> Dict[str, Any]:
    """Breakeven win rate for a given reward:risk is 1/(1+RR). Compare it to
    the historical rate that price moved the setup's way in these
    conditions. This is a SANITY CHECK, not a green light -- it assumes the
    user's directional read is as good as the base rate, which the
    unconditional research says is not reliably true."""
    hk = f"h{horizon}"
    hr = base_rate_result.get("by_horizon", {}).get(hk, {})
    if hr.get("state") != "OK":
        return {"state": "NO_BASE_RATE"}
    be_win = 1.0 / (1.0 + reward_risk)
    move_rate = hr["up_rate"] if direction.lower() in ("long", "buy", "up") else hr["down_rate"]
    margin = move_rate - be_win
    if margin >= 0.05:
        label = "PLAUSIBLE_IF_DIRECTION_READ_IS_SOUND"
    elif margin >= -0.03:
        label = "MARGINAL"
    else:
        label = "UNLIKELY_TO_BE_POSITIVE_EXPECTANCY"
    return {"state": "OK", "reward_risk": reward_risk, "breakeven_win_rate": round(be_win, 4),
            "historical_move_rate_in_direction": round(move_rate, 4), "margin": round(margin, 4),
            "label": label,
            "note": "Assumes your directional read matches the historical base rate. Phases 70-93 found "
                    "that systematic direction reads do NOT beat the base rate -- so this is a floor "
                    "check, not a confirmation."}


# ==========================================================================
# JOURNAL + SKILL TRACKER
# ==========================================================================
def _load_journal() -> List[Dict[str, Any]]:
    art = store.load_artifact(_JOURNAL_ARTIFACT)
    if not art:
        return []
    return list(art["payload"].get("setups", []))


def _save_journal(setups: List[Dict[str, Any]]) -> None:
    store.save_artifact(_JOURNAL_ARTIFACT, "phase100_setup_journal",
                        {"schema_version": SCHEMA_VERSION, "updated_at": datetime.now(timezone.utc).isoformat(),
                         "setups": setups})


def _macro_context() -> Dict[str, Any]:
    try:
        import macro_intelligence_engine as mie
        ctx = mie.get_macro_context() if hasattr(mie, "get_macro_context") else None
        if isinstance(ctx, dict):
            return {"state": "OK", "summary": ctx.get("summary") or ctx.get("regime") or "see macro engine"}
    except Exception:
        pass
    return {"state": "UNAVAILABLE", "summary": "macro context not available; check the economic calendar manually"}


def log_setup(instrument: str, tf: str, direction: str, entry: float, stop: float, target: float,
              tag: str, thesis: str = "") -> Dict[str, Any]:
    if instrument not in INTRADAY_UNIVERSE:
        return {"state": "UNKNOWN_INSTRUMENT"}
    if direction.lower() not in ("long", "short"):
        return {"state": "BAD_DIRECTION", "note": "direction must be 'long' or 'short'"}
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = round(reward / risk, 3) if risk > 0 else None
    sc = scan(instrument, tf)
    active = sc.get("active_conditions", [])
    br = base_rate(instrument, tf, tuple(active)) if active else {"state": "NO_CONDITIONS"}
    setup = {
        "setup_id": uuid.uuid4().hex[:12],
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument, "timeframe": tf, "direction": direction.lower(),
        "entry": entry, "stop": stop, "target": target, "reward_risk": rr,
        "tag": tag, "thesis": thesis,
        "conditions_at_log": active,
        "base_rate_at_log": br.get("by_horizon", {}).get("h4") if br.get("state") == "OK" else br.get("state"),
        "macro_at_log": _macro_context(),
        "status": "OPEN", "exit_price": None, "realized_r": None, "outcome_note": None,
        "resolved_at": None,
    }
    setups = _load_journal()
    setups.append(setup)
    _save_journal(setups)
    return {"state": "LOGGED", "setup": setup}


def log_outcome(setup_id: str, exit_price: float, outcome_note: str = "") -> Dict[str, Any]:
    setups = _load_journal()
    for s in setups:
        if s["setup_id"] == setup_id:
            if s["status"] != "OPEN":
                return {"state": "ALREADY_RESOLVED", "setup": s}
            risk = abs(s["entry"] - s["stop"])
            sign = 1.0 if s["direction"] == "long" else -1.0
            s["exit_price"] = exit_price
            s["realized_r"] = round(sign * (exit_price - s["entry"]) / risk, 3) if risk > 0 else None
            s["outcome_note"] = outcome_note
            s["status"] = "RESOLVED"
            s["resolved_at"] = datetime.now(timezone.utc).isoformat()
            _save_journal(setups)
            return {"state": "RESOLVED", "setup": s}
    return {"state": "NOT_FOUND"}


def list_setups(status: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
    out = _load_journal()
    if status:
        out = [s for s in out if s["status"] == status.upper()]
    if tag:
        out = [s for s in out if s["tag"] == tag]
    return out


def skill_report(tag: Optional[str] = None) -> Dict[str, Any]:
    resolved = [s for s in _load_journal() if s["status"] == "RESOLVED" and s["realized_r"] is not None]
    if tag:
        resolved = [s for s in resolved if s["tag"] == tag]
    n = len(resolved)
    if n < 5:
        return {"state": "INSUFFICIENT_SAMPLE", "n_resolved": n,
                "note": f"Need ~30 resolved setups{' for tag ' + tag if tag else ''} for a meaningful read."}
    rs = np.array([s["realized_r"] for s in resolved], float)
    win_rate = float((rs > 0).mean())
    expectancy_r = float(rs.mean())
    # base-rate expectancy proxy for the same setups: the h4 mean forward move
    # in ATR, signed by the user's direction, expressed in R via each setup's
    # own reward:risk stop distance in ATR terms is not recoverable here, so we
    # use the up/down-rate at a matched reward:risk as the coin-flip reference.
    ref_expectancies = []
    for s in resolved:
        br = s.get("base_rate_at_log")
        rr = s.get("reward_risk")
        if isinstance(br, dict) and br.get("state") == "OK" and rr:
            mr = br["up_rate"] if s["direction"] == "long" else br["down_rate"]
            ref_expectancies.append(mr * rr - (1 - mr) * 1.0)   # E[R] if the base-rate move-rate were the win rate
    ref_e = float(np.mean(ref_expectancies)) if ref_expectancies else None

    if ref_e is None:
        verdict = "NO_BASE_RATE_REFERENCE"
    elif n < 30:
        verdict = "INSUFFICIENT_SAMPLE_FOR_VERDICT"
    elif expectancy_r > ref_e + 0.15:
        verdict = "SELECTION_ADDS_EDGE"
    elif expectancy_r < ref_e - 0.15:
        verdict = "WORSE_THAN_BASE_RATE"
    else:
        verdict = "MATCHES_BASE_RATE"
    return {
        "state": "OK", "tag": tag or "ALL", "n_resolved": n,
        "your_win_rate": round(win_rate, 3), "your_expectancy_r": round(expectancy_r, 3),
        "your_total_r": round(float(rs.sum()), 2),
        "base_rate_reference_expectancy_r": round(ref_e, 3) if ref_e is not None else None,
        "verdict": verdict,
        "note": "SELECTION_ADDS_EDGE means your discretionary picking beat the historical base rate for "
                "the same conditions -- discretionary skill worth scaling. MATCHES/WORSE means a coin "
                "flip would have done as well or better; the honest move is to stop or change approach.",
    }


# ==========================================================================
# EVALUATE -- the interactive card
# ==========================================================================
def evaluate_setup(instrument: str, tf: str, direction: str, entry: float, stop: float,
                   target: float, tag: str = "adhoc") -> Dict[str, Any]:
    if instrument not in INTRADAY_UNIVERSE:
        return {"state": "UNKNOWN_INSTRUMENT", "universe": list(INTRADAY_UNIVERSE)}
    risk = abs(entry - stop)
    rr = round(abs(target - entry) / risk, 3) if risk > 0 else None
    sc = scan(instrument, tf)
    active = tuple(sc.get("active_conditions", []))
    br = base_rate(instrument, tf, active) if active else {"state": "NO_CONDITIONS_ACTIVE"}
    feas = rr_feasibility(br, direction, rr, horizon=4) if (br.get("state") == "OK" and rr) else {"state": "NO_BASE_RATE"}
    skill = skill_report(tag)

    h4 = br.get("by_horizon", {}).get("h4", {}) if br.get("state") == "OK" else {}
    summary_bits = []
    if not active:
        summary_bits.append("No named conditions are active on the current bar -- this is a discretionary read with no historical anchor.")
    else:
        summary_bits.append(f"Active: {', '.join(active)}.")
    if h4.get("state") == "OK":
        summary_bits.append(f"Over {h4['n']} historical instances, 4 bars forward went {'up' if direction.lower()=='long' else 'down'} "
                            f"{(h4['up_rate'] if direction.lower()=='long' else h4['down_rate']):.0%} of the time "
                            f"({h4['verdict']}); typical move {h4['mean_abs_move_in_atr']}x ATR.")
    if feas.get("state") == "OK":
        summary_bits.append(f"Your {rr}:1 setup needs a {feas['breakeven_win_rate']:.0%} win rate; base rate is {feas['historical_move_rate_in_direction']:.0%} -> {feas['label']}.")
    if skill.get("state") == "OK":
        summary_bits.append(f"Your record on '{tag}': {skill['n_resolved']} trades, {skill['your_win_rate']:.0%} win, "
                            f"{skill['your_expectancy_r']:+.2f}R expectancy ({skill['verdict']}).")
    summary_bits.append("This tool does not tell you to take the trade. It gives you the base rate so you can decide honestly.")

    return {
        "state": "OK", "instrument": instrument, "timeframe": tf, "direction": direction.lower(),
        "entry": entry, "stop": stop, "target": target, "reward_risk": rr,
        "scan": sc, "base_rate": br, "reward_risk_feasibility": feas, "your_track_record": skill,
        "macro": _macro_context(), "summary": " ".join(summary_bits),
    }


# ==========================================================================
# Result container / persistence (a periodic universe snapshot)
# ==========================================================================
@dataclass
class Phase100Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    design_note: Dict[str, Any]
    universe_scan_15m: Dict[str, Any]
    universe_scan_1h: Dict[str, Any]
    sample_base_rates: Dict[str, Any]
    skill_report_all: Dict[str, Any]
    n_setups_logged: int
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    live_automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


_SAMPLE_BASE_RATE_QUERIES: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("EURUSD", "15m", ("SWEEP_LOW",)),
    ("XAUUSD", "15m", ("VOL_EXPANSION", "RANGE_EXTREME_HIGH")),
    ("GBPUSD", "1h", ("FAILED_BREAKOUT_UP",)),
    ("USDJPY", "15m", ("SESSION_OPEN_LONDON",)),
    ("XAUUSD", "1h", ("PDH_TEST",)),
)


def run() -> Phase100Result:
    t0 = datetime.now(timezone.utc)
    s15 = scan_universe("15m", allow_fetch=False)
    s1h = scan_universe("1h", allow_fetch=False)
    samples = {}
    for inst, tf, conds in _SAMPLE_BASE_RATE_QUERIES:
        samples[f"{inst}_{tf}_{'+'.join(conds)}"] = base_rate(inst, tf, conds, allow_fetch=False)
    skill = skill_report()
    n_logged = len(_load_journal())

    s15b = scan_universe("15m", allow_fetch=False)
    determinism_match = (json.dumps(s15["conditions_active_somewhere"], sort_keys=True)
                         == json.dumps(s15b["conditions_active_somewhere"], sort_keys=True))
    ident = json.dumps({"samples": samples, "s15": s15["conditions_active_somewhere"]}, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()
    return Phase100Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash, design_note=DESIGN_NOTE,
        universe_scan_15m=s15, universe_scan_1h=s1h, sample_base_rates=samples,
        skill_report_all=skill, n_setups_logged=n_logged, determinism={"match": determinism_match},
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase100Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase100_intraday_copilot", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    import argparse
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Phase 100 intraday setup co-pilot")
    ap.add_argument("--scan", metavar="TF", help="scan the universe on a timeframe (15m/1h/4h)")
    ap.add_argument("--base-rate", nargs="+", metavar="ARG",
                    help="INSTRUMENT TF COND [COND ...] -- base rate for a condition set")
    ap.add_argument("--skill", action="store_true", help="print the skill report")
    ap.add_argument("--refresh", action="store_true", help="refresh the local bar cache from the store first")
    args = ap.parse_args(_argv)

    if args.refresh:
        print("refreshing local bar cache (this is slow the first time) ...", flush=True)
        print(json.dumps(refresh_cache(), indent=2, default=str))

    if args.scan:
        print(json.dumps(scan_universe(args.scan), indent=2, default=str))
        return 0
    if args.base_rate:
        inst, tf, *conds = args.base_rate
        print(json.dumps(base_rate(inst, tf, tuple(conds)), indent=2, default=str))
        return 0
    if args.skill:
        print(json.dumps(skill_report(), indent=2, default=str))
        return 0

    print("Phase 100 - intraday setup co-pilot ...", flush=True)
    res = run()
    h = persist(res)
    print(f"\n=== PHASE 100 ({res.runtime_seconds}s) ===")
    print(f"\n15m conditions active now: {json.dumps(res.universe_scan_15m['conditions_active_somewhere'], default=str)}")
    print(f"1h  conditions active now: {json.dumps(res.universe_scan_1h['conditions_active_somewhere'], default=str)}")
    print("\nsample base rates (h4):")
    for k, v in res.sample_base_rates.items():
        h4 = v.get("by_horizon", {}).get("h4", {})
        print(f"  {k}: n={v.get('n_occurrences')} up_rate={h4.get('up_rate')} verdict={h4.get('verdict')}")
    print(f"\nskill report: {json.dumps(res.skill_report_all, default=str)}")
    print(f"setups logged: {res.n_setups_logged}")
    print(f"determinism match: {res.determinism['match']}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "INTRADAY_UNIVERSE", "TIMEFRAMES", "CONDITIONS",
    "load_intraday", "refresh_cache", "scan", "scan_universe", "base_rate", "rr_feasibility",
    "log_setup", "log_outcome", "list_setups", "skill_report", "evaluate_setup", "run", "persist",
    "get_result", "main",
]
