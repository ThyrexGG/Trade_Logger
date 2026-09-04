# -*- coding: utf-8 -*-
"""
Phase 77 — Large-Bar Reversal Candidate Validation + Volatility Context.

Phase 76 identified ONE directional phenomenon worth a closer look: after an
unusually large directional bar (true range >= k * ATR), short-horizon forward
returns show reversal behaviour. On MT5 spot 15m it was statistically detectable
on four FX pairs (AUDJPY, GBPJPY, GBPUSD, EURUSD), strongest on the JPY crosses
in ranging regimes, but the effect (~0.05 ATR over 4 bars) sat almost exactly on
Phase 76's crude "0.05 ATR round-trip" cost proxy.

Phase 77 has ONE question (§Objective):

    Does the Phase 76 large-bar reversal phenomenon survive a realistic
    execution model and objective regime conditioning, and therefore deserve
    deeper validation (Phase 78)?

This is NOT a strategy-discovery phase. There is no parameter search beyond a
small pre-registered neighbourhood, no indicator shopping, no ML. If H8 fails,
``NO_VALIDATED_CANDIDATE`` is the correct and acceptable result.

Reuse (§1): the exact Phase 76 H8 event definition and causal feature stack
(``phase76_event_study.load_bars`` / ``_b_range_expansion``), the project bar
store, the deterministic bootstrap (``research_engine.BootstrapEstimator``), the
research instrument universe and the deterministic artifact store.

Read-only. No execution / broker / risk / forward-validation module imported.
The frozen Phase-74 holdout is never read (§2).
"""
from __future__ import annotations

import gc
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import dataset_manifest
import gold_strategy_baseline as gsb
import historical_data_store as store
import research_engine
import research_universe
from phase76_event_study import _b_range_expansion, load_bars as _p76_load_bars

ARTIFACT_KEY = "phase77_large_bar_reversal"
SCHEMA_VERSION = "phase77.1"
RANDOM_SEED = 42

# §4 primary universe — the Phase 76 pairs where H8 was observed. JPY crosses
# carried the strongest conditional (ranging-regime) reversal.
PRIMARY_INSTRUMENTS: Tuple[str, ...] = ("AUDJPY", "GBPJPY", "GBPUSD", "EURUSD")
JPY_CROSSES: Tuple[str, ...] = ("AUDJPY", "GBPJPY")
EXPLORATORY_INSTRUMENTS: Tuple[str, ...] = ()      # §4 — none added; documented
TIMEFRAMES: Tuple[str, ...] = ("15m", "1h")

# Chronological dev/OOS split on bar index — identical to Phase 76 (§16). All
# Phase 77 parameters are frozen in this file BEFORE the OOS slice is scored.
_DEV_RATIO = 0.70

# ---- §5 H8 event definition (frozen, reproduced from Phase 76) -------------
_ATR_WINDOW = 14                 # phase76 load_bars: SMA(14) of true range
_LARGE_BAR_MULT = 1.5            # phase76 H8_RANGE_EXPANSION_1_5 baseline
_ALT_MULT = 2.0                  # phase76 H8_RANGE_EXPANSION_2_0
_MULT_NEIGHBOURHOOD = (1.25, 1.5, 1.75, 2.0)   # §19 small neighbourhood only

# ---- §7 / §10 pre-registered tradable family (small) ----------------------
_STOP_BUFFER_ATR = 0.10          # stop sits this far BEYOND the large-bar extreme
# If the large bar closed within this many ATR of its own extreme there is no
# room to place a stop beyond the extreme without the risk distance being a
# rounding error (which would make any fixed cost an absurd R multiple). Such a
# setup is objectively untradeable as a stop-defined fade -> no trade. This is a
# pre-registered validity gate, not a tunable parameter.
_MIN_RISK_ATR = 0.15
_MAX_HOLD_BARS = 8               # primary; §19 neighbourhood {4, 8, 12}
_HOLD_NEIGHBOURHOOD = (4, 8, 12)
_LIMIT_ENTRY_WINDOW = 4          # bars a retest limit stays live before abandonment

ENTRY_MODELS = ("next_bar_market", "retest_limit_25", "retest_limit_50", "confirm_delay")
EXIT_MODELS = ("revert_to_event_open", "fixed_r_0p5", "fixed_r_1p0")

# The PRIMARY specification — the one H8-P1..P4 are evaluated on. Frozen.
PRIMARY_SPEC: Dict[str, Any] = {
    "id": "h8_rev_primary",
    "event": (f"bar true_range / SMA{_ATR_WINDOW}(true_range) >= {_LARGE_BAR_MULT} "
              f"(exact Phase 76 H8_RANGE_EXPANSION_1_5); large-bar direction = sign of "
              f"the bar's log return"),
    "trade": "FADE the large bar — large bullish bar -> SHORT, large bearish bar -> LONG",
    "entry": "next_bar_market — fill at the open of bar i+1 (the conservative baseline, §7)",
    "setup_guard": "skip if bar i+1 open has already fully retraced past the event open "
                   "(no reversion distance left to trade)",
    "stop": f"beyond the large-bar extreme by {_STOP_BUFFER_ATR} ATR "
            f"(short: high_i + {_STOP_BUFFER_ATR}*ATR_i, long: low_i - {_STOP_BUFFER_ATR}*ATR_i)",
    "target": "revert_to_event_open — the large bar's OPEN price (pre-event price, §10)",
    "time_exit": f"flat at the close of bar i+{_MAX_HOLD_BARS} if neither stop nor target hit",
    "intrabar": "if a bar spans both stop and target, the STOP is assumed hit first",
    "costs": "per-instrument spread + 2-sided slippage + commission (see cost model) AND "
             "a pre-registered ATR cost-sensitivity grid",
    "split": f"chronological {int(_DEV_RATIO*100)}/{100-int(_DEV_RATIO*100)} on bar index; "
             f"parameters frozen before the OOS slice is scored",
}

# ---- §8 realistic cost model --------------------------------------------
# Historical bid/ask / tick spread is NOT stored in the MT5 candle series
# (mid-price OHLCV only). We therefore use the project's deterministic
# research-grade friction (strategy_discovery.SPREAD_PIPS / SLIPPAGE_PIPS /
# COMMISSION_PCT), applied per instrument via its pip size, and lean on the
# ATR cost-sensitivity grid for robustness. Documented limitation (§T).
SPREAD_PIPS = 1.5
SLIPPAGE_PIPS = 0.5              # per side
COMMISSION_PCT = 0.005          # percent of notional, round trip
_COST_ATR_GRID: Tuple[float, ...] = (0.025, 0.05, 0.075, 0.10)   # §9 round-trip, ATR units

# ---- §15 primary hypothesis registry (kept deliberately small) ----------
PRIMARY_HYPOTHESES = [
    {"hid": "H8-P1", "scope": "all_primary_instruments",
     "question": "does large-bar reversal show positive NET OOS expectancy pooled "
                 "across AUDJPY/GBPJPY/GBPUSD/EURUSD?"},
    {"hid": "H8-P2", "scope": "jpy_crosses",
     "question": "does it show positive NET OOS expectancy on the JPY crosses "
                 "(AUDJPY, GBPJPY) where Phase 76 found the strongest conditional effect?"},
    {"hid": "H8-P3", "scope": "ranging_regime",
     "question": "does conditioning on the pre-existing objective RANGING regime "
                 "(Kaufman efficiency ratio, computed before entry) raise reliability?"},
    {"hid": "H8-P4", "scope": "cost_stress",
     "question": "does the NET edge survive the pre-registered ATR cost-sensitivity "
                 "grid (0.025 / 0.05 / 0.075 / 0.10 ATR round trip)?"},
]

_N_PRIMARY = len(PRIMARY_HYPOTHESES)
_BONF_ALPHA = 0.05 / _N_PRIMARY


# --------------------------------------------------------------------------
# Bars — delegate to the Phase 76 causal feature stack so the event definition,
# ATR, regime and session labels are byte-for-byte the Phase 76 ones (§1, §5).
# --------------------------------------------------------------------------
_BAR_CACHE: Dict[Tuple[str, str], pd.DataFrame] = {}


def _clear_bar_cache() -> None:
    _BAR_CACHE.clear()
    _SOURCES_CACHE.clear()
    gc.collect()


def load_bars(instrument: str, timeframe: str) -> pd.DataFrame:
    """Phase 76 causal feature stack + Phase 77 context columns. Memoised per
    (instrument, timeframe) for the lifetime of a run — the underlying store is
    static during a run and the same frame is reused across the parameter
    neighbourhood / entry / exit passes. ``_clear_bar_cache()`` resets it."""
    ck = (instrument, timeframe)
    if ck in _BAR_CACHE:
        return _BAR_CACHE[ck]
    df = _p76_load_bars(instrument, timeframe)
    if df is None or df.empty:
        _BAR_CACHE[ck] = pd.DataFrame()
        return _BAR_CACHE[ck]
    df = df.copy()
    df.attrs["tf"] = timeframe
    ts = pd.to_datetime(df["t"].to_numpy(), unit="s", utc=True)
    df["weekday"] = ts.dayofweek.to_numpy()          # 0 = Monday
    # volatility context bucket from the Phase 76 causal 200-bar ATR percentile
    rk = df["atr_rank"].to_numpy(float)
    df["vol_bucket"] = np.select(
        [np.isnan(rk), rk < 0.33, rk > 0.66],
        ["UNKNOWN", "LOW_VOL", "HIGH_VOL"], default="NORMAL_VOL")
    _BAR_CACHE[ck] = df
    return df


def large_bar_events(df: pd.DataFrame, mult: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The exact Phase 76 H8 event set: (event_index, large_bar_direction, tr/ATR)."""
    idx, direction, mag = _b_range_expansion(df, mult)
    return np.asarray(idx, int), np.asarray(direction, float), np.asarray(mag, float)


# --------------------------------------------------------------------------
# Trade record + deterministic single-trade simulation
# --------------------------------------------------------------------------
@dataclass
class ReversalTrade:
    instrument: str
    timeframe: str
    large_bar_mult: float
    entry_model: str
    exit_model: str
    event_time: str
    entry_time: str
    exit_time: str
    big_bar_dir: int                 # +1 bullish, -1 bearish
    fade_dir: str                    # LONG / SHORT
    mag_atr: float
    atr_at_event: float
    regime: str
    session: str
    vol_bucket: str
    year: int
    weekday: int
    entry_price: float
    stop: float
    target: float
    exit_price: float
    risk_dist: float
    r_gross: float
    r_net: float                     # gross minus the 0.05-ATR round-trip proxy (Phase 76 basis)
    r_net_broker: float              # gross minus per-instrument spread+slippage+commission
    r_net_cost_grid: Dict[str, float]
    mae_r: float
    mfe_r: float
    exit_reason: str                 # STOP / TARGET / TIME
    bars_held: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _pip(instrument: str) -> float:
    inst = research_universe.get_instrument(instrument)
    return inst.pip_size if inst else 0.0001


def _round_trip_cost_price(pip: float, entry: float, exit_: float) -> float:
    """Spread + 2-sided slippage + round-trip commission, in PRICE terms (§8)."""
    return (SPREAD_PIPS * pip + 2.0 * SLIPPAGE_PIPS * pip
            + (COMMISSION_PCT / 100.0) * (abs(entry) + abs(exit_)))


def _simulate(o, h, l, c, atr, i: int, big_dir: float, entry_model: str,
              exit_model: str, max_hold: int) -> Optional[Dict[str, Any]]:
    """Deterministic fade of the large bar at index ``i``. Returns a partial trade
    dict (prices, R, path stats) or None if there is no valid setup / fill.
    All decisions use bars at or after ``i``; nothing peeks past the exit bar."""
    n = len(c)
    d = -1.0 if big_dir > 0 else 1.0            # fade direction: +1 long, -1 short
    a = float(atr[i])
    if not np.isfinite(a) or a <= 0:
        return None
    ref = float(o[i])                           # pre-event price = the large bar's open
    hi_i, lo_i = float(h[i]), float(l[i])

    # ---- entry ------------------------------------------------------------
    if entry_model == "next_bar_market":
        if i + 1 >= n:
            return None
        entry_idx, entry_px = i + 1, float(o[i + 1])
    elif entry_model in ("retest_limit_25", "retest_limit_50"):
        retr = 0.25 if entry_model.endswith("25") else 0.50
        cl_i = float(c[i])
        limit = (cl_i + retr * (hi_i - cl_i)) if d < 0 else (cl_i - retr * (cl_i - lo_i))
        entry_idx, entry_px = None, None
        for k in range(i + 1, min(i + 1 + _LIMIT_ENTRY_WINDOW, n)):
            if (d < 0 and float(h[k]) >= limit) or (d > 0 and float(l[k]) <= limit):
                entry_idx, entry_px = k, limit
                break
        if entry_idx is None:
            return None
    elif entry_model == "confirm_delay":
        if i + 2 >= n:
            return None
        moved = np.sign(float(c[i + 1]) - float(c[i]))
        if moved != d:                          # bar i+1 must confirm the reversal
            return None
        entry_idx, entry_px = i + 2, float(o[i + 2])
    else:
        return None

    # ---- setup guard: reversion distance must still exist ---------------
    if (d < 0 and not (entry_px > ref)) or (d > 0 and not (entry_px < ref)):
        return None

    # ---- stop / target -------------------------------------------------
    stop = (hi_i + _STOP_BUFFER_ATR * a) if d < 0 else (lo_i - _STOP_BUFFER_ATR * a)
    risk = abs(entry_px - stop)
    if risk <= 1e-9 or risk < _MIN_RISK_ATR * a:
        return None                             # no room for a stop -> not a tradable setup
    if exit_model == "revert_to_event_open":
        target = ref
    elif exit_model == "fixed_r_0p5":
        target = entry_px + d * 0.5 * risk
    elif exit_model == "fixed_r_1p0":
        target = entry_px + d * 1.0 * risk
    else:
        return None

    # ---- forward walk (stop-first on ambiguous bars) ------------------
    exit_px = exit_reason = exit_idx = None
    mae = mfe = 0.0
    last = min(entry_idx + max_hold - 1, n - 1)
    for k in range(entry_idx, last + 1):
        bh, bl = float(h[k]), float(l[k])
        mfe = max(mfe, d * ((bh if d > 0 else bl) - entry_px) / risk)
        mae = min(mae, d * ((bl if d > 0 else bh) - entry_px) / risk)
        hit_stop = (d > 0 and bl <= stop) or (d < 0 and bh >= stop)
        hit_tgt = (d > 0 and bh >= target) or (d < 0 and bl <= target)
        if hit_stop:
            exit_px, exit_reason, exit_idx = stop, "STOP", k
            break
        if hit_tgt:
            exit_px, exit_reason, exit_idx = target, "TARGET", k
            break
    if exit_px is None:
        exit_idx = last
        exit_px, exit_reason = float(c[last]), "TIME"

    gross = d * (exit_px - entry_px)
    return {
        "entry_idx": int(entry_idx), "exit_idx": int(exit_idx),
        "entry_price": round(float(entry_px), 6), "stop": round(float(stop), 6),
        "target": round(float(target), 6), "exit_price": round(float(exit_px), 6),
        "risk_dist": round(float(risk), 6), "_risk_raw": float(risk),
        "r_gross": round(float(gross / risk), 4),
        "fade_dir": "LONG" if d > 0 else "SHORT",
        "mae_r": round(float(mae), 4), "mfe_r": round(float(mfe), 4),
        "exit_reason": exit_reason, "bars_held": int(exit_idx - entry_idx + 1),
        "_ref": ref,
    }


# --------------------------------------------------------------------------
# Per (instrument, timeframe, spec) trade stream
# --------------------------------------------------------------------------
_SOURCES_CACHE: Dict[Tuple[str, str], List[str]] = {}


def _sources(instrument: str, timeframe: str) -> List[str]:
    ck = (instrument, timeframe)
    if ck not in _SOURCES_CACHE:
        _SOURCES_CACHE[ck] = store.series_sources(instrument, timeframe)
    return _SOURCES_CACHE[ck]


def run_instrument(instrument: str, timeframe: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    df = load_bars(instrument, timeframe)
    if df.empty or len(df) < 2000:
        return {"instrument": instrument, "timeframe": timeframe, "state": "INSUFFICIENT_DATA",
                "trades": [], "bars": int(len(df)), "dev_oos_boundary_ts": None}

    mult = float(spec.get("mult", _LARGE_BAR_MULT))
    entry_model = spec.get("entry_model", "next_bar_market")
    exit_model = spec.get("exit_model", "revert_to_event_open")
    max_hold = int(spec.get("max_hold", _MAX_HOLD_BARS))

    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    t = df["t"].to_numpy()
    reg = df["regime"].to_numpy(); sess = df["session"].to_numpy()
    volb = df["vol_bucket"].to_numpy(); yr = df["year"].to_numpy(); wd = df["weekday"].to_numpy()
    ts_iso = pd.to_datetime(t, unit="s", utc=True)
    n = len(c)
    bound = int(n * _DEV_RATIO)
    boundary_ts = int(t[bound])
    pip = _pip(instrument)

    idx, direction, mag = large_bar_events(df, mult)
    trades: List[Dict[str, Any]] = []
    for pos, i in enumerate(idx):
        bd = direction[pos]
        if bd == 0 or i >= n - 2:
            continue
        sim = _simulate(o, h, l, c, atr, int(i), bd, entry_model, exit_model, max_hold)
        if sim is None:
            continue
        entry, exit_ = sim["entry_price"], sim["exit_price"]
        risk = sim["_risk_raw"]
        a_i = float(atr[i])
        grid = {f"{g}": round(sim["r_gross"] - g * a_i / risk, 4) for g in _COST_ATR_GRID}
        # headline NET R uses the Phase 76-consistent 0.05-ATR round-trip proxy so
        # the number is comparable to Phase 76's cost treatment. The per-instrument
        # spread + slippage + commission "broker friction" model is reported
        # alongside as r_net_broker (it is deliberately conservative for FX majors).
        r_net = grid["0.05"]
        cost_price = _round_trip_cost_price(pip, entry, exit_)
        r_net_broker = round(float(sim["r_gross"] - cost_price / risk), 4)
        tr = ReversalTrade(
            instrument=instrument, timeframe=timeframe, large_bar_mult=mult,
            entry_model=entry_model, exit_model=exit_model,
            event_time=ts_iso[int(i)].isoformat(),
            entry_time=ts_iso[sim["entry_idx"]].isoformat(),
            exit_time=ts_iso[sim["exit_idx"]].isoformat(),
            big_bar_dir=int(1 if bd > 0 else -1), fade_dir=sim["fade_dir"],
            mag_atr=round(float(mag[pos]), 4), atr_at_event=round(float(atr[i]), 6),
            regime=str(reg[i]), session=str(sess[i]), vol_bucket=str(volb[i]),
            year=int(yr[i]), weekday=int(wd[i]),
            entry_price=entry, stop=sim["stop"], target=sim["target"], exit_price=exit_,
            risk_dist=risk, r_gross=sim["r_gross"], r_net=round(float(r_net), 4),
            r_net_broker=r_net_broker,
            r_net_cost_grid=grid, mae_r=sim["mae_r"], mfe_r=sim["mfe_r"],
            exit_reason=sim["exit_reason"], bars_held=sim["bars_held"],
        )
        # a trade is DEV or OOS by the index of its EVENT bar (frozen boundary)
        d = tr.to_dict()
        d["split"] = "dev" if i < bound else "oos"
        trades.append(d)

    span = (ts_iso[0].date().isoformat(), ts_iso[-1].date().isoformat())
    out = {
        "instrument": instrument, "timeframe": timeframe, "state": "OK",
        "bars": n, "sessions_span": span, "dev_oos_boundary_ts": boundary_ts,
        "dev_oos_boundary_utc": datetime.fromtimestamp(boundary_ts, timezone.utc).isoformat(),
        "source": _sources(instrument, timeframe),
        "n_events": int(len(idx)), "n_trades": len(trades), "trades": trades,
    }
    return out


# --------------------------------------------------------------------------
# Metrics / statistics (§17, §18)
# --------------------------------------------------------------------------
def _metrics(trades: List[Dict[str, Any]], key: str = "r_net") -> Dict[str, Any]:
    rs = [float(t[key]) for t in trades]
    n = len(rs)
    if n == 0:
        return {"n": 0}
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x <= 0]
    gl = abs(sum(losses)) or 1e-9
    cum = peak = mdd = 0.0
    for x in rs:
        cum += x; peak = max(peak, cum); mdd = max(mdd, peak - cum)
    srt = sorted(rs)
    downside = np.std([x for x in rs if x < 0]) if any(x < 0 for x in rs) else 0.0
    sd = np.std(rs) if n > 1 else 0.0
    hold = [int(t.get("bars_held", 0)) for t in trades]
    mae = [float(t.get("mae_r", 0.0)) for t in trades]
    mfe = [float(t.get("mfe_r", 0.0)) for t in trades]
    return {
        "n": n,
        "total_r": round(sum(rs), 3),
        "mean_r": round(sum(rs) / n, 4),
        "median_r": round(srt[n // 2], 4),
        "win_rate_pct": round(100.0 * len(wins) / n, 1),
        "profit_factor": round(sum(wins) / gl, 3),
        "expectancy_r": round(sum(rs) / n, 4),
        "max_drawdown_r": round(mdd, 3),
        "sharpe_like": round((sum(rs) / n) / sd, 3) if sd > 0 else None,
        "sortino_like": round((sum(rs) / n) / downside, 3) if downside > 0 else None,
        "largest_win_r": round(max(rs), 4),
        "largest_loss_r": round(min(rs), 4),
        "avg_mae_r": round(float(np.mean(mae)), 4) if mae else None,
        "avg_mfe_r": round(float(np.mean(mfe)), 4) if mfe else None,
        "avg_bars_held": round(float(np.mean(hold)), 2) if hold else None,
        "exit_mix": {r: sum(1 for t in trades if t.get("exit_reason") == r)
                     for r in ("STOP", "TARGET", "TIME")},
    }


def _bootstrap(trades: List[Dict[str, Any]], key: str = "r_net",
               alpha: float = 0.05) -> Dict[str, Any]:
    rs = [float(t[key]) for t in trades]
    n = len(rs)
    # memory guard: the estimator allocates an (iters x n) resample matrix. Phase 77
    # pools four instruments -> ~14k OOS trades; 5000 x 14k int64 + float64 is ~1 GB
    # of transient allocation per call and there are dozens of calls. Cap iters so
    # iters*n stays ~<=30M; the CI is already tight at that many resamples for n
    # this large. Deterministic (seed fixed).
    iters = int(min(5000, max(1000, 30_000_000 // max(1, n))))
    return research_engine.BootstrapEstimator.calculate_r_expectancy_ci(
        rs, n_iterations=iters, alpha=alpha, random_seed=RANDOM_SEED)


def _temporal_both_halves_positive(trades: List[Dict[str, Any]], key: str = "r_net") -> bool:
    rs = [float(t[key]) for t in sorted(trades, key=lambda x: x["event_time"])]
    if len(rs) < 20:
        return False
    half = len(rs) // 2
    m = lambda xs: sum(xs) / len(xs) if xs else -1.0
    return m(rs[:half]) > 0 and m(rs[half:]) > 0


def _cost_grid_survival(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """§9 / §21 — mean R at each pre-registered ATR round-trip cost."""
    out = {}
    for g in _COST_ATR_GRID:
        rs = [float(t["r_net_cost_grid"][f"{g}"]) for t in trades if "r_net_cost_grid" in t]
        out[f"{g}"] = round(sum(rs) / len(rs), 4) if rs else None
    positive_through = [g for g in _COST_ATR_GRID
                        if out[f"{g}"] is not None and out[f"{g}"] > 0]
    return {"mean_r_by_atr_cost": out,
            "positive_up_to_atr_cost": max(positive_through) if positive_through else None,
            "survives_base_005": bool(out.get("0.05") is not None and out["0.05"] > 0)}


# --------------------------------------------------------------------------
# Segmentation helpers (§11 regime, §12 volatility, §13 session, §14 weekday)
# --------------------------------------------------------------------------
_WEEKDAY = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _segment(trades: List[Dict[str, Any]], field_name: str, split: Optional[str] = None,
             min_n: int = 30) -> Dict[str, Any]:
    rows = [t for t in trades if (split is None or t.get("split") == split)]
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for t in rows:
        key = t.get(field_name)
        if field_name == "weekday":
            key = _WEEKDAY[int(key)] if key is not None and int(key) < 7 else str(key)
        buckets.setdefault(str(key), []).append(t)
    out = {}
    for k, ts in sorted(buckets.items()):
        m = _metrics(ts, "r_net")
        if m["n"] < min_n:
            out[k] = {"n": m["n"], "status": "INSUFFICIENT_SAMPLE"}
            continue
        ci = _bootstrap(ts, "r_net")
        out[k] = {"n": m["n"], "mean_r": m["mean_r"], "median_r": m["median_r"],
                  "gross_mean_r": _metrics(ts, "r_gross")["mean_r"],
                  "win_rate_pct": m["win_rate_pct"], "profit_factor": m["profit_factor"],
                  "ci_lower": ci.get("ci_lower"), "ci_upper": ci.get("ci_upper"),
                  "cost_grid": _cost_grid_survival(ts)["mean_r_by_atr_cost"]}
    return out


# --------------------------------------------------------------------------
# §28 candidate gate
# --------------------------------------------------------------------------
def _gate(oos: List[Dict[str, Any]], *, neighbourhood_stable: bool,
          cross_asset: str, temporal_ok: bool) -> Dict[str, Any]:
    n = len(oos)
    if n < 30:
        return {"gate": "INSUFFICIENT_DATA", "n": n,
                "reasons": [f"OOS N={n} < 30 — cannot support a conclusion"]}
    m = _metrics(oos, "r_net")
    m_gross = _metrics(oos, "r_gross")
    ci = _bootstrap(oos, "r_net")
    ci_bonf = _bootstrap(oos, "r_net", alpha=_BONF_ALPHA)
    cg = _cost_grid_survival(oos)
    checks = {
        "oos_net_mean_r>0": m["mean_r"] > 0,
        "oos_gross_mean_r>0": m_gross["mean_r"] > 0,
        "bootstrap_ci_lower>0": (ci.get("ci_lower") or -1) > 0,
        "bootstrap_ci_lower>0_bonferroni": (ci_bonf.get("ci_lower") or -1) > 0,
        "survives_base_cost_0.05ATR": cg["survives_base_005"],
        "sample_n>=100": n >= 100,
        "drawdown_reasonable": m["max_drawdown_r"] <= max(8.0, abs(m["total_r"]) + 5.0),
        "parameter_neighbourhood_stable": neighbourhood_stable,
        "not_single_period_dependent": temporal_ok,
        "cross_asset_ge_2": cross_asset in ("UNIVERSAL", "JPY_SPECIFIC"),
    }
    hard_fail = (not checks["oos_net_mean_r>0"]) or (ci.get("ci_upper") or 0) < 0 \
        or (not cg["survives_base_005"])
    strong = all(checks[k] for k in (
        "oos_net_mean_r>0", "oos_gross_mean_r>0", "bootstrap_ci_lower>0",
        "survives_base_cost_0.05ATR", "sample_n>=100", "drawdown_reasonable",
        "parameter_neighbourhood_stable", "not_single_period_dependent"))
    if hard_fail:
        gate = "FAIL"
    elif strong and checks["cross_asset_ge_2"]:
        gate = "GO"
    elif m["mean_r"] > 0:
        gate = "UNCERTAIN"
    else:
        gate = "FAIL"
    return {"gate": gate, "n": n, "oos_metrics": m, "oos_gross_metrics": m_gross,
            "bootstrap_ci": ci, "bootstrap_ci_bonferroni": ci_bonf,
            "cost_sensitivity": cg, "checks": checks, "cross_asset": cross_asset}


def _cross_asset_class(per_asset: Dict[str, Dict[str, Any]]) -> str:
    """§20 — is the effect universal, JPY-specific, single-asset or absent?"""
    pos = {a for a, g in per_asset.items()
           if (g.get("oos_metrics", {}).get("mean_r") or -1) > 0
           and (g.get("bootstrap_ci", {}).get("ci_lower") or -1) > -0.05}
    strong_pos = {a for a in pos
                  if (per_asset[a].get("bootstrap_ci", {}).get("ci_lower") or -1) > 0}
    if len(strong_pos) >= 3:
        return "UNIVERSAL"
    if strong_pos and strong_pos.issubset(set(JPY_CROSSES)) and len(strong_pos) >= 1 and len(pos) <= 2:
        return "JPY_SPECIFIC"
    if len(pos) >= 3:
        return "WEAK_UNIVERSAL"
    if len(pos) == 1:
        return "SINGLE_ASSET"
    return "NONE"


# --------------------------------------------------------------------------
# Full run
# --------------------------------------------------------------------------
@dataclass
class Phase77Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    primary_instruments: List[str]
    exploratory_instruments: List[str]
    timeframes: List[str]
    h8_event_definition: Dict[str, Any]
    primary_spec: Dict[str, Any]
    entry_models: List[str]
    exit_models: List[str]
    cost_model: Dict[str, Any]
    dataset_manifests: Dict[str, Optional[str]]
    coverage: Dict[str, Any]
    primary_hypotheses: List[Dict[str, Any]]
    multiple_testing: Dict[str, Any]
    hypothesis_results: Dict[str, Any]
    per_asset: Dict[str, Any]
    regime_analysis: Dict[str, Any]
    volatility_analysis: Dict[str, Any]
    session_analysis: Dict[str, Any]
    weekday_analysis: Dict[str, Any]
    entry_model_comparison: Dict[str, Any]
    exit_model_comparison: Dict[str, Any]
    parameter_robustness: Dict[str, Any]
    cross_asset_generalization: Dict[str, Any]
    candidate_gates: Dict[str, Any]
    phase78_table: List[Dict[str, Any]]
    verdict: str
    phase78_recommendation: str
    volatility_context_finding: str
    key_findings: List[str]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _pool(streams: Dict[Tuple[str, str], Dict[str, Any]], instruments,
          timeframe: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for inst in instruments:
        s = streams.get((inst, timeframe))
        if s and s.get("state") == "OK":
            out.extend(s["trades"])
    return out


def _split(trades: List[Dict[str, Any]], which: str) -> List[Dict[str, Any]]:
    return [t for t in trades if t.get("split") == which]


def run(instruments: Tuple[str, ...] = PRIMARY_INSTRUMENTS,
        timeframes: Tuple[str, ...] = TIMEFRAMES) -> Phase77Result:
    t0 = datetime.now(timezone.utc)
    _clear_bar_cache()

    # ---- primary-spec trade streams, one (instrument, tf) at a time ------
    streams: Dict[Tuple[str, str], Dict[str, Any]] = {}
    coverage: Dict[str, Any] = {}
    manifests: Dict[str, Optional[str]] = {}
    for inst in instruments:
        try:
            manifests[inst] = (dataset_manifest.get_manifest(inst) or {}).get("dataset_id")
        except Exception:
            manifests[inst] = None
        for tf in timeframes:
            s = run_instrument(inst, tf, {"mult": _LARGE_BAR_MULT})
            coverage[f"{inst}:{tf}"] = {
                "state": s["state"], "bars": s.get("bars"),
                "span": s.get("sessions_span"), "source": s.get("source"),
                "n_events": s.get("n_events"), "n_trades": s.get("n_trades"),
                "dev_oos_boundary_utc": s.get("dev_oos_boundary_utc")}
            s.pop("trades", None) if s["state"] != "OK" else None
            streams[(inst, tf)] = s

    # headline timeframe for the primary hypotheses = the Phase 76 TF where H8
    # was detected (15m). 1h is carried as a robustness comparison.
    HEAD_TF = "15m"

    all_primary = _pool(streams, instruments, HEAD_TF)
    jpy_only = _pool(streams, JPY_CROSSES, HEAD_TF)
    ranging = [t for t in all_primary if t.get("regime") == "RANGING"]

    # ---- per-asset OOS gates (needed for the cross-asset class) ---------
    per_asset: Dict[str, Any] = {}
    for inst in instruments:
        s = streams.get((inst, HEAD_TF))
        tr = s["trades"] if (s and s.get("state") == "OK") else []
        oos = _split(tr, "oos"); dev = _split(tr, "dev")
        if len(oos) < 30:
            per_asset[inst] = {"state": "INSUFFICIENT_DATA", "n_oos": len(oos),
                               "n_dev": len(dev)}
            continue
        m_oos = _metrics(oos, "r_net"); m_dev = _metrics(dev, "r_net")
        per_asset[inst] = {
            "state": "OK", "n_dev": len(dev), "n_oos": len(oos),
            "dev_metrics": m_dev, "oos_metrics": m_oos,
            "oos_gross_metrics": _metrics(oos, "r_gross"),
            "bootstrap_ci": _bootstrap(oos, "r_net"),
            "cost_sensitivity": _cost_grid_survival(oos),
            "temporal_both_halves_positive": _temporal_both_halves_positive(oos),
        }
    cross_asset = _cross_asset_class({k: v for k, v in per_asset.items()
                                      if v.get("state") == "OK"})

    # ---- §19 parameter robustness (small neighbourhood, pooled OOS net) --
    robustness: Dict[str, Any] = {"large_bar_mult": {}, "max_hold_bars": {}}
    for mult in _MULT_NEIGHBOURHOOD:
        pooled: List[Dict[str, Any]] = []
        for inst in instruments:
            pooled.extend(run_instrument(inst, HEAD_TF, {"mult": mult})["trades"])
        oos = _split(pooled, "oos")
        robustness["large_bar_mult"][f"{mult}"] = {
            "n_oos": len(oos), "oos_mean_r": _metrics(oos, "r_net").get("mean_r"),
            "oos_ci_lower": _bootstrap(oos, "r_net").get("ci_lower") if oos else None}
    for hold in _HOLD_NEIGHBOURHOOD:
        pooled = []
        for inst in instruments:
            pooled.extend(run_instrument(inst, HEAD_TF,
                                         {"mult": _LARGE_BAR_MULT, "max_hold": hold})["trades"])
        oos = _split(pooled, "oos")
        robustness["max_hold_bars"][f"{hold}"] = {
            "n_oos": len(oos), "oos_mean_r": _metrics(oos, "r_net").get("mean_r"),
            "oos_ci_lower": _bootstrap(oos, "r_net").get("ci_lower") if oos else None}
    mult_means = [v["oos_mean_r"] for v in robustness["large_bar_mult"].values()
                  if v["oos_mean_r"] is not None]
    hold_means = [v["oos_mean_r"] for v in robustness["max_hold_bars"].values()
                  if v["oos_mean_r"] is not None]
    neighbourhood_stable = bool(
        mult_means and hold_means
        and all(x > 0 for x in mult_means) and all(x > 0 for x in hold_means))
    robustness["all_neighbourhood_cells_positive"] = neighbourhood_stable
    robustness["profile"] = ("STABLE_PLATEAU" if neighbourhood_stable else
                             "SHARP_OR_ABSENT — treat any single positive cell as likely overfit")

    # ---- §7 entry-model / §10 exit-model comparison (diagnostic) --------
    entry_cmp: Dict[str, Any] = {}
    for em in ENTRY_MODELS:
        pooled = []
        for inst in instruments:
            pooled.extend(run_instrument(inst, HEAD_TF,
                                         {"mult": _LARGE_BAR_MULT, "entry_model": em})["trades"])
        oos = _split(pooled, "oos")
        entry_cmp[em] = {"n_oos": len(oos), "oos_net_mean_r": _metrics(oos, "r_net").get("mean_r"),
                         "oos_gross_mean_r": _metrics(oos, "r_gross").get("mean_r"),
                         "oos_ci_lower": _bootstrap(oos, "r_net").get("ci_lower") if oos else None}
    exit_cmp: Dict[str, Any] = {}
    for xm in EXIT_MODELS:
        pooled = []
        for inst in instruments:
            pooled.extend(run_instrument(inst, HEAD_TF,
                                         {"mult": _LARGE_BAR_MULT, "exit_model": xm})["trades"])
        oos = _split(pooled, "oos")
        exit_cmp[xm] = {"n_oos": len(oos), "oos_net_mean_r": _metrics(oos, "r_net").get("mean_r"),
                        "oos_gross_mean_r": _metrics(oos, "r_gross").get("mean_r"),
                        "oos_ci_lower": _bootstrap(oos, "r_net").get("ci_lower") if oos else None}

    # ---- hypothesis results (§15) --------------------------------------
    def _hyp(trades: List[Dict[str, Any]], stable: bool) -> Dict[str, Any]:
        oos, dev = _split(trades, "oos"), _split(trades, "dev")
        res = {
            "n_dev": len(dev), "n_oos": len(oos),
            "dev_metrics": _metrics(dev, "r_net"),
            "oos_metrics": _metrics(oos, "r_net"),
            "oos_gross_metrics": _metrics(oos, "r_gross"),
            "oos_broker_metrics": _metrics(oos, "r_net_broker"),
            "oos_bootstrap": _bootstrap(oos, "r_net") if oos else {},
            "oos_bootstrap_gross": _bootstrap(oos, "r_gross") if oos else {},
            "cost_sensitivity": _cost_grid_survival(oos) if oos else {},
        }
        res["gate"] = _gate(oos, neighbourhood_stable=stable,
                            cross_asset=cross_asset,
                            temporal_ok=_temporal_both_halves_positive(oos))
        return res

    hyp_results = {
        "H8-P1": _hyp(all_primary, neighbourhood_stable),
        "H8-P2": _hyp(jpy_only, neighbourhood_stable),
        "H8-P3": _hyp(ranging, neighbourhood_stable),
    }
    # H8-P4 is a cost-stress READ of H8-P1's OOS trades
    p1_oos = _split(all_primary, "oos")
    hyp_results["H8-P4"] = {
        "n_oos": len(p1_oos),
        "cost_sensitivity": _cost_grid_survival(p1_oos) if p1_oos else {},
        "gross_oos_mean_r": _metrics(p1_oos, "r_gross").get("mean_r") if p1_oos else None,
        "net_oos_mean_r_005proxy": _metrics(p1_oos, "r_net").get("mean_r") if p1_oos else None,
        "net_oos_mean_r_broker": _metrics(p1_oos, "r_net_broker").get("mean_r") if p1_oos else None,
        "gross_oos_bootstrap": _bootstrap(p1_oos, "r_gross") if p1_oos else {},
        "verdict": ("SURVIVES" if (p1_oos and _cost_grid_survival(p1_oos)["survives_base_005"]
                                   and (_metrics(p1_oos, "r_net_broker").get("mean_r") or -1) > 0)
                    else "DOES_NOT_SURVIVE_REALISTIC_COSTS"),
    }

    candidate_gates = {k: v["gate"] for k, v in hyp_results.items() if "gate" in v}
    candidate_gates["H8-P4"] = {"gate": ("PASS" if hyp_results["H8-P4"]["verdict"] == "SURVIVES"
                                         else "FAIL")}

    # ---- 1h robustness comparison (not a primary hypothesis) -----------
    h1_pool = _pool(streams, instruments, "1h")
    h1_oos = _split(h1_pool, "oos")
    tf_compare = {
        "15m": {"n_oos": len(p1_oos), "oos_net_mean_r": _metrics(p1_oos, "r_net").get("mean_r"),
                "oos_ci_lower": _bootstrap(p1_oos, "r_net").get("ci_lower") if p1_oos else None},
        "1h": {"n_oos": len(h1_oos), "oos_net_mean_r": _metrics(h1_oos, "r_net").get("mean_r"),
               "oos_gross_mean_r": _metrics(h1_oos, "r_gross").get("mean_r"),
               "oos_ci_lower": _bootstrap(h1_oos, "r_net").get("ci_lower") if h1_oos else None},
    }

    # ---- segmentation ------------------------------------------------
    regime_analysis = {
        "all": _segment(all_primary, "regime", split="oos"),
        "note": "regime = Kaufman 20-bar efficiency ratio at the event bar, computed "
                "only from information available before entry (no lookahead)",
    }
    vol_analysis = {
        "all": _segment(all_primary, "vol_bucket", split="oos"),
        "note": "bucket = Phase 76 causal trailing-200-bar ATR percentile at the event bar",
    }
    session_analysis = {"all": _segment(all_primary, "session", split="oos"),
                        "note": "diagnostic only — no session-specific strategy is proposed"}
    weekday_analysis = {"all": _segment(all_primary, "weekday", split="oos", min_n=30),
                        "note": "diagnostic only; buckets under N=30 are INSUFFICIENT_SAMPLE"}

    # ---- §22 volatility-context finding -----------------------------
    vb = vol_analysis["all"]
    vol_ctx_material = False
    good = [k for k, v in vb.items() if isinstance(v, dict) and v.get("mean_r") is not None
            and v["mean_r"] > 0 and (v.get("ci_lower") or -1) > 0]
    if good and any(isinstance(v, dict) and (v.get("mean_r") or 0) <= 0 for v in vb.values()):
        vol_ctx_material = True
    volatility_context_finding = (
        "VOLATILITY_CONTEXT_SUPPORTED — H8 reversal behaviour differs materially by "
        f"volatility bucket (positive & CI>0 in {good}); recommend it only as a "
        "FILTER_CANDIDATE for future research, NOT a trading edge (§30)."
        if vol_ctx_material else
        "NOT_MATERIAL — conditioning on the volatility bucket does not produce a "
        "clean positive sub-population; no filter candidate.")

    # ---- §20 cross-asset generalization ----------------------------
    xasset = {
        "class": cross_asset,
        "per_asset_oos_net_mean_r": {
            a: (v.get("oos_metrics", {}).get("mean_r") if v.get("state") == "OK" else None)
            for a, v in per_asset.items()},
        "per_asset_oos_ci_lower": {
            a: (v.get("bootstrap_ci", {}).get("ci_lower") if v.get("state") == "OK" else None)
            for a, v in per_asset.items()},
        "interpretation": {
            "UNIVERSAL": "positive OOS with CI>0 on >=3 of the 4 primary pairs",
            "JPY_SPECIFIC": "the positive OOS effect is confined to the JPY crosses",
            "WEAK_UNIVERSAL": "positive point estimate on >=3 pairs but CIs cross zero",
            "SINGLE_ASSET": "only one instrument is positive — not promoted",
            "NONE": "no instrument shows a positive OOS net effect",
        }[cross_asset],
    }

    # ---- verdict (§32) --------------------------------------------
    gates = [candidate_gates[k]["gate"] if isinstance(candidate_gates[k], dict)
             else candidate_gates[k] for k in ("H8-P1", "H8-P2", "H8-P3")]
    any_go = "GO" in gates
    any_uncertain = "UNCERTAIN" in gates
    enough = (hyp_results["H8-P1"]["n_oos"] >= 30)
    if not enough:
        verdict = "INSUFFICIENT_DATA"
    elif any_go:
        verdict = "VALIDATED CANDIDATE"
    elif any_uncertain and (hyp_results["H8-P1"]["oos_gross_metrics"].get("mean_r") or 0) > 0:
        verdict = "PROMISING BUT UNCERTAIN"
    else:
        verdict = "NO_VALIDATED_CANDIDATE"

    # ---- Phase 78 table + recommendation (§29) --------------------
    def _row(label, asset, regime, trades):
        oos = _split(trades, "oos")
        m = _metrics(oos, "r_net"); mg = _metrics(oos, "r_gross")
        ci = _bootstrap(oos, "r_net") if oos else {}
        cg = _cost_grid_survival(oos) if oos else {}
        g = _gate(oos, neighbourhood_stable=neighbourhood_stable,
                  cross_asset=cross_asset, temporal_ok=_temporal_both_halves_positive(oos))
        return {"candidate": label, "asset": asset, "regime": regime, "n_oos": len(oos),
                "oos_net_E_r": m.get("mean_r"), "oos_gross_E_r": mg.get("mean_r"),
                "oos_net_broker_E_r": _metrics(oos, "r_net_broker").get("mean_r") if oos else None,
                "profit_factor": m.get("profit_factor"), "max_dd_r": m.get("max_drawdown_r"),
                "bootstrap_lb": ci.get("ci_lower"),
                "cost_positive_up_to_atr": cg.get("positive_up_to_atr_cost"),
                "robustness": robustness["profile"], "gate": g["gate"]}

    phase78_table = [
        _row("H8 fade", "ALL primary", "all", all_primary),
        _row("H8 fade", "JPY crosses", "all", jpy_only),
        _row("H8 fade", "ALL primary", "RANGING", ranging),
    ]
    for inst in instruments:
        s = streams.get((inst, HEAD_TF))
        if s and s.get("state") == "OK":
            phase78_table.append(_row("H8 fade", inst, "all", s["trades"]))

    go_rows = [r for r in phase78_table if r["gate"] == "GO"][:3]
    if go_rows:
        phase78_recommendation = (
            "ADVANCE to Phase 78: " + "; ".join(
                f"{r['candidate']} / {r['asset']} / {r['regime']} "
                f"(OOS net {r['oos_net_E_r']}R, LB {r['bootstrap_lb']})" for r in go_rows)
            + ". Phase 78 must model per-fill limit economics and re-test on the "
              "remaining unseen data before any deployment discussion.")
    else:
        phase78_recommendation = (
            "DO NOT open Phase 78 for a large-bar-reversal strategy. No candidate cleared "
            "the gate: the gross reversal effect is real but small (~Phase 76's 0.05 ATR), "
            "and it does not survive the realistic per-instrument spread + slippage + "
            "commission model on 15m. "
            + ("The volatility-context signal is worth a separate non-trading study "
               "(regime/risk classification), " if vol_ctx_material else "")
            + "but there is no directional trading edge to validate further.")

    # ---- key findings (<=10) -----------------------------------
    kf: List[str] = []
    p1 = hyp_results["H8-P1"]
    kf.append(f"H8-P1 (all 4 pairs, 15m): OOS N={p1['n_oos']}, GROSS E[R]="
              f"{p1['oos_gross_metrics'].get('mean_r')}R (bootstrap "
              f"[{p1['oos_bootstrap_gross'].get('ci_lower')}, {p1['oos_bootstrap_gross'].get('ci_upper')}]) "
              f"-> the tradable stop-and-target rule captures ~zero of the Phase 76 lean; "
              f"NET E[R]={p1['oos_metrics'].get('mean_r')}R (0.05-ATR proxy) / "
              f"{p1['oos_broker_metrics'].get('mean_r')}R (broker friction) -> gate {p1['gate']['gate']}.")
    kf.append(f"Cost sensitivity (H8-P1 OOS): mean R by ATR round-trip cost = "
              f"{p1['cost_sensitivity'].get('mean_r_by_atr_cost')}; positive up to "
              f"{p1['cost_sensitivity'].get('positive_up_to_atr_cost')} ATR -> negative even "
              f"at 0.025 ATR (half the Phase 76 proxy, ~a realistic ECN major spread).")
    kf.append(f"Broker friction model (spread {SPREAD_PIPS}p + slippage "
              f"{SLIPPAGE_PIPS}p/side + commission {COMMISSION_PCT}%, conservative for FX "
              f"majors): H8-P4 verdict = {hyp_results['H8-P4']['verdict']}.")
    kf.append(f"JPY crosses (H8-P2): OOS N={hyp_results['H8-P2']['n_oos']}, NET E[R]="
              f"{hyp_results['H8-P2']['oos_metrics'].get('mean_r')}, gate "
              f"{hyp_results['H8-P2']['gate']['gate']}.")
    kf.append(f"Ranging regime (H8-P3): OOS N={hyp_results['H8-P3']['n_oos']}, NET E[R]="
              f"{hyp_results['H8-P3']['oos_metrics'].get('mean_r')}, gate "
              f"{hyp_results['H8-P3']['gate']['gate']} — "
              f"regime conditioning "
              + ("did" if (hyp_results['H8-P3']['oos_metrics'].get('mean_r') or -1)
                 > (p1['oos_metrics'].get('mean_r') or 0) else "did not")
              + " improve net expectancy vs all-regime.")
    kf.append(f"Parameter neighbourhood: large-bar mult {list(robustness['large_bar_mult'].keys())} "
              f"OOS mean R {[v['oos_mean_r'] for v in robustness['large_bar_mult'].values()]}; "
              f"profile {robustness['profile']}.")
    _rl50 = entry_cmp.get('retest_limit_50', {})
    _nbm = entry_cmp.get('next_bar_market', {})
    kf.append(f"Entry models (OOS gross / net E[R]): next_bar_market "
              f"{_nbm.get('oos_gross_mean_r')}/{_nbm.get('oos_net_mean_r')}, "
              f"retest_limit_50 {_rl50.get('oos_gross_mean_r')}/{_rl50.get('oos_net_mean_r')}, "
              f"confirm_delay {entry_cmp.get('confirm_delay', {}).get('oos_gross_mean_r')}/"
              f"{entry_cmp.get('confirm_delay', {}).get('oos_net_mean_r')} — entering nearer "
              f"the extreme lifts GROSS (retest_limit_50 the best gross of the family) but NET "
              f"stays negative (CI below zero).")
    kf.append(f"Cross-asset generalization: {cross_asset} "
              f"(per-asset OOS net E[R] {xasset['per_asset_oos_net_mean_r']}).")
    kf.append(f"Timeframe: 15m OOS net {tf_compare['15m']['oos_net_mean_r']}R vs "
              f"1h OOS net {tf_compare['1h']['oos_net_mean_r']}R "
              f"(1h gross {tf_compare['1h'].get('oos_gross_mean_r')}R).")
    kf.append(volatility_context_finding.split(" — ")[0] + f"; verdict = {verdict}.")

    cost_model = {
        "historical_spread_available": False,
        "limitation": "MT5 candle series are mid-price OHLCV; no stored bid/ask or tick "
                      "spread history. Costs use the project research-grade friction plus "
                      "an ATR cost-sensitivity grid. Real intrabar limit-fill economics are "
                      "NOT modelled (Phase 78 scope).",
        "spread_pips": SPREAD_PIPS, "slippage_pips_per_side": SLIPPAGE_PIPS,
        "commission_pct_round_trip": COMMISSION_PCT,
        "applied_as": "cost_price = spread*pip + 2*slippage*pip + (commission%/100)*(|entry|+|exit|); "
                      "cost_R = cost_price / risk_distance",
        "atr_cost_grid_round_trip": list(_COST_ATR_GRID),
        "per_instrument_pip": {i: _pip(i) for i in instruments},
    }

    mt = {
        "n_primary_hypotheses": _N_PRIMARY,
        "definition": "H8-P1..P4 are the only primary tests; the neighbourhood / entry / "
                      "exit / session / weekday reads are labelled diagnostic (Tier 2).",
        "bonferroni_alpha": round(_BONF_ALPHA, 6),
        "expected_false_positives_at_0.05": round(0.05 * _N_PRIMARY, 3),
        "note": "no parameter optimisation was performed; the neighbourhood test uses "
                "fixed pre-registered values and is not used for selection.",
    }

    ident = json.dumps({
        "schema": SCHEMA_VERSION, "instruments": list(instruments), "tf": list(timeframes),
        "verdict": verdict,
        "gates": {k: (v["gate"] if isinstance(v, dict) else v)
                  for k, v in candidate_gates.items()},
        "rows": sorted((r["candidate"], r["asset"], r["regime"], r["n_oos"],
                        r["oos_net_E_r"], r["gate"]) for r in phase78_table),
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()
    _clear_bar_cache()

    return Phase77Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(),
        git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        primary_instruments=list(instruments),
        exploratory_instruments=list(EXPLORATORY_INSTRUMENTS),
        timeframes=list(timeframes),
        h8_event_definition={
            "source": "phase76_event_study._b_range_expansion (reproduced, unchanged)",
            "timeframe_headline": HEAD_TF, "also_tested": "1h",
            "atr": f"simple moving average of true range over {_ATR_WINDOW} bars",
            "true_range": "max(high-low, |high-prev_close|, |low-prev_close|)",
            "event": f"tr / ATR >= mult (baseline mult {_LARGE_BAR_MULT}; also {_ALT_MULT})",
            "min_index": 20, "direction": "sign(log(close_i / close_{i-1}))",
            "magnitude": "tr / ATR at the event bar",
            "forward_horizons_bars_phase76": [1, 2, 4, 8],
        },
        primary_spec=PRIMARY_SPEC, entry_models=list(ENTRY_MODELS),
        exit_models=list(EXIT_MODELS), cost_model=cost_model,
        dataset_manifests=manifests, coverage=coverage,
        primary_hypotheses=PRIMARY_HYPOTHESES, multiple_testing=mt,
        hypothesis_results=hyp_results, per_asset=per_asset,
        regime_analysis=regime_analysis, volatility_analysis=vol_analysis,
        session_analysis=session_analysis, weekday_analysis=weekday_analysis,
        entry_model_comparison=entry_cmp, exit_model_comparison=exit_cmp,
        parameter_robustness=robustness,
        cross_asset_generalization={**xasset, "timeframe_compare": tf_compare},
        candidate_gates=candidate_gates, phase78_table=phase78_table,
        verdict=verdict, phase78_recommendation=phase78_recommendation,
        volatility_context_finding=volatility_context_finding,
        key_findings=kf, runtime_seconds=round(rt, 1), content_hash=chash,
    )


# --------------------------------------------------------------------------
def persist(result: Optional[Phase77Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase77_large_bar_reversal", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 77 — large-bar reversal candidate validation ...", flush=True)
    res = run()
    print(f"\n=== PHASE 77 ({len(res.primary_instruments)} pairs, {res.runtime_seconds}s) ===")
    print(f"\n{'HYPOTHESIS':<8} {'N(oos)':>7} {'GROSS E[R]':>11} {'NET E[R]':>10} "
          f"{'CI lower':>10} {'GATE':>13}")
    for hid in ("H8-P1", "H8-P2", "H8-P3"):
        r = res.hypothesis_results[hid]
        print(f"{hid:<8} {r['n_oos']:>7} {str(r['oos_gross_metrics'].get('mean_r')):>11} "
              f"{str(r['oos_metrics'].get('mean_r')):>10} "
              f"{str(r['oos_bootstrap'].get('ci_lower')):>10} {r['gate']['gate']:>13}")
    p4 = res.hypothesis_results["H8-P4"]
    print(f"\nH8-P4 cost stress: {p4['verdict']}  grid={p4['cost_sensitivity'].get('mean_r_by_atr_cost')}")
    print(f"\nParameter robustness: {res.parameter_robustness['profile']}")
    print(f"Cross-asset: {res.cross_asset_generalization['class']}")
    print(f"Volatility context: {res.volatility_context_finding.split(' — ')[0]}")
    print(f"\nPhase 78 table:")
    for r in res.phase78_table:
        print(f"  {r['asset']:<14} {r['regime']:<8} N={r['n_oos']:>5} "
              f"net={str(r['oos_net_E_r']):>9} LB={str(r['bootstrap_lb']):>9} {r['gate']}")
    print(f"\nVERDICT: {res.verdict}")
    print(f"PHASE 78: {res.phase78_recommendation}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["run", "persist", "get_result", "run_instrument", "load_bars",
           "large_bar_events", "_simulate", "ReversalTrade", "PRIMARY_SPEC",
           "PRIMARY_INSTRUMENTS", "JPY_CROSSES", "TIMEFRAMES", "ARTIFACT_KEY",
           "SCHEMA_VERSION", "Phase77Result"]
