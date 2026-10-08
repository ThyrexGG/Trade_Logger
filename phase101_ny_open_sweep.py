"""Phase 101 — NY-open liquidity sweep + reversal (TJR-style) on NQ and ES.

Research only. Reads broker candles from the local MT5 terminal (read-only),
caches them under .cache/phase101/, and backtests a PRE-REGISTERED grid:

    4 liquidity levels  x  2 entry models  x  2 instruments  = 16 cells

Every rule, cost and pass/fail threshold below was fixed before any result
was looked at. Nothing is tuned afterwards; a negative answer is a result.

Levels (all known before the trade window opens, except the opening range):
  OR   first 5 minutes after 09:30 New York (M5: the 09:30 bar; M15: 09:30-09:45)
  ON   overnight range, previous day 18:00 -> 09:30
  LDN  London session, 02:00 -> 05:00 New York
  PD   previous day's regular session (09:30 -> 16:00) high / low

Entry models (both fade the sweep: high swept -> short, low swept -> long):
  RECLAIM  a bar trades beyond the level, then within SWEEP_BARS a bar CLOSES
           back inside it -> market entry at that close.
  TJR      sweep -> market-structure shift (a close beyond the low/high of the
           3 bars leading into the sweep extreme, within MSS_BARS) -> a fair
           value gap inside that displacement -> limit entry at the gap's near
           edge, valid for FILL_BARS; cancelled if the sweep extreme is broken first.

Risk / exit (identical for every cell):
  stop   = the sweep extreme;  target = 2R;  sweeps only 09:30-11:00 NY,
  entries before 11:00 NY, everything flat at 12:00 NY. One trade per day per
  cell (the first valid setup). A bar touching both stop and target counts as
  a stop; on a limit-fill bar only the stop is checked.

Costs (per trade, in price): the recorded bar spread at entry, plus slippage
on every market execution (RECLAIM entry, stop, time exit): NQ 0.50, ES 0.10.
Trades whose stop is closer than 2x the entry spread are skipped (untradeable).

Verdict per cell (pre-registered):
  CANDIDATE  out-of-sample (last 40% of days) N >= 30, OOS mean R > 0 with the
             Bonferroni-widened (16 cells) bootstrap CI above 0, in-sample mean
             R > 0, random-direction placebo p < 0.05, and the M15 4-year
             replication also positive.
  PROMISING  OOS mean R > 0 with the plain 95% CI above 0, but fails a CANDIDATE test.
  NO_EDGE    everything else.

    python -m phase101_ny_open_sweep            # backtest from cache
    python -m phase101_ny_open_sweep --fetch    # refresh the cache from MT5 first
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, ".cache", "phase101")
RESULT_PATH = os.path.join(CACHE, "phase101_result.json")

SYMBOLS = {"NQ": "NDX100", "ES": "SPX500"}  # FundedNext MT5 CFD names
# Broker server clock vs New York, measured from the data (the 09:30 NY open is the
# biggest bar-range jump of the morning): NY+6 until the weekend of 2024-07-27,
# NY+7 from Monday 2024-07-29 on. Both are DST-aligned with New York.
SERVER_CLOCK_CHANGE = pd.Timestamp("2024-07-28")  # in server time
SERVER_MINUS_NY_HOURS_BEFORE = 6
SERVER_MINUS_NY_HOURS = 7
SLIPPAGE = {"NQ": 0.50, "ES": 0.10}
POINT = 0.01
LEVELS = ("OR", "ON", "LDN", "PD")
ENTRIES = ("RECLAIM", "TJR")
TARGET_R = 2.0
OOS_FRACTION = 0.40
N_CELLS = len(LEVELS) * len(ENTRIES) * len(SYMBOLS)
BOOT = 10_000
PLACEBO = 500
SEED = 101

# bar counts per timeframe
TF_MIN = {"M5": 5, "M15": 15}
SWEEP_BARS = {"M5": 6, "M15": 2}  # RECLAIM: close back inside within 30 min
MSS_BARS = {"M5": 12, "M15": 4}  # TJR: shift within 60 min of the extreme
FILL_BARS = {"M5": 12, "M15": 4}  # TJR: limit valid for 60 min


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def fetch_from_mt5() -> None:  # pragma: no cover - needs the local terminal
    import MetaTrader5 as mt5

    os.makedirs(CACHE, exist_ok=True)
    if not mt5.initialize(timeout=30000):
        raise SystemExit(f"MT5 terminal not reachable: {mt5.last_error()}")
    try:
        now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
        for vsym in SYMBOLS.values():
            mt5.symbol_select(vsym, True)
            for tfn, tf, days in (("M1", mt5.TIMEFRAME_M1, 20), ("M5", mt5.TIMEFRAME_M5, 60), ("M15", mt5.TIMEFRAME_M15, 200)):
                frames, end = [], now
                for _ in range(80):
                    start = end - dt.timedelta(days=days)
                    r = mt5.copy_rates_range(vsym, tf, start, end)
                    if r is None or len(r) == 0:
                        break
                    frames.append(pd.DataFrame(r))
                    end = start
                df = pd.concat(frames).drop_duplicates("time").sort_values("time")
                df.to_csv(os.path.join(CACHE, f"{vsym}_{tfn}_server.csv"), index=False)
    finally:
        mt5.shutdown()


def load(symbol: str, tf: str) -> pd.DataFrame:
    """Bars indexed by New York wall-clock time (bar OPEN time)."""
    df = pd.read_csv(os.path.join(CACHE, f"{SYMBOLS[symbol]}_{tf}_server.csv"))
    server = pd.to_datetime(df["time"], unit="s")
    hours = np.where(server < SERVER_CLOCK_CHANGE, SERVER_MINUS_NY_HOURS_BEFORE, SERVER_MINUS_NY_HOURS)
    ny = server - pd.to_timedelta(hours, unit="h")
    out = pd.DataFrame(
        {
            "open": df["open"].to_numpy(float),
            "high": df["high"].to_numpy(float),
            "low": df["low"].to_numpy(float),
            "close": df["close"].to_numpy(float),
            "spread": df["spread"].to_numpy(float) * POINT,
        },
        index=pd.DatetimeIndex(ny, name="ny"),
    )
    return out[~out.index.duplicated()].sort_index()


def clock_check(df: pd.DataFrame) -> Dict[str, str]:
    """Per calendar year, where is the biggest average jump in bar range between 08:00 and 11:00 NY?"""
    out = {}
    rng = df["high"] - df["low"]
    wk = df.index.weekday < 5
    for year, g in rng[wk].groupby(df.index[wk].year):
        prof = g.groupby(g.index.strftime("%H:%M")).mean().loc["08:00":"11:00"]
        jump = (prof / prof.shift(1)).dropna()
        out[str(year)] = str(jump.idxmax()) if len(jump) else "n/a"
    return out


# ----------------------------------------------------------------------------
# Trade simulation
# ----------------------------------------------------------------------------
@dataclass
class Trade:
    day: str
    symbol: str
    level: str
    entry_model: str
    side: str  # LONG / SHORT
    entry_time: str
    entry: float
    stop: float
    target: float
    risk: float
    exit_time: str
    exit_reason: str
    r_gross: float
    cost_r: float
    r: float


def _simulate_exit(h: np.ndarray, l: np.ndarray, o: np.ndarray, times: pd.DatetimeIndex, start: int, end: int,
                   side: int, entry: float, stop: float, target: float, fill_bar: Optional[int]) -> Tuple[int, float, str]:
    """Walk bars [start, end) after entry. Returns (exit_bar, exit_price, reason).
    side +1 long / -1 short. `fill_bar`: a limit fill on that bar checks only the stop."""
    if fill_bar is not None:
        if (side > 0 and l[fill_bar] <= stop) or (side < 0 and h[fill_bar] >= stop):
            return fill_bar, stop, "stop"
    for k in range(start, end):
        hit_stop = l[k] <= stop if side > 0 else h[k] >= stop
        hit_tgt = h[k] >= target if side > 0 else l[k] <= target
        if hit_stop:
            return k, stop, "stop"
        if hit_tgt:
            return k, target, "target"
    # flat at 12:00: the open of the first bar at/after 12:00 (or the last close we have)
    if end < len(o):
        return end, o[end], "time"
    return end - 1, o[end - 1], "time"


def _day_slices(df: pd.DataFrame) -> Dict[dt.date, pd.DataFrame]:
    return {d: g for d, g in df.groupby(df.index.date)}


def _levels_for_day(df: pd.DataFrame, day: pd.Timestamp, prev_rth: Optional[pd.DataFrame], tf: str) -> Dict[str, Tuple[float, float, pd.Timestamp]]:
    """{level: (high, low, sweeps_allowed_from)}"""
    t930 = day + pd.Timedelta(hours=9, minutes=30)
    lv: Dict[str, Tuple[float, float, pd.Timestamp]] = {}
    or_end = t930 + pd.Timedelta(minutes=5 if tf == "M5" else 15)
    orb = df.loc[t930: or_end - pd.Timedelta(seconds=1)]
    if len(orb):
        lv["OR"] = (orb["high"].max(), orb["low"].min(), or_end)
    on = df.loc[day - pd.Timedelta(hours=6): t930 - pd.Timedelta(seconds=1)]  # prev 18:00 -> 09:30
    if len(on) >= 10:
        lv["ON"] = (on["high"].max(), on["low"].min(), t930)
    ldn = df.loc[day + pd.Timedelta(hours=2): day + pd.Timedelta(hours=5) - pd.Timedelta(seconds=1)]
    if len(ldn) >= 3:
        lv["LDN"] = (ldn["high"].max(), ldn["low"].min(), t930)
    if prev_rth is not None and len(prev_rth) >= 10:
        lv["PD"] = (prev_rth["high"].max(), prev_rth["low"].min(), t930)
    return lv


def backtest(symbol: str, tf: str, df: pd.DataFrame) -> List[Trade]:
    trades: List[Trade] = []
    days = sorted({d for d in df.index.normalize() if d.weekday() < 5})
    h, l, o, c, spr = (df[k].to_numpy() for k in ("high", "low", "open", "close", "spread"))
    idx = df.index
    prev_rth = None
    for day in days:
        t930 = day + pd.Timedelta(hours=9, minutes=30)
        t1100 = day + pd.Timedelta(hours=11)
        t1200 = day + pd.Timedelta(hours=12)
        rth = df.loc[t930: day + pd.Timedelta(hours=16) - pd.Timedelta(seconds=1)]
        if len(rth) < (6 if tf == "M15" else 20):  # holiday / half day / missing data
            prev_rth = rth if len(rth) else prev_rth
            continue
        levels = _levels_for_day(df, day, prev_rth, tf)
        i_end = idx.searchsorted(t1200)  # first bar at/after 12:00
        i_last_entry = idx.searchsorted(t1100)
        for level, (lh, ll, allowed_from) in levels.items():
            i0 = idx.searchsorted(allowed_from)
            for model in ENTRIES:
                t = _first_setup(symbol, tf, model, level, h, l, o, c, spr, idx, i0, i_last_entry, i_end, lh, ll, day)
                if t is not None:
                    trades.append(t)
        prev_rth = rth
    return trades


def _first_setup(symbol, tf, model, level, h, l, o, c, spr, idx, i0, i_last_entry, i_end, lh, ll, day) -> Optional[Trade]:
    """Scan bars for the first sweep of either side that yields a valid entry."""
    best: Optional[Trade] = None
    for side_swept in ("HIGH", "LOW"):
        t = _setup_for_side(symbol, tf, model, level, side_swept, h, l, o, c, spr, idx, i0, i_last_entry, i_end, lh, ll, day)
        if t is not None and (best is None or t.entry_time < best.entry_time):
            best = t
    return best


def _setup_for_side(symbol, tf, model, level, side_swept, h, l, o, c, spr, idx, i0, i_last_entry, i_end, lh, ll, day) -> Optional[Trade]:
    short = side_swept == "HIGH"
    lvl = lh if short else ll
    side = -1 if short else +1
    # first sweep bar in the window
    i_sweep = None
    for i in range(i0, i_last_entry):
        if (short and h[i] > lvl) or (not short and l[i] < lvl):
            i_sweep = i
            break
    if i_sweep is None:
        return None

    if model == "RECLAIM":
        ext = h[i_sweep] if short else l[i_sweep]
        for j in range(i_sweep, min(i_sweep + SWEEP_BARS[tf], i_last_entry)):
            ext = max(ext, h[j]) if short else min(ext, l[j])
            if (short and c[j] < lvl) or (not short and c[j] > lvl):
                entry = c[j]
                return _finish(symbol, model, level, side, day, idx, h, l, o, spr, entry_bar=j, entry=entry,
                               stop=ext, start=j + 1, i_end=i_end, fill_bar=None, market_entry=True)
        return None

    # TJR: sweep -> MSS -> FVG -> limit at the gap's near edge
    ext_bar = i_sweep
    for j in range(i_sweep, min(i_sweep + MSS_BARS[tf], i_last_entry)):
        if (short and h[j] > h[ext_bar]) or (not short and l[j] < l[ext_bar]):
            ext_bar = j
        lead = range(max(0, ext_bar - 3), ext_bar)
        if not lead:
            continue
        ref = min(l[k] for k in lead) if short else max(h[k] for k in lead)
        if j > ext_bar and ((short and c[j] < ref) or (not short and c[j] > ref)):
            # the most recent FVG inside the displacement (ext_bar .. j)
            fvg_edge = None
            for k in range(j, ext_bar + 1, -1):
                if short and l[k - 2] > h[k]:
                    fvg_edge = h[k]
                    break
                if not short and h[k - 2] < l[k]:
                    fvg_edge = l[k]
                    break
            if fvg_edge is None:
                return None
            stop = h[ext_bar] if short else l[ext_bar]
            for f in range(j + 1, min(j + 1 + FILL_BARS[tf], i_last_entry)):
                if (short and h[f] >= stop) or (not short and l[f] <= stop):
                    return None  # extreme broken before the retrace filled us
                if (short and h[f] >= fvg_edge) or (not short and l[f] <= fvg_edge):
                    return _finish(symbol, model, level, side, day, idx, h, l, o, spr, entry_bar=f, entry=fvg_edge,
                                   stop=stop, start=f + 1, i_end=i_end, fill_bar=f, market_entry=False)
            return None
    return None


def _finish(symbol, model, level, side, day, idx, h, l, o, spr, entry_bar, entry, stop, start, i_end, fill_bar, market_entry) -> Optional[Trade]:
    risk = abs(entry - stop)
    spread = float(spr[entry_bar])
    if risk <= 0 or risk < 2 * spread:
        return None
    target = entry + side * TARGET_R * risk
    k, px, reason = _simulate_exit(h, l, o, idx, start, i_end, side, entry, stop, target, fill_bar)
    gross = side * (px - entry)
    slip = SLIPPAGE[symbol]
    cost = spread + (slip if market_entry else 0.0) + (slip if reason in ("stop", "time") else 0.0)
    return Trade(
        day=str(day.date()), symbol=symbol, level=level, entry_model=model, side="LONG" if side > 0 else "SHORT",
        entry_time=str(idx[entry_bar]), entry=round(entry, 2), stop=round(stop, 2), target=round(target, 2),
        risk=round(risk, 2), exit_time=str(idx[min(k, len(idx) - 1)]), exit_reason=reason,
        r_gross=round(gross / risk, 4), cost_r=round(cost / risk, 4), r=round((gross - cost) / risk, 4),
    )


# ----------------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------------
def _boot_ci(x: np.ndarray, alpha: float, rng: np.random.Generator) -> Tuple[float, float]:
    if len(x) < 2:
        return (float("nan"), float("nan"))
    means = rng.choice(x, size=(BOOT, len(x)), replace=True).mean(axis=1)
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def summarize(rs: np.ndarray, rng: np.random.Generator) -> Dict[str, float]:
    if len(rs) == 0:
        return {"n": 0}
    wins, losses = rs[rs > 0].sum(), -rs[rs < 0].sum()
    eq = np.cumsum(rs)
    dd = float((np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq).max())
    lo95, hi95 = _boot_ci(rs, 0.05, rng)
    lob, hib = _boot_ci(rs, 0.05 / N_CELLS, rng)
    return {
        "n": int(len(rs)), "win_rate": round(float((rs > 0).mean()), 3), "mean_r": round(float(rs.mean()), 3),
        "total_r": round(float(rs.sum()), 1), "pf": round(float(wins / losses), 2) if losses > 0 else float("inf"),
        "max_dd_r": round(dd, 1), "ci95": [round(lo95, 3), round(hi95, 3)], "ci_bonf": [round(lob, 3), round(hib, 3)],
    }


def placebo_p(trades: List[Trade], df: pd.DataFrame, rng: np.random.Generator) -> float:
    """Same entry bars, entry prices, stop distances and exits — random direction. p = P(placebo mean >= actual)."""
    if len(trades) < 10:
        return float("nan")
    h, l, o, spr = (df[k].to_numpy() for k in ("high", "low", "open", "spread"))
    idx = df.index
    pre = []
    for t in trades:
        eb = idx.get_loc(pd.Timestamp(t.entry_time))
        day = pd.Timestamp(t.day)
        i_end = idx.searchsorted(day + pd.Timedelta(hours=12))
        res = {}
        for side in (+1, -1):
            stop = t.entry - side * t.risk
            target = t.entry + side * TARGET_R * t.risk
            k, px, reason = _simulate_exit(h, l, o, idx, eb + 1, i_end, side, t.entry, stop, target, None)
            cost = t.cost_r * t.risk
            res[side] = (side * (px - t.entry) - cost) / t.risk
        pre.append(res)
    actual = np.mean([t.r for t in trades])
    sims = np.empty(PLACEBO)
    for s in range(PLACEBO):
        flips = rng.integers(0, 2, len(pre))
        sims[s] = np.mean([p[+1] if f else p[-1] for p, f in zip(pre, flips)])
    return round(float((sims >= actual).mean()), 4)


# ----------------------------------------------------------------------------
# Trade management follow-up (pre-registered after the entry verdict, before
# this run): the SAME entries and stops, different exits.
#   FULL_2R           the original: whole position to 2R
#   PARTIAL_1R_BE     half off at +1R, stop -> entry (from the next bar), rest to 2R
#   PARTIAL_LEVEL_BE  half off at the nearest key level in the trade's direction
#                     (any of the day's OR/ON/LDN/PD highs and lows) that is at
#                     least 0.5R away and short of 2R; none -> +1R. Then as above.
# Everything still flat at 12:00. Costs: entry spread, plus slippage on the
# market entry (RECLAIM) and on each market exit, weighted by the size it closes.
# ----------------------------------------------------------------------------
MANAGEMENT = ("FULL_2R", "PARTIAL_1R_BE", "PARTIAL_LEVEL_BE")
PARTIAL_SIZE = 0.5
KEY_LEVEL_MIN_R = 0.5


def _levels_by_day(df: pd.DataFrame, tf: str) -> Dict[str, List[float]]:
    """day -> every level price known that day (same construction as backtest())."""
    out: Dict[str, List[float]] = {}
    prev_rth = None
    for day in sorted({d for d in df.index.normalize() if d.weekday() < 5}):
        t930 = day + pd.Timedelta(hours=9, minutes=30)
        rth = df.loc[t930: day + pd.Timedelta(hours=16) - pd.Timedelta(seconds=1)]
        lv = _levels_for_day(df, day, prev_rth, tf)
        out[str(day.date())] = [x for (hi, lo, _) in lv.values() for x in (hi, lo)]
        if len(rth):
            prev_rth = rth
    return out


def _simulate_managed(h, l, o, start, end, side, entry, stop, partial_px, fill_bar) -> Tuple[float, str, float]:
    """Half off at `partial_px`, stop to entry, rest to TARGET_R. Returns
    (gross R for the whole position, outcome, fraction of size closed at market)."""
    risk = abs(entry - stop)
    target = entry + side * TARGET_R * risk

    def through(k, px, favourable):
        if favourable:
            return h[k] >= px if side > 0 else l[k] <= px
        return l[k] <= px if side > 0 else h[k] >= px

    if fill_bar is not None and through(fill_bar, stop, False):
        return -1.0, "stop", 1.0
    r1 = None
    for k in range(start, end):
        if r1 is None:
            if through(k, stop, False):
                return -1.0, "stop", 1.0
            if through(k, partial_px, True):
                r1 = side * (partial_px - entry) / risk
                if through(k, target, True):
                    return PARTIAL_SIZE * r1 + (1 - PARTIAL_SIZE) * TARGET_R, "partial+target", 0.0
        else:
            if through(k, entry, False):
                return PARTIAL_SIZE * r1, "partial+breakeven", 1 - PARTIAL_SIZE
            if through(k, target, True):
                return PARTIAL_SIZE * r1 + (1 - PARTIAL_SIZE) * TARGET_R, "partial+target", 0.0
    px = o[end] if end < len(o) else o[end - 1]
    rem = side * (px - entry) / risk
    if r1 is None:
        return rem, "time", 1.0
    return PARTIAL_SIZE * r1 + (1 - PARTIAL_SIZE) * rem, "partial+time", 1 - PARTIAL_SIZE


def managed_r(trades: List[Trade], df: pd.DataFrame, levels: Dict[str, List[float]], mode: str) -> List[Tuple[Trade, float, str]]:
    if mode == "FULL_2R":
        return [(t, t.r, t.exit_reason) for t in trades]
    h, l, o, spr = (df[k].to_numpy() for k in ("high", "low", "open", "spread"))
    idx = df.index
    out = []
    for t in trades:
        side = 1 if t.side == "LONG" else -1
        eb = idx.get_loc(pd.Timestamp(t.entry_time))
        i_end = idx.searchsorted(pd.Timestamp(t.day) + pd.Timedelta(hours=12))
        partial = t.entry + side * 1.0 * t.risk
        if mode == "PARTIAL_LEVEL_BE":
            lo_px = t.entry + side * KEY_LEVEL_MIN_R * t.risk
            ahead = [x for x in levels.get(t.day, [])
                     if (side > 0 and lo_px <= x < t.target) or (side < 0 and t.target < x <= lo_px)]
            if ahead:
                partial = min(ahead) if side > 0 else max(ahead)
        fill_bar = eb if t.entry_model == "TJR" else None
        start = eb + 1
        gross, outcome, mkt_frac = _simulate_managed(h, l, o, start, i_end, side, t.entry, t.stop, partial, fill_bar)
        slip = SLIPPAGE[t.symbol]
        cost = float(spr[eb]) + (slip if t.entry_model == "RECLAIM" else 0.0) + slip * mkt_frac
        out.append((t, gross - cost / t.risk, outcome))
    return out


def run_management() -> Dict:
    rng = np.random.default_rng(SEED)
    res: Dict = {"phase": "101b", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "management": MANAGEMENT, "partial_size": PARTIAL_SIZE, "cells": []}
    for s in SYMBOLS:
        df = load(s, "M5")
        trades = backtest(s, "M5", df)
        levels = _levels_by_day(df, "M5")
        all_days = sorted({str(d.date()) for d in df.index.normalize() if d.weekday() < 5})
        cut = all_days[int(len(all_days) * (1 - OOS_FRACTION))]
        for level in LEVELS:
            for model in ENTRIES:
                cell = [t for t in trades if t.level == level and t.entry_model == model]
                row = {"symbol": s, "level": level, "entry": model, "oos_from": cut}
                for mode in MANAGEMENT:
                    rs = managed_r(cell, df, levels, mode)
                    full = np.array([r for _, r, _ in rs])
                    oos = np.array([r for t, r, _ in rs if t.day >= cut])
                    row[mode] = {
                        "full": summarize(full, rng), "oos": summarize(oos, rng),
                        "outcomes": {k: sum(1 for *_, o_ in rs if o_ == k) for k in sorted({o_ for *_, o_ in rs})},
                    }
                res["cells"].append(row)
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, "phase101_management.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    return res


# ----------------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------------
def run() -> Dict:
    rng = np.random.default_rng(SEED)
    data = {(s, tf): load(s, tf) for s in SYMBOLS for tf in ("M5", "M15")}
    out: Dict = {
        "phase": 101, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "spec": {
            "levels": LEVELS, "entries": ENTRIES, "target_r": TARGET_R, "oos_fraction": OOS_FRACTION,
            "server_minus_ny_hours": {"before_2024-07-28": SERVER_MINUS_NY_HOURS_BEFORE, "from_2024-07-28": SERVER_MINUS_NY_HOURS}, "slippage": SLIPPAGE, "cells": N_CELLS,
        },
        "data": {}, "clock_check": {}, "cells": [], "trades_sample": [],
    }
    all_trades: Dict[Tuple[str, str], List[Trade]] = {}
    for (s, tf), df in data.items():
        out["data"][f"{s}_{tf}"] = {"bars": int(len(df)), "from": str(df.index[0]), "to": str(df.index[-1])}
        out["clock_check"][f"{s}_{tf}"] = clock_check(df)
        all_trades[(s, tf)] = backtest(s, tf, df)

    for s in SYMBOLS:
        trades5 = all_trades[(s, "M5")]
        days5 = sorted({t.day for t in trades5})
        df5 = data[(s, "M5")]
        all_days = sorted({str(d.date()) for d in df5.index.normalize() if d.weekday() < 5})
        cut = all_days[int(len(all_days) * (1 - OOS_FRACTION))]
        for level in LEVELS:
            for model in ENTRIES:
                cell = [t for t in trades5 if t.level == level and t.entry_model == model]
                is_ = np.array([t.r for t in cell if t.day < cut])
                oos = np.array([t.r for t in cell if t.day >= cut])
                rep = np.array([t.r for t in all_trades[(s, "M15")] if t.level == level and t.entry_model == model])
                oos_trades = [t for t in cell if t.day >= cut]
                st_full, st_is, st_oos, st_rep = (summarize(x, rng) for x in (np.array([t.r for t in cell]), is_, oos, rep))
                p = placebo_p(oos_trades, df5, rng)
                verdict = "NO_EDGE"
                if st_oos.get("n", 0) >= 1 and st_oos.get("mean_r", -1) > 0 and st_oos.get("ci95", [-1])[0] > 0:
                    verdict = "PROMISING"
                    if (st_oos["n"] >= 30 and st_oos["ci_bonf"][0] > 0 and st_is.get("mean_r", -1) > 0
                            and p == p and p < 0.05 and st_rep.get("mean_r", -1) > 0):
                        verdict = "CANDIDATE"
                out["cells"].append({
                    "symbol": s, "level": level, "entry": model, "oos_from": cut,
                    "full_m5": st_full, "in_sample": st_is, "out_of_sample": st_oos, "placebo_p_oos": p,
                    "m15_4y_replication": st_rep, "verdict": verdict,
                    "exit_mix_m5": {r: sum(1 for t in cell if t.exit_reason == r) for r in ("target", "stop", "time")},
                    "avg_cost_r": round(float(np.mean([t.cost_r for t in cell])), 3) if cell else None,
                    "long_short": [sum(1 for t in cell if t.side == "LONG"), sum(1 for t in cell if t.side == "SHORT")],
                })
    out["trades_sample"] = [asdict(t) for t in all_trades[("NQ", "M5")][:40]]
    out["verdict"] = (
        "CANDIDATE_FOUND" if any(c["verdict"] == "CANDIDATE" for c in out["cells"])
        else "PROMISING_ONLY" if any(c["verdict"] == "PROMISING" for c in out["cells"])
        else "NO_EDGE"
    )
    os.makedirs(CACHE, exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    with open(os.path.join(CACHE, "phase101_trades.json"), "w", encoding="utf-8") as f:
        json.dump({f"{k[0]}_{k[1]}": [asdict(t) for t in v] for k, v in all_trades.items()}, f, default=str)
    return out


def main(argv=None) -> int:  # pragma: no cover
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch", action="store_true", help="refresh the candle cache from the local MT5 terminal first")
    ap.add_argument("--management", action="store_true", help="compare full-2R vs partial-at-1R / partial-at-key-level + breakeven")
    a = ap.parse_args(argv)
    if a.fetch:
        fetch_from_mt5()
    if a.management:
        m = run_management()
        for c in m["cells"]:
            parts = []
            for mode in MANAGEMENT:
                f, o = c[mode]["full"], c[mode]["oos"]
                parts.append(f"{mode}: N={f.get('n',0)} win={f.get('win_rate','-')} mean={f.get('mean_r','-')} dd={f.get('max_dd_r','-')} oos={o.get('mean_r','-')}")
            print(f"{c['symbol']} {c['level']:<4} {c['entry']:<8} | " + " | ".join(parts))
        return 0
    res = run()
    print(f"verdict: {res['verdict']}")
    for c in res["cells"]:
        o = c["out_of_sample"]
        r = c["m15_4y_replication"]
        print(f"{c['symbol']} {c['level']:<4} {c['entry']:<8} full N={c['full_m5'].get('n',0):>3} mean={c['full_m5'].get('mean_r','-'):>6} | "
              f"OOS N={o.get('n',0):>3} mean={o.get('mean_r','-'):>6} ci95={o.get('ci95')} p={c['placebo_p_oos']} | "
              f"M15-4y N={r.get('n',0):>4} mean={r.get('mean_r','-'):>6} | {c['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
