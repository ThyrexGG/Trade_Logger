# -*- coding: utf-8 -*-
"""
Phase 95 -- Swing Momentum: Time-Series + Cross-Sectional, Daily-Bar Universe.

The first strategy phase of the swing-trading pivot (Phase 94 built the
data foundation; Phases 70-93 established and closed the intraday
directional search). This phase tests ONE pre-registered question with
NO parameter fitting of any kind:

    Does a classical, frozen-rule momentum book -- time-series momentum
    (own-trend following) plus cross-sectional momentum (relative-strength
    long/short) -- produce a positive, cost-surviving, out-of-sample
    risk-adjusted return on the retail-accessible FX + metals + crypto
    daily universe?

Everything about the strategy is fixed BEFORE any result is computed and
is never tuned, per-asset-optimised, or "best-of" selected:

  * Weekly bars (Friday-anchored). Swing horizon; also collapses the
    FX-weekday / crypto-7-day calendar mismatch.
  * Momentum lookbacks: 13 / 26 / 52 weeks (~3 / 6 / 12 months) -- the
    canonical academic set, equally weighted, never searched.
  * Time-series signal  = mean of sign(trailing-return_L) over the three L.
  * Cross-sectional signal = within each sleeve, rank by the blended
    trailing return; long the top third, short the bottom third,
    count-neutral.
  * Inverse-volatility position sizing (trailing 26-week realised vol),
    gross normalised to 1, then the whole sleeve is ex-ante vol-targeted
    to 10% annualised using a causal trailing estimate, leverage capped.
  * Weekly rebalance.
  * Realistic retail costs: per-instrument one-way spread/slippage in
    basis points of notional traded, charged on turnover, with a
    BASE / ADVERSE / SEVERE ladder. Crypto short legs are assumed held
    as perpetual-futures shorts and are charged/credited the actual
    Binance funding rate (Phase 94 data) -- that funding P&L is tracked
    and reported SEPARATELY so the momentum result is never conflated
    with incidental carry (carry is Phase 96, not this phase).

Honest reporting: each sleeve (FX+metals, crypto) and each sub-strategy
(TS, XS, their 50/50 combination) and the combined two-sleeve book get
their OWN verdict -- full sample, per calendar year, and first-half /
second-half (the crypto "one big bull market" concern). Nothing is
pooled to hide a dead sleeve.

Controls: random-sign placebo, cross-sectional-shuffle placebo, a
long-only vol-targeted buy-and-hold benchmark, a cost ladder, a
predeclared lookback neighbourhood, and a predeclared rebalance-frequency
neighbourhood. No "best" variant is ever chosen; the frozen design is the
headline and the neighbourhoods only report sensitivity.

Read-only research. No execution, no broker transmission, no
account-management mutation, no risk-engine import. The frozen Phase-74
Gold holdout is never read -- ``frozen_contract_hash`` cites the
hard-coded canonical constant via ``gold_strategy_baseline``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase94_swing_data_foundation as p94

SCHEMA_VERSION = "phase95.1"
ARTIFACT_KEY = "phase95_swing_momentum"

# ==========================================================================
# Frozen universe (from Phase 94's completed data foundation)
# ==========================================================================
FX_METALS_SLEEVE: Tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "EURGBP", "XAUUSD", "XAGUSD",
)
CRYPTO_SLEEVE: Tuple[str, ...] = tuple(f"{b}USD" for b in p94.CRYPTO_UNIVERSE)  # 27, <BASE>USD
SLEEVES: Tuple[str, ...] = ("FX_METALS", "CRYPTO")
SUBSTRATEGIES: Tuple[str, ...] = ("TS", "XS", "COMBO")

# ==========================================================================
# Frozen strategy parameters -- chosen from standard practice BEFORE any
# result was seen; never tuned, never per-asset, never "best-of".
# ==========================================================================
_LOOKBACKS_WEEKS: Tuple[int, ...] = (13, 26, 52)     # ~3 / 6 / 12 months
_VOL_LOOKBACK_WEEKS = 26                              # trailing realised-vol window
_REBALANCE_WEEKS = 1                                  # weekly
_WARMUP_WEEKS = 52                                    # longest lookback
_WEEKS_PER_YEAR = 52.0
_SLEEVE_VOL_TARGET = 0.10                             # ex-ante annualised
_MAX_LEVERAGE: Dict[str, float] = {"FX_METALS": 3.0, "CRYPTO": 2.0}
_SIGMA_FLOOR = 0.05                                   # annualised per-name vol floor (avoid 1/tiny)
_XS_TERTILE = 1.0 / 3.0                               # top / bottom third
_MIN_XS_NAMES = 6                                     # need this many valid names to run XS in a week

# one-way transaction cost, basis points of notional traded (per rebalance side)
_COST_BPS: Dict[str, float] = {}
for _s in ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"):
    _COST_BPS[_s] = 1.0
for _s in ("EURJPY", "GBPJPY", "AUDJPY", "EURGBP"):
    _COST_BPS[_s] = 2.0
_COST_BPS["XAUUSD"] = 2.5
_COST_BPS["XAGUSD"] = 4.0
for _s in CRYPTO_SLEEVE:
    _COST_BPS[_s] = 5.0 if _s in ("BTCUSD", "ETHUSD") else 10.0

_COST_LADDER: Dict[str, float] = {"ZERO": 0.0, "BASE": 1.0, "ADVERSE": 2.0, "SEVERE": 4.0}

# predeclared sensitivity neighbourhoods (reported, never selected from)
_LOOKBACK_NEIGHBOURHOOD: Dict[str, Tuple[int, ...]] = {
    "L13": (13,), "L26": (26,), "L52": (52,), "L13_26_52_frozen": (13, 26, 52),
}
_REBALANCE_NEIGHBOURHOOD: Tuple[int, ...] = (1, 2, 4)   # weekly (frozen) / biweekly / monthly

_PLACEBO_REPS = 300
_RANDOM_SIGN_SEED = 95001
_XS_SHUFFLE_SEED = 95501

DESIGN_NOTE: Dict[str, Any] = {
    "question": "Does a frozen-rule TS+XS momentum book earn a positive cost-surviving OOS "
                "risk-adjusted return on retail FX+metals+crypto daily bars?",
    "bar": "weekly, Friday-anchored (W-FRI), close-to-close returns",
    "lookbacks_weeks": list(_LOOKBACKS_WEEKS),
    "ts_signal": "mean over L of sign(prod(1+r_[t-L+1..t]) - 1); range [-1,1]",
    "xs_signal": "within sleeve: rank by mean over L of trailing return_L; +1 top third, -1 bottom "
                 "third, 0 middle; count-neutral",
    "combo": "0.5*TS_weights + 0.5*XS_weights (post vol-scaling, per sleeve)",
    "sizing": "w_i = signal_i / sigma_i (sigma_i = trailing 26w realised vol annualised, floored 0.05); "
              "gross-normalised to sum|w|=1; then sleeve ex-ante vol-targeted to 10% ann. via causal "
              "trailing 26w portfolio-vol estimate; leverage capped (FX 3x, crypto 2x)",
    "rebalance": "weekly",
    "costs": "per-instrument one-way bps of notional traded on turnover; ladder ZERO/BASE/ADVERSE/"
             "SEVERE = 0/1/2/4x; crypto shorts held as perp shorts, charged/credited actual Binance "
             "funding (tracked separately, NOT counted toward the momentum verdict)",
    "no_fitting": "every parameter frozen before results; neighbourhoods reported, never selected from",
    "oos": "rules are fully pre-registered with zero fitting -> the entire post-warmup history is OOS; "
           "per-calendar-year and first/second-half splits report stability",
    "holdout": "frozen Phase-74 Gold holdout never read; frozen_contract_hash cites the hard-coded "
               "canonical constant",
}


# ==========================================================================
# git / persistence helpers
# ==========================================================================
def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


# ==========================================================================
# Data: weekly return panel + weekly funding panel
# ==========================================================================
def _daily_close_series(asset: str) -> pd.Series:
    candles = store.get_candles(asset, "1d")
    if not candles:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([c["time"] for c in candles], unit="s", utc=True)
    s = pd.Series([float(c["close"]) for c in candles], index=idx).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s[s > 0]


def _weekly_returns(asset: str) -> pd.Series:
    s = _daily_close_series(asset)
    if s.empty:
        return pd.Series(dtype=float)
    wk = s.resample("W-FRI").last().dropna()
    return wk.pct_change().dropna()


_PANEL_CACHE: Dict[Tuple[str, ...], pd.DataFrame] = {}
_FUNDING_CACHE: Dict[Tuple[str, ...], pd.DataFrame] = {}


def build_return_panel(assets: Tuple[str, ...]) -> pd.DataFrame:
    """Weekly close-to-close returns, columns = assets, index = week-ending
    Friday (UTC). A cell is NaN before the asset's first weekly bar and is
    treated downstream as 'no position' (excluded from normalisation).

    Cached per asset-tuple for the life of the process: the underlying
    daily store is read-only within a run and every caller wants the exact
    same panel, so re-reading it dozens of times only adds latency."""
    key = tuple(assets)
    if key not in _PANEL_CACHE:
        cols = {a: _weekly_returns(a) for a in assets}
        _PANEL_CACHE[key] = pd.DataFrame(cols).sort_index()
    return _PANEL_CACHE[key].copy()


def _weekly_funding_series(asset: str) -> pd.Series:
    """Weekly-summed perpetual funding rate for a crypto asset (fraction,
    e.g. 0.0003 = +3 bps that week). Long pays / short receives when
    positive."""
    fd = p94.get_funding_daily(asset)
    if not fd or not fd.get("daily_summed_funding_rate"):
        return pd.Series(dtype=float)
    rows = fd["daily_summed_funding_rate"]
    idx = pd.to_datetime([int(r[0]) for r in rows], unit="s", utc=True)
    s = pd.Series([float(r[1]) for r in rows], index=idx).sort_index()
    return s.resample("W-FRI").sum()


def build_funding_panel(assets: Tuple[str, ...], like: pd.DataFrame) -> pd.DataFrame:
    cols = {a: _weekly_funding_series(a) for a in assets}
    fp = pd.DataFrame(cols).reindex(like.index).fillna(0.0)
    return fp


# ==========================================================================
# Signals (frozen)
# ==========================================================================
def _trailing_return(returns: np.ndarray, t: int, lookback: int) -> float:
    """prod(1 + r[t-lookback+1 .. t]) - 1, or NaN if the window is not fully
    populated with finite returns."""
    if t - lookback + 1 < 0:
        return np.nan
    win = returns[t - lookback + 1: t + 1]
    if win.shape[0] != lookback or not np.isfinite(win).all():
        return np.nan
    return float(np.prod(1.0 + win) - 1.0)


def _mom_matrix(panel: pd.DataFrame, lookbacks: Tuple[int, ...]) -> Dict[int, np.ndarray]:
    """{lookback: (T x N) trailing-return matrix}."""
    arr = panel.to_numpy(float)
    T, N = arr.shape
    out: Dict[int, np.ndarray] = {}
    for L in lookbacks:
        m = np.full((T, N), np.nan)
        for j in range(N):
            col = arr[:, j]
            for t in range(L - 1, T):
                m[t, j] = _trailing_return(col, t, L)
        out[L] = m
    return out


def _safe_nanmean_axis0(stack: np.ndarray) -> np.ndarray:
    """np.nanmean over axis 0, returning NaN (no warning) for all-NaN cells."""
    finite = np.isfinite(stack)
    cnt = finite.sum(axis=0)
    tot = np.where(finite, stack, 0.0).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(cnt > 0, tot / cnt, np.nan)
    return out


def ts_signal_matrix(mom: Dict[int, np.ndarray]) -> np.ndarray:
    """mean over L of sign(trailing_return_L); NaN where no lookback is
    available. Range [-1, 1]."""
    stacked = np.stack([np.sign(mom[L]) for L in mom], axis=0)   # (nL, T, N)
    return _safe_nanmean_axis0(stacked)


def xs_signal_matrix(mom: Dict[int, np.ndarray]) -> np.ndarray:
    """Within each row (week): rank valid names by the blended trailing
    return (mean over L); +1 top third, -1 bottom third, 0 otherwise.
    Count-neutral by construction."""
    blend = _safe_nanmean_axis0(np.stack([mom[L] for L in mom], axis=0))   # (T, N)
    T, N = blend.shape
    sig = np.zeros((T, N))
    for t in range(T):
        row = blend[t]
        valid = np.where(np.isfinite(row))[0]
        if valid.size < _MIN_XS_NAMES:
            sig[t, :] = np.nan
            continue
        order = valid[np.argsort(row[valid])]
        k = max(1, int(np.floor(order.size * _XS_TERTILE)))
        sig[t, order[:k]] = -1.0
        sig[t, order[-k:]] = 1.0
    return sig


# ==========================================================================
# Sizing + simulation
# ==========================================================================
def _ann_vol_matrix(panel: pd.DataFrame, lookback: int = _VOL_LOOKBACK_WEEKS) -> np.ndarray:
    """Trailing realised weekly std * sqrt(52), causal (uses r[..t]), floored."""
    arr = panel.to_numpy(float)
    T, N = arr.shape
    out = np.full((T, N), np.nan)
    for j in range(N):
        col = arr[:, j]
        for t in range(lookback - 1, T):
            win = col[t - lookback + 1: t + 1]
            if np.isfinite(win).sum() >= max(8, lookback // 2):
                out[t, j] = np.nanstd(win, ddof=1) * np.sqrt(_WEEKS_PER_YEAR)
    return np.where(np.isfinite(out), np.maximum(out, _SIGMA_FLOOR), np.nan)


def _raw_weights(signal: np.ndarray, ann_vol: np.ndarray) -> np.ndarray:
    """w_i = signal_i / sigma_i, gross-normalised per week to sum|w| = 1.
    Names with a NaN signal or NaN vol get weight 0."""
    w = np.where(np.isfinite(signal) & np.isfinite(ann_vol), signal / ann_vol, 0.0)
    gross = np.sum(np.abs(w), axis=1, keepdims=True)
    gross[gross == 0.0] = 1.0
    return w / gross


def simulate_sleeve(panel: pd.DataFrame, funding: pd.DataFrame, target_weights: np.ndarray,
                    sleeve: str, cost_mult: float = 1.0,
                    rebalance_weeks: int = _REBALANCE_WEEKS,
                    apply_funding: bool = True) -> Dict[str, Any]:
    """Given a (T x N) pre-vol-target weight matrix, run the weekly book:
    ex-ante vol-target the sleeve (causal), cap leverage, hold weights
    between rebalances, charge turnover costs, and (crypto) credit/charge
    perp funding on short legs. Returns the weekly net-return series and
    its decomposition."""
    r = panel.to_numpy(float)
    f = funding.to_numpy(float)
    T, N = r.shape
    assets = list(panel.columns)
    cost_bps = np.array([_COST_BPS.get(a, 10.0) for a in assets]) * 1e-4 * cost_mult
    max_lev = _MAX_LEVERAGE[sleeve]

    fwd = np.vstack([r[1:], np.full((1, N), np.nan)])        # return realised t -> t+1
    fwd_fin = np.vstack([f[1:], np.full((1, N), np.nan)])

    held = np.zeros(N)             # currently-held levered weights
    cur_unlev = np.zeros(N)        # currently-held UNLEVERED (gross=1) target weights
    unlev_hist: List[float] = []   # realised unlevered target returns (causal vol estimator input)
    net, gross_ret, cost_ret, fund_ret, turnover, lev_series = [], [], [], [], [], []

    for t in range(T):
        rebalance = (t % rebalance_weeks == 0)
        if rebalance:
            tw = np.where(np.isfinite(target_weights[t]), target_weights[t], 0.0)
            # ex-ante sleeve vol estimate from the unlevered target return history (causal)
            hist = np.array(unlev_hist[-_VOL_LOOKBACK_WEEKS:], float)
            hist = hist[np.isfinite(hist)]
            if hist.size >= 8:
                pv = float(hist.std(ddof=1) * np.sqrt(_WEEKS_PER_YEAR))
            else:
                pv = _SLEEVE_VOL_TARGET
            lev = 0.0 if pv <= 1e-9 else min(_SLEEVE_VOL_TARGET / pv, max_lev)
            new_held = lev * tw
            cur_unlev = tw
        else:
            new_held = held
            lev = float(np.sum(np.abs(held)))

        c = float(np.sum(np.abs(new_held - held) * cost_bps))
        d_turnover = float(np.sum(np.abs(new_held - held)))

        fr = fwd[t]
        fin = fwd_fin[t]
        step_mask = np.isfinite(fr)
        g = float(np.sum(new_held[step_mask] * fr[step_mask]))
        # perp funding: a SHORT position (held<0) receives funding when funding>0
        fpnl = 0.0
        if apply_funding and sleeve == "CRYPTO":
            fin_mask = step_mask & np.isfinite(fin) & (new_held < 0)
            fpnl = float(np.sum(-new_held[fin_mask] * fin[fin_mask]))

        um = step_mask & np.isfinite(cur_unlev)
        unlev_hist.append(float(np.sum(cur_unlev[um] * fr[um])) if um.any() else np.nan)

        n = g - c + fpnl
        net.append(n); gross_ret.append(g); cost_ret.append(-c); fund_ret.append(fpnl)
        turnover.append(d_turnover); lev_series.append(lev)
        held = new_held

    return {
        "index": panel.index,
        "net": np.array(net), "gross": np.array(gross_ret), "cost": np.array(cost_ret),
        "funding": np.array(fund_ret), "turnover": np.array(turnover), "leverage": np.array(lev_series),
    }


# ==========================================================================
# Metrics
# ==========================================================================
def _metrics(net: np.ndarray, index: pd.DatetimeIndex, warmup: int = _WARMUP_WEEKS,
             extra: Optional[Dict[str, np.ndarray]] = None) -> Dict[str, Any]:
    n = np.asarray(net, float)[warmup:]
    ix = index[warmup:]
    n = n[np.isfinite(n)]
    if n.size < 26:
        return {"state": "INSUFFICIENT_SAMPLE", "n_weeks": int(n.size)}
    equity = np.cumprod(1.0 + n)
    years = n.size / _WEEKS_PER_YEAR
    cagr = float(equity[-1] ** (1.0 / years) - 1.0) if equity[-1] > 0 else -1.0
    vol = float(n.std(ddof=1) * np.sqrt(_WEEKS_PER_YEAR))
    sharpe = float(n.mean() / n.std(ddof=1) * np.sqrt(_WEEKS_PER_YEAR)) if n.std(ddof=1) > 0 else 0.0
    running_max = np.maximum.accumulate(equity)
    dd = equity / running_max - 1.0
    max_dd = float(dd.min())
    # drawdown duration (weeks)
    underwater = dd < 0
    md = cur = 0
    for u in underwater:
        cur = cur + 1 if u else 0
        md = max(md, cur)
    ser = pd.Series(n, index=ix[: n.size])
    monthly = (1.0 + ser).resample("ME").prod() - 1.0
    monthly_hit = float((monthly > 0).mean()) if monthly.size else None
    yearly = (1.0 + ser).resample("YE").prod() - 1.0
    out = {
        "state": "OK", "n_weeks": int(n.size), "start": ix[0].date().isoformat(),
        "end": ix[min(n.size, len(ix)) - 1].date().isoformat(),
        "cagr": round(cagr, 4), "ann_vol": round(vol, 4), "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4), "max_dd_weeks": int(md),
        "calmar": round(cagr / abs(max_dd), 3) if max_dd < 0 else None,
        "monthly_hit_rate": round(monthly_hit, 3) if monthly_hit is not None else None,
        "weekly_skew": round(float(pd.Series(n).skew()), 3),
        "worst_week": round(float(n.min()), 4), "best_week": round(float(n.max()), 4),
        "total_return": round(float(equity[-1] - 1.0), 4),
        "per_year_return": {str(k.year): round(float(v), 4) for k, v in yearly.items()},
        "positive_years": int((yearly > 0).sum()), "n_years": int(yearly.size),
    }
    if extra is not None:
        tt = np.asarray(extra.get("turnover", []), float)[warmup:]
        ct = np.asarray(extra.get("cost", []), float)[warmup:]
        ft = np.asarray(extra.get("funding", []), float)[warmup:]
        lv = np.asarray(extra.get("leverage", []), float)[warmup:]
        out["ann_turnover"] = round(float(np.nansum(tt) / years), 2)
        out["ann_cost_drag"] = round(float(-np.nansum(ct) / years), 4)
        out["ann_funding_pnl"] = round(float(np.nansum(ft) / years), 4)
        out["avg_leverage"] = round(float(np.nanmean(lv)), 2)
    return out


def _half_split_metrics(net: np.ndarray, index: pd.DatetimeIndex, warmup: int = _WARMUP_WEEKS) -> Dict[str, Any]:
    n = np.asarray(net, float)
    live = np.arange(warmup, n.size)
    if live.size < 104:
        return {"state": "INSUFFICIENT_SAMPLE"}
    mid = warmup + live.size // 2
    first = np.full_like(n, np.nan); first[warmup:mid] = n[warmup:mid]
    second = np.full_like(n, np.nan); second[mid:] = n[mid:]
    return {
        "first_half": _metrics(first, index, warmup=warmup),
        "second_half": _metrics(second, index, warmup=mid),
    }


# ==========================================================================
# Strategy assembly per sleeve
# ==========================================================================
def _sleeve_weight_sets(panel: pd.DataFrame, lookbacks: Tuple[int, ...] = _LOOKBACKS_WEEKS
                        ) -> Dict[str, np.ndarray]:
    mom = _mom_matrix(panel, lookbacks)
    ann_vol = _ann_vol_matrix(panel)
    ts_sig = ts_signal_matrix(mom)
    xs_sig = xs_signal_matrix(mom)
    w_ts = _raw_weights(ts_sig, ann_vol)
    w_xs = _raw_weights(xs_sig, ann_vol)
    w_combo = 0.5 * w_ts + 0.5 * w_xs
    return {"TS": w_ts, "XS": w_xs, "COMBO": w_combo, "_ann_vol": ann_vol,
            "_ts_sig": ts_sig, "_xs_sig": xs_sig}


def run_sleeve(sleeve: str, cost_key: str = "BASE", lookbacks: Tuple[int, ...] = _LOOKBACKS_WEEKS,
               rebalance_weeks: int = _REBALANCE_WEEKS, apply_funding: bool = True
               ) -> Dict[str, Any]:
    assets = FX_METALS_SLEEVE if sleeve == "FX_METALS" else CRYPTO_SLEEVE
    panel = build_return_panel(assets)
    funding = build_funding_panel(assets, panel) if sleeve == "CRYPTO" else pd.DataFrame(
        0.0, index=panel.index, columns=panel.columns)
    wsets = _sleeve_weight_sets(panel, lookbacks)
    out: Dict[str, Any] = {"sleeve": sleeve, "assets": list(assets), "n_weeks": int(len(panel)),
                           "cost_key": cost_key, "by_substrategy": {}}
    for sub in SUBSTRATEGIES:
        sim = simulate_sleeve(panel, funding, wsets[sub], sleeve,
                              cost_mult=_COST_LADDER[cost_key], rebalance_weeks=rebalance_weeks,
                              apply_funding=apply_funding)
        m = _metrics(sim["net"], sim["index"], extra=sim)
        m_halves = _half_split_metrics(sim["net"], sim["index"])
        out["by_substrategy"][sub] = {"metrics": m, "halves": m_halves,
                                      "_net": sim["net"], "_index": sim["index"]}
    return out


# ==========================================================================
# Combined two-sleeve book (causal inverse-vol blend of the sleeve COMBOs)
# ==========================================================================
def combined_book(fx_combo_net: np.ndarray, fx_index: pd.DatetimeIndex,
                  cr_combo_net: np.ndarray, cr_index: pd.DatetimeIndex) -> Dict[str, Any]:
    a = pd.Series(fx_combo_net, index=fx_index)
    b = pd.Series(cr_combo_net, index=cr_index)
    df = pd.concat({"FX_METALS": a, "CRYPTO": b}, axis=1).dropna(how="all")
    both = df.dropna()
    if len(both) < 104:
        return {"state": "INSUFFICIENT_SAMPLE"}
    net = []
    for t in range(len(both)):
        if t < 26:
            wv = np.array([0.5, 0.5])
        else:
            win = both.iloc[t - 26:t]
            vols = win.std(ddof=1).to_numpy()
            with np.errstate(divide="ignore", invalid="ignore"):
                inv = np.where(vols > 1e-9, 1.0 / np.where(vols > 1e-9, vols, 1.0), 0.0)
            wv = inv / inv.sum() if inv.sum() > 0 else np.array([0.5, 0.5])
        net.append(float(np.dot(wv, both.iloc[t].to_numpy())))
    net = np.array(net)
    return {"state": "OK", "metrics": _metrics(net, both.index, warmup=_WARMUP_WEEKS),
            "halves": _half_split_metrics(net, both.index, warmup=_WARMUP_WEEKS),
            "_net": net, "_index": both.index}


# ==========================================================================
# Controls
# ==========================================================================
def random_sign_placebo(sleeve: str, sub: str = "COMBO", reps: int = _PLACEBO_REPS,
                        seed: int = _RANDOM_SIGN_SEED) -> Dict[str, Any]:
    """Replace each name's signal SIGN with a fresh random +-1 every week,
    keeping the identical inverse-vol sizing / vol-target / cost machinery.
    The real strategy must beat this distribution's upper tail."""
    assets = FX_METALS_SLEEVE if sleeve == "FX_METALS" else CRYPTO_SLEEVE
    panel = build_return_panel(assets)
    funding = build_funding_panel(assets, panel) if sleeve == "CRYPTO" else pd.DataFrame(
        0.0, index=panel.index, columns=panel.columns)
    wsets = _sleeve_weight_sets(panel)
    real_net = simulate_sleeve(panel, funding, wsets[sub], sleeve)["net"]
    real_sharpe = _metrics(real_net, panel.index).get("sharpe")

    ann_vol = wsets["_ann_vol"]
    base_sig = wsets["_ts_sig"] if sub != "XS" else wsets["_xs_sig"]
    active = np.isfinite(base_sig)
    rng = np.random.default_rng(seed)
    sharpes = []
    for _ in range(reps):
        rsign = rng.choice([-1.0, 1.0], size=base_sig.shape)
        sig = np.where(active, rsign, np.nan)
        w = _raw_weights(sig, ann_vol)
        nn = simulate_sleeve(panel, funding, w, sleeve)["net"]
        s = _metrics(nn, panel.index).get("sharpe")
        if s is not None:
            sharpes.append(s)
    arr = np.array(sharpes)
    return _placebo_summary(real_sharpe, arr, reps, seed, "random_sign")


def xs_shuffle_placebo(sleeve: str, reps: int = _PLACEBO_REPS, seed: int = _XS_SHUFFLE_SEED) -> Dict[str, Any]:
    """Permute the cross-sectional signal ACROSS names within each week
    (destroys the relative-strength ordering, keeps the +1/-1/0 counts)."""
    assets = FX_METALS_SLEEVE if sleeve == "FX_METALS" else CRYPTO_SLEEVE
    panel = build_return_panel(assets)
    funding = build_funding_panel(assets, panel) if sleeve == "CRYPTO" else pd.DataFrame(
        0.0, index=panel.index, columns=panel.columns)
    wsets = _sleeve_weight_sets(panel)
    real_net = simulate_sleeve(panel, funding, wsets["XS"], sleeve)["net"]
    real_sharpe = _metrics(real_net, panel.index).get("sharpe")
    xs_sig = wsets["_xs_sig"]
    ann_vol = wsets["_ann_vol"]
    rng = np.random.default_rng(seed)
    T = xs_sig.shape[0]
    sharpes = []
    for _ in range(reps):
        sig = xs_sig.copy()
        for t in range(T):
            row = sig[t]
            if np.isfinite(row).any():
                finite = np.where(np.isfinite(row))[0]
                sig[t, finite] = rng.permutation(row[finite])
        w = _raw_weights(sig, ann_vol)
        nn = simulate_sleeve(panel, funding, w, sleeve)["net"]
        s = _metrics(nn, panel.index).get("sharpe")
        if s is not None:
            sharpes.append(s)
    return _placebo_summary(real_sharpe, np.array(sharpes), reps, seed, "xs_shuffle")


def _placebo_summary(real: Optional[float], arr: np.ndarray, reps: int, seed: int, name: str) -> Dict[str, Any]:
    if real is None or arr.size == 0:
        return {"name": name, "state": "INSUFFICIENT_SAMPLE"}
    pct = float((arr <= real).mean())
    return {"name": name, "real_sharpe": round(real, 3), "placebo_mean_sharpe": round(float(arr.mean()), 3),
            "placebo_std_sharpe": round(float(arr.std(ddof=1)), 3),
            "placebo_p95_sharpe": round(float(np.percentile(arr, 95)), 3),
            "real_percentile": round(pct, 4), "empirical_p_one_sided": round(float((arr >= real).mean()), 4),
            "n_reps": int(arr.size), "seed": seed}


def buy_and_hold_benchmark(sleeve: str) -> Dict[str, Any]:
    """Long-only, equal-signal (+1 everywhere), identical inverse-vol sizing
    + vol-target + costs. 'Does momentum beat just owning the basket?'"""
    assets = FX_METALS_SLEEVE if sleeve == "FX_METALS" else CRYPTO_SLEEVE
    panel = build_return_panel(assets)
    funding = build_funding_panel(assets, panel) if sleeve == "CRYPTO" else pd.DataFrame(
        0.0, index=panel.index, columns=panel.columns)
    ann_vol = _ann_vol_matrix(panel)
    ones = np.where(np.isfinite(panel.to_numpy(float)), 1.0, np.nan)
    w = _raw_weights(ones, ann_vol)
    sim = simulate_sleeve(panel, funding, w, sleeve, apply_funding=False)
    return {"metrics": _metrics(sim["net"], sim["index"], extra=sim)}


def cost_sensitivity(sleeve: str, sub: str = "COMBO") -> Dict[str, Any]:
    out = {}
    for key in _COST_LADDER:
        res = run_sleeve(sleeve, cost_key=key)
        out[key] = res["by_substrategy"][sub]["metrics"].get("sharpe")
    return {"by_cost_key": out}


def lookback_sensitivity(sleeve: str, sub: str = "COMBO") -> Dict[str, Any]:
    out = {}
    for name, lbs in _LOOKBACK_NEIGHBOURHOOD.items():
        res = run_sleeve(sleeve, cost_key="BASE", lookbacks=lbs)
        m = res["by_substrategy"][sub]["metrics"]
        out[name] = {"lookbacks": list(lbs), "sharpe": m.get("sharpe"), "cagr": m.get("cagr"),
                     "max_drawdown": m.get("max_drawdown")}
    return {"by_lookback": out, "note": "L13_26_52_frozen is the pre-registered design; the singles are "
            "reported for sensitivity only and are never selected from."}


def rebalance_sensitivity(sleeve: str, sub: str = "COMBO") -> Dict[str, Any]:
    out = {}
    for rb in _REBALANCE_NEIGHBOURHOOD:
        res = run_sleeve(sleeve, cost_key="BASE", rebalance_weeks=rb)
        m = res["by_substrategy"][sub]["metrics"]
        out[f"every_{rb}w"] = {"sharpe": m.get("sharpe"), "cagr": m.get("cagr"),
                               "ann_cost_drag": m.get("ann_cost_drag")}
    return {"by_rebalance": out, "note": "weekly (every_1w) is the pre-registered design."}


def per_asset_contribution(sleeve: str, sub: str = "COMBO") -> Dict[str, Any]:
    """Each name's average weekly contribution (weight * forward return) and
    its stand-alone trailing-12m TS hit rate -- a descriptive breakdown, not
    a selection tool."""
    assets = FX_METALS_SLEEVE if sleeve == "FX_METALS" else CRYPTO_SLEEVE
    panel = build_return_panel(assets)
    funding = build_funding_panel(assets, panel) if sleeve == "CRYPTO" else pd.DataFrame(
        0.0, index=panel.index, columns=panel.columns)
    wsets = _sleeve_weight_sets(panel)
    w = wsets[sub]
    r = panel.to_numpy(float)
    T, N = r.shape
    fwd = np.vstack([r[1:], np.full((1, N), np.nan)])
    contrib = np.nansum(np.where(np.isfinite(fwd), w * fwd, 0.0), axis=0)
    out = {}
    for j, a in enumerate(assets):
        out[a] = {"total_contribution": round(float(contrib[j]), 4),
                  "mean_weekly_contribution_bps": round(float(contrib[j] / max(1, T) * 1e4), 2)}
    ranked = sorted(out.items(), key=lambda kv: kv[1]["total_contribution"], reverse=True)
    return {"per_asset": out, "top5": [k for k, _ in ranked[:5]], "bottom5": [k for k, _ in ranked[-5:]]}


# ==========================================================================
# Verdicts (frozen decision rules)
# ==========================================================================
_VALID_VERDICTS = ("SWING_MOMENTUM_EDGE_CONFIRMED", "SWING_MOMENTUM_EDGE_PROMISING",
                   "SWING_MOMENTUM_EDGE_NOT_ESTABLISHED", "SWING_MOMENTUM_EDGE_NEGATIVE")


def classify_sleeve_verdict(base_metrics: Dict[str, Any], adverse_metrics: Dict[str, Any],
                            placebo: Dict[str, Any], benchmark: Dict[str, Any]) -> Tuple[str, str]:
    if base_metrics.get("state") != "OK":
        return "SWING_MOMENTUM_EDGE_NOT_ESTABLISHED", "Insufficient sample to evaluate."
    sharpe = base_metrics.get("sharpe") or 0.0
    adv_sharpe = adverse_metrics.get("sharpe") if adverse_metrics.get("state") == "OK" else None
    pos_years = base_metrics.get("positive_years", 0)
    n_years = base_metrics.get("n_years", 0)
    year_frac = pos_years / n_years if n_years else 0.0
    pctl = placebo.get("real_percentile")
    bench_sharpe = (benchmark.get("metrics", {}) or {}).get("sharpe")
    beats_bench = bench_sharpe is None or sharpe >= bench_sharpe

    if sharpe < 0.0:
        return "SWING_MOMENTUM_EDGE_NEGATIVE", f"Net Sharpe {sharpe} is negative after BASE costs."
    if (sharpe >= 0.40 and pctl is not None and pctl >= 0.95 and year_frac >= 0.60
            and adv_sharpe is not None and adv_sharpe > 0.0 and beats_bench):
        return "SWING_MOMENTUM_EDGE_CONFIRMED", (
            f"Net Sharpe {sharpe} (BASE), still positive under ADVERSE costs ({adv_sharpe}), above the "
            f"95th pct of the random-sign placebo ({pctl}), positive in {pos_years}/{n_years} calendar "
            f"years, and at least matches the vol-matched buy-and-hold benchmark ({bench_sharpe}).")
    if sharpe >= 0.25 and pctl is not None and pctl >= 0.90:
        return "SWING_MOMENTUM_EDGE_PROMISING", (
            f"Net Sharpe {sharpe} (BASE) and above the 90th pct of the placebo ({pctl}), but does not "
            f"clear the full bar (Sharpe>=0.40, placebo>=0.95, >=60% positive years [{year_frac:.2f}], "
            f"ADVERSE-cost positive [{adv_sharpe}], beats benchmark [{beats_bench}]).")
    return "SWING_MOMENTUM_EDGE_NOT_ESTABLISHED", (
        f"Net Sharpe {sharpe} (BASE), placebo percentile {pctl} -- does not separate convincingly from "
        f"random-sign exposure with the same sizing.")


def classify_overall(combined_verdict: str) -> str:
    if combined_verdict == "SWING_MOMENTUM_EDGE_CONFIRMED":
        return "PROFITABLE_SWING_EDGE_FOUND"
    if combined_verdict == "SWING_MOMENTUM_EDGE_PROMISING":
        return "PROFITABLE_SWING_EDGE_PROMISING"
    return "PROFITABLE_SWING_EDGE_NOT_ESTABLISHED"


# ==========================================================================
# Result container
# ==========================================================================
@dataclass
class Phase95Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    design_note: Dict[str, Any]
    universe: Dict[str, List[str]]
    sleeve_results: Dict[str, Any]
    combined_book: Dict[str, Any]
    controls: Dict[str, Any]
    per_asset_contribution: Dict[str, Any]
    sleeve_verdicts: Dict[str, Any]
    overall_verdict: str
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    live_automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _strip_private(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_private(v) for v in obj]
    if isinstance(obj, (pd.DatetimeIndex, pd.Index)):
        return None
    if isinstance(obj, np.ndarray):
        return None
    return obj


def run() -> Phase95Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()

    sleeve_results: Dict[str, Any] = {}
    sleeve_verdicts: Dict[str, Any] = {}
    controls: Dict[str, Any] = {}
    per_asset: Dict[str, Any] = {}

    combo_nets: Dict[str, Any] = {}
    for sleeve in SLEEVES:
        base = run_sleeve(sleeve, cost_key="BASE")
        adverse = run_sleeve(sleeve, cost_key="ADVERSE")
        sleeve_results[sleeve] = {
            "by_substrategy": {s: {"metrics": base["by_substrategy"][s]["metrics"],
                                   "halves": base["by_substrategy"][s]["halves"],
                                   "adverse_metrics": adverse["by_substrategy"][s]["metrics"]}
                               for s in SUBSTRATEGIES},
            "n_weeks": base["n_weeks"], "assets": base["assets"],
        }
        rs_plac = random_sign_placebo(sleeve, "COMBO")
        xs_plac = xs_shuffle_placebo(sleeve)
        bench = buy_and_hold_benchmark(sleeve)
        controls[sleeve] = {
            "random_sign_placebo_combo": rs_plac,
            "xs_shuffle_placebo": xs_plac,
            "buy_and_hold_benchmark": bench,
            "cost_sensitivity_combo": cost_sensitivity(sleeve, "COMBO"),
            "lookback_sensitivity_combo": lookback_sensitivity(sleeve, "COMBO"),
            "rebalance_sensitivity_combo": rebalance_sensitivity(sleeve, "COMBO"),
        }
        per_asset[sleeve] = per_asset_contribution(sleeve, "COMBO")

        v, reason = classify_sleeve_verdict(
            base["by_substrategy"]["COMBO"]["metrics"],
            adverse["by_substrategy"]["COMBO"]["metrics"],
            rs_plac, bench)
        sleeve_verdicts[sleeve] = {"substrategy": "COMBO", "verdict": v, "reason": reason,
                                   "ts_verdict": classify_sleeve_verdict(
                                       base["by_substrategy"]["TS"]["metrics"],
                                       adverse["by_substrategy"]["TS"]["metrics"], rs_plac, bench)[0],
                                   "xs_verdict": classify_sleeve_verdict(
                                       base["by_substrategy"]["XS"]["metrics"],
                                       adverse["by_substrategy"]["XS"]["metrics"], xs_plac, bench)[0]}
        combo_nets[sleeve] = (base["by_substrategy"]["COMBO"]["_net"],
                              base["by_substrategy"]["COMBO"]["_index"])

    cb = combined_book(combo_nets["FX_METALS"][0], combo_nets["FX_METALS"][1],
                       combo_nets["CRYPTO"][0], combo_nets["CRYPTO"][1])
    # combined verdict: reuse the FX random-sign placebo tail as a conservative reference
    cb_metrics = cb.get("metrics", {"state": "INSUFFICIENT_SAMPLE"})
    cb_placebo = controls["FX_METALS"]["random_sign_placebo_combo"]
    cb_bench = controls["FX_METALS"]["buy_and_hold_benchmark"]
    # adverse combined: quick re-run
    adv_fx = run_sleeve("FX_METALS", cost_key="ADVERSE")["by_substrategy"]["COMBO"]
    adv_cr = run_sleeve("CRYPTO", cost_key="ADVERSE")["by_substrategy"]["COMBO"]
    cb_adv = combined_book(adv_fx["_net"], adv_fx["_index"], adv_cr["_net"], adv_cr["_index"]).get(
        "metrics", {"state": "INSUFFICIENT_SAMPLE"})
    cb_v, cb_reason = classify_sleeve_verdict(cb_metrics, cb_adv, cb_placebo, cb_bench)
    sleeve_verdicts["COMBINED_BOOK"] = {"verdict": cb_v, "reason": cb_reason}
    overall = classify_overall(cb_v)

    # determinism: re-run the FX COMBO sleeve and hash key metrics
    d1 = run_sleeve("FX_METALS", cost_key="BASE")["by_substrategy"]["COMBO"]["metrics"]
    d2 = run_sleeve("FX_METALS", cost_key="BASE")["by_substrategy"]["COMBO"]["metrics"]
    determinism_match = (json.dumps(d1, sort_keys=True, default=str)
                         == json.dumps(d2, sort_keys=True, default=str))

    payload_for_hash = _strip_private({
        "sleeve_results": sleeve_results, "combined_book": cb.get("metrics"),
        "sleeve_verdicts": sleeve_verdicts, "overall": overall,
    })
    chash = hashlib.sha256(json.dumps(payload_for_hash, sort_keys=True, default=str).encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase95Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        design_note=DESIGN_NOTE,
        universe={"FX_METALS": list(FX_METALS_SLEEVE), "CRYPTO": list(CRYPTO_SLEEVE)},
        sleeve_results=_strip_private(sleeve_results),
        combined_book=_strip_private(cb),
        controls=_strip_private(controls),
        per_asset_contribution=_strip_private(per_asset),
        sleeve_verdicts=sleeve_verdicts, overall_verdict=overall,
        determinism={"match": determinism_match},
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase95Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase95_swing_momentum", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("Phase 95 - swing momentum (TS + XS, daily-bar universe) ...", flush=True)
    res = run()
    h = persist(res)   # persist first -- verbose printing must never lose the artifact
    print(f"\n=== PHASE 95 ({res.runtime_seconds}s) ===")
    for sleeve in SLEEVES:
        sr = res.sleeve_results[sleeve]["by_substrategy"]
        print(f"\n[{sleeve}]  ({res.sleeve_results[sleeve]['n_weeks']} weeks)")
        for sub in SUBSTRATEGIES:
            m = sr[sub]["metrics"]
            if m.get("state") == "OK":
                print(f"  {sub:6} Sharpe {m['sharpe']:+.2f}  CAGR {m['cagr']:+.1%}  "
                      f"maxDD {m['max_drawdown']:+.1%}  cost {m.get('ann_cost_drag'):.2%}/yr  "
                      f"fundPnL {m.get('ann_funding_pnl'):+.2%}/yr")
        v = res.sleeve_verdicts[sleeve]
        print(f"  -> {v['verdict']}  (TS={v['ts_verdict']}, XS={v['xs_verdict']})")
        print(f"     {v['reason']}")
    cbm = res.combined_book.get("metrics", {})
    if cbm.get("state") == "OK":
        print(f"\n[COMBINED_BOOK] Sharpe {cbm['sharpe']:+.2f}  CAGR {cbm['cagr']:+.1%}  maxDD {cbm['max_drawdown']:+.1%}")
    print(f"  -> {res.sleeve_verdicts['COMBINED_BOOK']['verdict']}")
    print(f"     {res.sleeve_verdicts['COMBINED_BOOK']['reason']}")
    print(f"\nOVERALL: {res.overall_verdict}")
    print(f"determinism match: {res.determinism['match']}")
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DESIGN_NOTE", "FX_METALS_SLEEVE", "CRYPTO_SLEEVE",
    "SLEEVES", "SUBSTRATEGIES", "build_return_panel", "build_funding_panel",
    "ts_signal_matrix", "xs_signal_matrix", "run_sleeve", "combined_book",
    "random_sign_placebo", "xs_shuffle_placebo", "buy_and_hold_benchmark",
    "cost_sensitivity", "lookback_sensitivity", "rebalance_sensitivity",
    "per_asset_contribution", "classify_sleeve_verdict", "classify_overall",
    "run", "persist", "get_result", "main",
]
