# -*- coding: utf-8 -*-
"""
Killzone liquidity-sweep + MSS scanner (W15).

Assistive pattern-flagging only — never a signal, never executed, no
position sizing or entry recommendation. Reuses the existing generic
market-data primitives (`calculate_market_structure`, `calculate_liquidity_zones`,
`detect_active_killzone`, `detect_fvgs`, `get_realtime_candles`) rather than
the frozen XAUUSD-specific research engines (`xauusd_daily_command_center.py`,
`trade_setup_engine.py`) — those are a separate, closed research contract
(frozen strategy, no manual overrides) this module must not touch or import.

What it does: flags candidate "liquidity sweep -> market structure shift"
events on a lower timeframe, checks whether each one's direction agrees with
the higher-timeframe structural bias, and whether it fell inside a named ICT
killzone window. It computes none of these subjectively — every threshold
(swing window, displacement-vs-ATR, sweep-to-shift candle gap) is a plain,
disclosed number, not a hidden judgment call.

Each candidate also gets a `potential_entry`/`potential_stop`/`potential_target`
(the shift level, the sweep level, and the nearest untapped liquidity pool in
the trade's direction — three numbers already shown elsewhere on the page,
just arranged into one plan) plus a `risk_reward` and a `confluence_score`
(0-5, a plain count of disclosed factors met — see `_confluence()`). None of
that is a win probability or a recommendation to take the trade: it is
arithmetic on facts already on screen, laid out so candidates can be sorted
and skimmed instead of read one at a time. A human still judges whether any
of it is worth trading — the same posture as Chart Analyzer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

import market_data

_SWING_LOOKBACK = 5  # bars each side — matches market_data.calculate_market_structure's default
_MAX_CANDLES_AFTER_SWEEP = 6  # how soon after a sweep the shift must occur to count as one event
_MIN_DISPLACEMENT_ATR_MULT = 0.5  # a shift's candle body must be at least this fraction of recent ATR

# Confluence checklist thresholds — plain, disclosed numbers, not a hidden
# model. "Strong" displacement is 2x the bar-inclusion minimum; "quick"
# reaction is a third of the max allowed sweep-to-shift gap; R:R uses the
# same 1.5 floor a lot of discretionary ICT trading itself treats as a
# minimum worth taking. Changing these changes what counts as a star, not
# whether a candidate is flagged at all (find_candidates() doesn't use them).
_STRONG_DISPLACEMENT_ATR_MULT = 1.0
_QUICK_REACTION_MAX_CANDLES = 2
_MIN_WORTHWHILE_RR = 1.5


def _candles_to_df(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    if df.empty:
        return df
    return df.sort_values("time").reset_index(drop=True)


def _killzone_for_timestamp(ts: int) -> str:
    """Historical version of `market_data.detect_active_killzone()` — that one
    only reads the current wall clock; this evaluates an arbitrary candle's
    time against the same ICT EST windows, so past candidates can be tagged."""
    est, _ = market_data._get_tz_eastern_and_utc()
    dt_est = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(est)
    time_float = dt_est.hour + dt_est.minute / 60.0
    if time_float >= 20.0 or time_float < 0.0:
        return "Asian Range (Consolidation)"
    if 2.0 <= time_float < 5.0:
        return "London Killzone (Manipulation/Expansion)"
    if 8.5 <= time_float < 11.0:
        return "NY AM Killzone (Reversal/Continuation)"
    if 13.5 <= time_float < 16.0:
        return "NY PM Killzone"
    return "No Active Killzone (Dead Zone)"


def _swings(df: pd.DataFrame, lookback: int = _SWING_LOOKBACK) -> pd.DataFrame:
    d = df.copy()
    window = lookback * 2 + 1
    d["swing_high"] = d["high"] == d["high"].rolling(window=window, center=True).max()
    d["swing_low"] = d["low"] == d["low"].rolling(window=window, center=True).min()
    return d


def detect_liquidity_sweeps(df: pd.DataFrame, lookback: int = _SWING_LOOKBACK) -> List[Dict[str, Any]]:
    """A sweep: a candle's wick clears a recent, already-confirmed swing point,
    then closes back on the other side of it — a rejection, not a breakout.
    `BSL_SWEEP` = a swing high (buy-side liquidity) got taken; `SSL_SWEEP` = a
    swing low (sell-side liquidity) got taken."""
    if df.empty or len(df) < lookback * 2 + 2:
        return []
    d = _swings(df, lookback)
    swing_highs = d[d["swing_high"]]
    swing_lows = d[d["swing_low"]]
    sweeps: List[Dict[str, Any]] = []

    for i in range(lookback * 2, len(d)):
        row = d.iloc[i]
        prior_highs = swing_highs[swing_highs.index < i]
        prior_lows = swing_lows[swing_lows.index < i]

        if not prior_highs.empty:
            level = float(prior_highs["high"].iloc[-1])
            if row["high"] > level and row["close"] < level:
                sweeps.append({
                    "type": "BSL_SWEEP",
                    "level": round(level, 5),
                    "time": int(row["time"]),
                    "wick_price": round(float(row["high"]), 5),
                    "close_price": round(float(row["close"]), 5),
                })
        if not prior_lows.empty:
            level = float(prior_lows["low"].iloc[-1])
            if row["low"] < level and row["close"] > level:
                sweeps.append({
                    "type": "SSL_SWEEP",
                    "level": round(level, 5),
                    "time": int(row["time"]),
                    "wick_price": round(float(row["low"]), 5),
                    "close_price": round(float(row["close"]), 5),
                })
    return sweeps


def detect_structure_shifts(df: pd.DataFrame, lookback: int = _SWING_LOOKBACK) -> List[Dict[str, Any]]:
    """Every point in the window where price closed beyond the most recent
    opposing confirmed swing point with real displacement (a candle body at
    least `_MIN_DISPLACEMENT_ATR_MULT` x the recent ATR) — a market-structure
    shift, not just a wick poke through the level."""
    if df.empty or len(df) < lookback * 2 + 2:
        return []
    d = _swings(df, lookback)
    swing_highs = d[d["swing_high"]]
    swing_lows = d[d["swing_low"]]

    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift()).abs(),
        (d["low"] - d["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=1).mean()

    shifts: List[Dict[str, Any]] = []
    for i in range(lookback * 2, len(d)):
        row = d.iloc[i]
        body = abs(float(row["close"]) - float(row["open"]))
        atr_i = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else 0.0
        min_body = atr_i * _MIN_DISPLACEMENT_ATR_MULT

        atr_multiple = round(body / atr_i, 2) if atr_i > 0 else None

        prior_highs = swing_highs[swing_highs.index < i]
        if not prior_highs.empty:
            level = float(prior_highs["high"].iloc[-1])
            if row["close"] > level and body >= min_body:
                shifts.append({
                    "direction": "bullish", "level": round(level, 5),
                    "time": int(row["time"]), "close_price": round(float(row["close"]), 5),
                    "atr_multiple": atr_multiple,
                })

        prior_lows = swing_lows[swing_lows.index < i]
        if not prior_lows.empty:
            level = float(prior_lows["low"].iloc[-1])
            if row["close"] < level and body >= min_body:
                shifts.append({
                    "direction": "bearish", "level": round(level, 5),
                    "time": int(row["time"]), "close_price": round(float(row["close"]), 5),
                    "atr_multiple": atr_multiple,
                })
    return shifts


def _bar_index_for_time(df: pd.DataFrame, ts: int) -> int:
    matches = df.index[df["time"] == ts]
    return int(matches[0]) if len(matches) else -1


def find_candidates(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Pairs each structure shift with the nearest prior opposing-direction
    sweep, within `_MAX_CANDLES_AFTER_SWEEP` bars — a bullish shift wants a
    preceding sell-side-liquidity sweep (a stop-hunt low, then reversal up);
    a bearish shift wants a preceding buy-side sweep."""
    sweeps = detect_liquidity_sweeps(df)
    shifts = detect_structure_shifts(df)
    candidates: List[Dict[str, Any]] = []

    seen_sweeps = set()  # (sweep_time, direction) — the first shift after a given sweep is
    # the actual event; later bars still closed beyond the same level are continuation,
    # not a second distinct signal.
    for shift in shifts:
        wanted = "SSL_SWEEP" if shift["direction"] == "bullish" else "BSL_SWEEP"
        matching = [s for s in sweeps if s["type"] == wanted and s["time"] < shift["time"]]
        if not matching:
            continue
        sweep = matching[-1]
        key = (sweep["time"], shift["direction"])
        if key in seen_sweeps:
            continue
        shift_idx = _bar_index_for_time(df, shift["time"])
        sweep_idx = _bar_index_for_time(df, sweep["time"])
        if shift_idx < 0 or sweep_idx < 0 or (shift_idx - sweep_idx) > _MAX_CANDLES_AFTER_SWEEP:
            continue
        seen_sweeps.add(key)
        candidates.append({
            "direction": shift["direction"],
            "sweep_time": sweep["time"],
            "sweep_level": sweep["level"],
            "shift_time": shift["time"],
            "shift_level": shift["level"],
            "killzone": _killzone_for_timestamp(shift["time"]),
            "displacement_atr_mult": shift.get("atr_multiple"),
            "candles_after_sweep": shift_idx - sweep_idx,
        })
    return candidates


def _nearest_target(direction: str, entry: float, liquidity: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """The nearest untapped liquidity pool that lies in the trade's own
    direction of travel (BSL above entry for a long, SSL below for a short) —
    the same "draw on liquidity" concept `calculate_liquidity_zones` already
    surfaces for the whole symbol, just filtered to ones on the right side of
    this specific entry."""
    pools = liquidity.get("bsl", []) if direction == "bullish" else liquidity.get("ssl", [])
    ahead = [p for p in pools if (p["price"] > entry if direction == "bullish" else p["price"] < entry)]
    if not ahead:
        return None
    return min(ahead, key=lambda p: abs(p["price"] - entry))


def _plan_metrics(direction: str, entry: float, stop: float,
                   liquidity: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Entry = the shift level (where the structure actually broke), stop =
    the sweep level (beyond the wick that was swept — if it sweeps again, the
    read was wrong), target = the nearest real liquidity pool in the trade's
    direction. Plain arithmetic on numbers already computed elsewhere on this
    page; not a recommendation to use these exact numbers."""
    target_pool = _nearest_target(direction, entry, liquidity)
    risk = abs(entry - stop)
    out: Dict[str, Any] = {
        "potential_entry": round(entry, 5),
        "potential_stop": round(stop, 5),
        "potential_target": None,
        "risk_reward": None,
    }
    if target_pool is not None and risk > 0:
        target = float(target_pool["price"])
        out["potential_target"] = round(target, 5)
        out["risk_reward"] = round(abs(target - entry) / risk, 2)
    return out


def _confluence(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """A 0-5 checklist score — a count of plain, disclosed, already-shown
    facts this candidate happens to satisfy, NOT a win probability or a
    model's confidence. Every factor is visible elsewhere on the page; this
    just tallies them so candidates can be sorted/skimmed instead of having
    to cross-reference by eye. Thresholds are the module-level constants
    above, all disclosed in `factors`' labels."""
    disp = candidate.get("displacement_atr_mult")
    rr = candidate.get("risk_reward")
    factors = [
        {"label": "Agrees with the higher-timeframe bias", "met": bool(candidate.get("agrees_with_htf_bias"))},
        {"label": "Inside a named ICT killzone (not the dead zone)",
         "met": candidate.get("killzone") != "No Active Killzone (Dead Zone)"},
        {"label": f"Displacement ≥ {_STRONG_DISPLACEMENT_ATR_MULT}x ATR",
         "met": disp is not None and disp >= _STRONG_DISPLACEMENT_ATR_MULT},
        {"label": f"Shift within {_QUICK_REACTION_MAX_CANDLES} candles of the sweep",
         "met": candidate.get("candles_after_sweep", 999) <= _QUICK_REACTION_MAX_CANDLES},
        {"label": f"R:R to nearest liquidity target ≥ {_MIN_WORTHWHILE_RR}",
         "met": rr is not None and rr >= _MIN_WORTHWHILE_RR},
    ]
    return {"confluence_score": sum(1 for f in factors if f["met"]), "confluence_factors": factors}


def scan(symbol: str = "USDJPY", ltf: str = "15m", htf: str = "1h",
         ltf_count: int = 200, htf_count: int = 300) -> Dict[str, Any]:
    """The one entry point the API router calls. Always returns a dict shaped
    for `ChartAnalysisResponse`-style graceful degradation — `ok: False` with
    an `error` string on any data problem, never an exception.

    Default `htf="1h"`, not "1d": `market_data.get_realtime_candles`'s Yahoo
    path caps daily bars at a ~1-month window regardless of the requested
    count, which is too few candles for `calculate_market_structure` to find
    2+ confirmed swings on. 1h vs 15m is also a completely standard ICT
    bias/entry timeframe pairing on its own, not just a workaround. There is
    no true "4h" available from that function either — it silently serves 1h
    candles for a "4h" request (no resampling), so it isn't offered as a
    timeframe option here to avoid the false impression of real 4h bars.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    sym = (symbol or "USDJPY").strip()

    try:
        ltf_candles, ltf_source = market_data.get_candles_with_source(sym, ltf, ltf_count, ttl_sec=30)
        htf_candles, htf_source = market_data.get_candles_with_source(sym, htf, htf_count, ttl_sec=300)
    except Exception as exc:
        return {"ok": False, "symbol": sym.upper(), "error": f"Data fetch failed: {exc}", "timestamp": now_iso}

    ltf_df = _candles_to_df(ltf_candles)
    htf_df = _candles_to_df(htf_candles)
    if ltf_df.empty or htf_df.empty:
        return {"ok": False, "symbol": sym.upper(), "error": "No candle data available for that symbol.", "timestamp": now_iso}

    htf_structure = market_data.calculate_market_structure(htf_df)
    htf_liquidity = market_data.calculate_liquidity_zones(htf_df)
    trend = htf_structure.get("trend", "")
    htf_bias = "bullish" if "Bullish" in trend else ("bearish" if "Bearish" in trend else "neutral")

    candidates = find_candidates(ltf_df)
    for c in candidates:
        c["agrees_with_htf_bias"] = c["direction"] == htf_bias
        c.update(_plan_metrics(c["direction"], c["shift_level"], c["sweep_level"], htf_liquidity))
        c.update(_confluence(c))
    candidates.sort(key=lambda c: c["shift_time"], reverse=True)

    sources = {ltf_source, htf_source}
    fallback_note = " (synthetic fallback — not real market data)" if "synthetic_fallback" in sources else ""

    return {
        "ok": True,
        "symbol": sym.upper(),
        "ltf": ltf,
        "htf": htf,
        "ltf_source": ltf_source,
        "htf_source": htf_source,
        "htf_bias": htf_bias,
        "htf_structure": htf_structure,
        "htf_liquidity_targets": htf_liquidity,
        "current_killzone": market_data.detect_active_killzone(),
        "candidates": candidates[:15],
        "recent_unmitigated_fvgs": market_data.detect_fvgs(ltf_df),
        "disclaimer": (
            "Pattern-flagging only, not a signal — every event here still needs your own "
            "judgment (does the draw on liquidity make sense, do you trust this as a real "
            "killzone, does it actually agree with a higher timeframe). "
            f"Data source: {ltf_source}/{htf_source}{fallback_note}."
        ),
        "timestamp": now_iso,
    }
