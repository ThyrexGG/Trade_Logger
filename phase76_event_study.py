# -*- coding: utf-8 -*-
"""
Phase 76 — Literature-Guided Market Behavior Discovery.

A research phase, NOT a strategy phase. The question (§1):

    What measurable market behaviors are present in TradeLogger's authoritative
    MT5 datasets and sufficiently persistent to justify further research?

Success = discovering and validating (or rejecting) market *phenomena*, not
finding a profitable backtest. Every hypothesis in ``HYPOTHESES`` is
pre-registered (§5) with an explicit link to published literature (§4). Each is
an **event study**: for each event bar, forward ATR-normalised returns over
standardised horizons, aggregated with a block bootstrap (§22) that respects the
serial dependence of overlapping events. Chronological 70/30 dev/OOS split
(§21). Tiered multiple-testing control (§23). A frozen discovery score (§30).

Evidence levels are kept distinct (§2): published evidence (A) != TradeLogger
replication (B) != economic significance (C) != OOS persistence (D) !=
robustness (E) != strategy candidate (F).

Memory-bounded (§6): instruments are processed one at a time, event studies emit
compact per-event records, and cross-year analysis groups those records rather
than re-running anything.

Read-only. No execution / broker / risk / forward-validation module imported.
The frozen Phase-74 holdout is never read (§8).
"""
from __future__ import annotations

import gc
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import dataset_manifest
import gold_strategy_baseline as gsb
import historical_data_store as store

SCHEMA_VERSION = "phase76.1"
ARTIFACT_KEY = "phase76_market_behavior_discovery"
RANDOM_SEED = 42
_BOOT_ITERS = 3000
_DEV_RATIO = 0.70
# Conservative round-trip cost proxy in ATR units (§24). Spot FX / gold retail
# spreads + slippage are typically a small fraction of a 14-bar ATR on 15m/1h.
_COST_ATR_PROXY = 0.05

PRIMARY_INSTRUMENTS = ("XAUUSD", "USDJPY", "EURUSD", "GBPJPY")
SECONDARY_INSTRUMENTS = ("GBPUSD", "AUDJPY")
ALL_INSTRUMENTS = PRIMARY_INSTRUMENTS + SECONDARY_INSTRUMENTS

# Forward horizons in BARS of the study timeframe. On 15m: 1/2/4/8 bars =
# 15/30/60/120 min (§9). Lower-resolution info is never fabricated from bars.
FWD_HORIZONS = (1, 2, 4, 8)
HORIZON_MAP_K = (1, 2, 4, 8, 16, 32)

# --------------------------------------------------------------------------
# §3 Literature registry. Bibliographic detail is from the assistant's training
# knowledge (no live retrieval was performed); DOIs given where known. Each
# entry carries an explicit transferability class:
#   DIRECTLY_RELEVANT     — same asset class / frequency as our test
#   INDIRECTLY_INFORMATIVE — related market or frequency; hypothesis, not proof
#   CONCEPTUAL_ONLY       — the mechanism only; effect size does not transfer
# --------------------------------------------------------------------------
LITERATURE = [
    {
        "id": "L-TSMOM", "title": "Time Series Momentum",
        "authors": "Moskowitz, T. J.; Ooi, Y. H.; Pedersen, L. H.",
        "year": 2012, "venue": "Journal of Financial Economics 104(2), 228-250",
        "doi": "10.1016/j.jfineco.2011.11.003",
        "asset_class": "futures/forwards (equity indices, currencies, commodities, bonds)",
        "instruments": "58 liquid futures/forwards", "period": "1965-2009",
        "frequency": "monthly", "phenomenon": "own-past-return continuation (trend)",
        "directional_hypothesis": "positive past 1-12m return predicts positive next-month return",
        "conditioning": "look-back length; partial reversal beyond ~12 months",
        "cost_treatment": "modest at monthly frequency; discussed",
        "limitations": "monthly; futures not spot; crowding since publication",
        "relevance": "we test the SIGN of the effect on MT5 spot FX + XAUUSD at 1h/1d — "
                     "horizons and instruments the paper never studied",
        "transferability": {"spot_fx": "INDIRECTLY_INFORMATIVE", "xauusd": "INDIRECTLY_INFORMATIVE",
                            "intraday_m15": "CONCEPTUAL_ONLY", "session_based": "CONCEPTUAL_ONLY"},
        "hypotheses": ["H1_TSMOM"],
    },
    {
        "id": "L-INTRADAY-MOM", "title": "Market Intraday Momentum",
        "authors": "Gao, L.; Han, Y.; Li, S. Z.; Zhou, G.",
        "year": 2018, "venue": "Journal of Financial Economics 129(2), 394-414",
        "doi": "10.1016/j.jfineco.2018.05.009",
        "asset_class": "equity index (SPY) + international index futures",
        "instruments": "SPY; 10+ international index futures", "period": "1993-2016 (SPY)",
        "frequency": "30-minute intraday",
        "phenomenon": "first-half-hour return predicts last-half-hour return same day",
        "directional_hypothesis": "positive predictive slope open-interval -> close-interval",
        "conditioning": "cash-session structure; higher on high-volatility / high-volume days",
        "cost_treatment": "ETF-level; small",
        "limitations": "equity index cash session; 24h spot FX has no single open",
        "relevance": "test whether a standardized recent move (>= 0.5 ATR over N bars) "
                     "predicts continuation on MT5 15m/1h",
        "transferability": {"spot_fx": "CONCEPTUAL_ONLY", "xauusd": "CONCEPTUAL_ONLY",
                            "intraday_m15": "INDIRECTLY_INFORMATIVE", "session_based": "INDIRECTLY_INFORMATIVE"},
        "hypotheses": ["H2_INTRADAY_MOM"],
    },
    {
        "id": "L-REVERSAL-J", "title": "Evidence of Predictable Behavior of Security Returns",
        "authors": "Jegadeesh, N.", "year": 1990,
        "venue": "Journal of Finance 45(3), 881-898",
        "doi": "10.1111/j.1540-6261.1990.tb05110.x",
        "asset_class": "US equities", "instruments": "NYSE/AMEX common stocks",
        "period": "1934-1987", "frequency": "monthly (and weekly follow-ups)",
        "phenomenon": "short-horizon return reversal (contrarian)",
        "directional_hypothesis": "prior-period losers outperform winners next period",
        "conditioning": "strongest at the shortest horizons; size-dependent",
        "cost_treatment": "raw; bid-ask bounce inflates the effect",
        "limitations": "equities, monthly/weekly; microstructure-driven; not spot FX intraday",
        "relevance": "test single-bar / few-bar reversal on 15m/1h, distinguishing "
                     "genuine reversal from continuation",
        "transferability": {"spot_fx": "CONCEPTUAL_ONLY", "xauusd": "CONCEPTUAL_ONLY",
                            "intraday_m15": "INDIRECTLY_INFORMATIVE", "session_based": "CONCEPTUAL_ONLY"},
        "hypotheses": ["H3_ST_REVERSAL"],
    },
    {
        "id": "L-REVERSAL-L", "title": "Fads, Martingales, and Market Efficiency",
        "authors": "Lehmann, B. N.", "year": 1990,
        "venue": "Quarterly Journal of Economics 105(1), 1-28",
        "doi": "10.2307/2937816",
        "asset_class": "US equities", "instruments": "NYSE/AMEX stocks",
        "period": "1962-1986", "frequency": "weekly",
        "phenomenon": "weekly return reversal",
        "directional_hypothesis": "zero-cost contrarian portfolio earns positive returns weekly",
        "conditioning": "concentrated in small / illiquid names",
        "cost_treatment": "raw; author notes transaction costs may absorb much of it",
        "limitations": "weekly equities; heavy microstructure component",
        "relevance": "corroborates the short-horizon reversal hypothesis; not spot FX",
        "transferability": {"spot_fx": "CONCEPTUAL_ONLY", "xauusd": "CONCEPTUAL_ONLY",
                            "intraday_m15": "CONCEPTUAL_ONLY", "session_based": "CONCEPTUAL_ONLY"},
        "hypotheses": ["H3_ST_REVERSAL"],
    },
    {
        "id": "L-GARCH", "title": "Generalized Autoregressive Conditional Heteroskedasticity",
        "authors": "Bollerslev, T.", "year": 1986,
        "venue": "Journal of Econometrics 31(3), 307-327",
        "doi": "10.1016/0304-4076(86)90063-1",
        "asset_class": "macro / financial time series", "instruments": "US inflation (orig.); "
        "since applied to nearly all financial series",
        "period": "n/a (methodological)", "frequency": "daily and lower",
        "phenomenon": "conditional heteroskedasticity — volatility clustering",
        "directional_hypothesis": "NONE — a variance property, not a return-sign property",
        "conditioning": "n/a", "cost_treatment": "n/a",
        "limitations": "says nothing about return direction; no direct trading implication",
        "relevance": "we measure |return| / squared-return autocorrelation and ATR "
                     "persistence directly — as a diagnostic, not a strategy",
        "transferability": {"spot_fx": "DIRECTLY_RELEVANT", "xauusd": "DIRECTLY_RELEVANT",
                            "intraday_m15": "DIRECTLY_RELEVANT", "session_based": "INDIRECTLY_INFORMATIVE"},
        "hypotheses": ["H5_VOL_CLUSTERING"],
    },
    {
        "id": "L-LONGMEM", "title": "A Long Memory Property of Stock Market Returns and a New Model",
        "authors": "Ding, Z.; Granger, C. W. J.; Engle, R. F.", "year": 1993,
        "venue": "Journal of Empirical Finance 1(1), 83-106",
        "doi": "10.1016/0927-5398(93)90006-D",
        "asset_class": "equity index", "instruments": "S&P 500", "period": "1928-1991",
        "frequency": "daily",
        "phenomenon": "slow-decaying autocorrelation of |return|^d (long memory in volatility)",
        "directional_hypothesis": "NONE", "conditioning": "power d ~ 1 maximises the ACF",
        "cost_treatment": "n/a", "limitations": "variance property; equity index; daily",
        "relevance": "the |return| ACF shape we measure on MT5 bars should look similar "
                     "if the property holds in our data",
        "transferability": {"spot_fx": "DIRECTLY_RELEVANT", "xauusd": "DIRECTLY_RELEVANT",
                            "intraday_m15": "DIRECTLY_RELEVANT", "session_based": "INDIRECTLY_INFORMATIVE"},
        "hypotheses": ["H5_VOL_CLUSTERING"],
    },
    {
        "id": "L-INTRADAY-VOL", "title": "Intraday periodicity and volatility persistence in "
        "financial markets",
        "authors": "Andersen, T. G.; Bollerslev, T.", "year": 1997,
        "venue": "Journal of Empirical Finance 4(2-3), 115-158",
        "doi": "10.1016/S0927-5398(97)00004-2",
        "asset_class": "FX + equity index", "instruments": "DEM/USD, S&P 500",
        "period": "1986-1996 (FX)", "frequency": "5-minute",
        "phenomenon": "strong deterministic intraday volatility seasonality tied to "
                      "Tokyo/London/NY market hours",
        "directional_hypothesis": "NONE for direction; volatility rises around session opens "
                                  "and the London/NY overlap",
        "conditioning": "time-of-day; day-of-week",
        "cost_treatment": "spreads widen outside the overlap (noted in the spreads literature)",
        "limitations": "a volatility-seasonality result, not a directional edge",
        "relevance": "we test whether measurable DIRECTIONAL conditional behavior (not just "
                     "volatility) exists around the London / NY opens on MT5 15m",
        "transferability": {"spot_fx": "DIRECTLY_RELEVANT", "xauusd": "INDIRECTLY_INFORMATIVE",
                            "intraday_m15": "DIRECTLY_RELEVANT", "session_based": "DIRECTLY_RELEVANT"},
        "hypotheses": ["H10_SESSION_LONDON", "H10_SESSION_NY"],
    },
    {
        "id": "L-DIAG-VOLCYCLE", "title": "(diagnostic) volatility compression/expansion cycle",
        "authors": "— (no single peer-reviewed source; NR-bar folklore)", "year": None,
        "venue": "—", "doi": None, "asset_class": "—", "instruments": "—",
        "period": "—", "frequency": "—",
        "phenomenon": "compressed ranges claimed to precede expansion; direction unspecified",
        "directional_hypothesis": "NONE (magnitude only); NR7 already FAILED as a filter in Phase 75",
        "conditioning": "ATR / true-range percentile state", "cost_treatment": "n/a",
        "limitations": "no rigorous peer-reviewed effect size; treated as EXPLORATORY diagnostic",
        "relevance": "measure the empirical forward |return| distribution after ATR-percentile "
                     "compression / expansion — as a diagnostic, not a strategy",
        "transferability": {"spot_fx": "CONCEPTUAL_ONLY", "xauusd": "CONCEPTUAL_ONLY",
                            "intraday_m15": "CONCEPTUAL_ONLY", "session_based": "CONCEPTUAL_ONLY"},
        "hypotheses": ["H7_VOL_COMPRESSION", "H6_VOL_EXPANSION", "H8_RANGE_EXPANSION_1_5",
                       "H8_RANGE_EXPANSION_2_0", "H11_PREV_DAY_HIGH"],
    },
]


# --------------------------------------------------------------------------
# §35 data integrity
# --------------------------------------------------------------------------
def data_integrity(instrument: str, timeframe: str) -> Dict[str, Any]:
    rows = store.get_candles(instrument, timeframe)
    cov = store.get_coverage(instrument, timeframe)
    ga = store.analyze_gaps(instrument, timeframe)
    srcs = store.series_sources(instrument, timeframe)
    if not rows:
        return {"state": "NO_DATA", "sources": srcs}
    t = np.array([r["time"] for r in rows])
    o = np.array([r["open"] for r in rows], float)
    h = np.array([r["high"] for r in rows], float)
    lo = np.array([r["low"] for r in rows], float)
    c = np.array([r["close"] for r in rows], float)
    return {
        "state": "OK",
        "sources": srcs,
        "single_provider": len(srcs) == 1,
        "provider": srcs[0] if srcs else None,
        "bars": len(rows),
        "first_utc": datetime.fromtimestamp(int(t.min()), timezone.utc).isoformat(),
        "last_utc": datetime.fromtimestamp(int(t.max()), timezone.utc).isoformat(),
        "timestamps_strictly_ordered": bool(np.all(np.diff(t) > 0)),
        "duplicate_timestamps": int(len(t) - len(np.unique(t))),
        "ohlc_violations": int(np.sum((h < lo) | (h < np.maximum(o, c)) | (lo > np.minimum(o, c)))),
        "nonpositive_prices": int(np.sum((o <= 0) | (h <= 0) | (lo <= 0) | (c <= 0))),
        "anomalous_gaps": ga.get("anomalous_gaps", 0),
        "weekend_gaps": ga.get("weekend_gaps", 0),
        "suspect_bars": int(cov.suspect),
        "non_mt5_rows": int(sum(1 for r in rows if r.get("source") != "mt5")),
    }


# --------------------------------------------------------------------------
# Bar loading + causal features (all computed from information at bar t)
# --------------------------------------------------------------------------
def load_bars(instrument: str, timeframe: str) -> pd.DataFrame:
    rows = store.get_candles(instrument, timeframe)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "source" in df.columns:
        df = df[df["source"] == "mt5"]
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    n = len(df)
    ts = pd.to_datetime(df["time"].to_numpy(), unit="s", utc=True)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    v = np.clip(df["volume"].to_numpy(float), 0.0, None)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    ret = np.concatenate([[0.0], np.diff(np.log(c))])
    tr = np.maximum.reduce([h - lo, np.abs(h - prev_c), np.abs(lo - prev_c)])
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    atr_ret = np.where(c > 0, atr / c, np.nan)
    # a STABLE denominator for magnitude tests: the trailing 200-bar mean of
    # atr_ret. Unlike the spot atr_ret it does not collapse at compression events,
    # so normalising by it does not bias a "forward |return|" study.
    atr_ret_stable = pd.Series(atr_ret).rolling(200, min_periods=50).mean().to_numpy()
    # trailing 200-bar ATR percentile rank (causal), vectorised
    w = 200
    atr_rank = np.full(n, np.nan)
    if n >= w:
        sw = np.lib.stride_tricks.sliding_window_view(atr, w)
        atr_rank[w - 1:] = (sw <= sw[:, -1:]).mean(axis=1)
    # deterministic regime — 20-bar efficiency ratio (Kaufman)
    move = np.abs(c - np.concatenate([np.full(20, c[0]), c[:-20]]))
    path = pd.Series(np.abs(ret)).rolling(20, min_periods=20).sum().to_numpy() + 1e-12
    eff = move / path
    regime = np.where(eff > 0.35, "TRENDING", np.where(eff < 0.15, "RANGING", "MIXED"))
    hr = ts.hour.to_numpy()
    session = np.select(
        [(hr >= 0) & (hr < 7), (hr >= 7) & (hr < 12), (hr >= 12) & (hr < 16), (hr >= 16) & (hr < 21)],
        ["TOKYO", "LONDON", "LONDON_NY_OVERLAP", "NEW_YORK"], default="LATE_US")
    year = ts.year.to_numpy()
    dates = ts.date
    out = pd.DataFrame({
        "t": df["time"].to_numpy(), "open": o, "high": h, "low": lo, "close": c, "vol": v,
        "hour": hr, "minute": ts.minute.to_numpy(), "year": year, "date": dates,
        "ret": ret, "tr": tr, "atr": atr, "atr_ret": atr_ret, "atr_ret_stable": atr_ret_stable, "atr_rank": atr_rank,
        "tr_atr": tr / np.where(atr > 0, atr, np.nan), "eff": eff, "regime": regime,
        "session": session,
    })
    # previous-day levels (causal: shift the daily aggregate by one calendar day)
    daily = out.groupby("date").agg(dh=("high", "max"), dl=("low", "min"), dc=("close", "last"))
    daily["pdh"] = daily["dh"].shift(1); daily["pdl"] = daily["dl"].shift(1)
    daily["pdc"] = daily["dc"].shift(1)
    out = out.merge(daily[["pdh", "pdl", "pdc"]], on="date", how="left")
    return out


# --------------------------------------------------------------------------
# §22 statistics — block bootstrap for overlapping / dependent events
# --------------------------------------------------------------------------
def block_bootstrap(values: np.ndarray, block: int, iters: int = _BOOT_ITERS,
                    seed: int = RANDOM_SEED) -> Dict[str, Any]:
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    n = len(v)
    if n < 20:
        return {"n": int(n), "mean": (round(float(np.mean(v)), 6) if n else None),
                "ci_lower": None, "ci_upper": None, "se": None, "effect_z": None,
                "verdict": "INSUFFICIENT_SAMPLE"}
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    # memory guard: keep iters * n bounded (~24M cells). For very large samples
    # (e.g. the full-series horizon map) fewer resamples still give a stable CI.
    eff_iters = int(min(iters, max(500, 24_000_000 // n)))
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(eff_iters, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(eff_iters, -1)[:, :n]
    bm = v[idx].mean(axis=1)
    lo, hi = np.percentile(bm, [2.5, 97.5])
    se = float(np.std(bm, ddof=1))
    mean = float(np.mean(v))
    return {
        "n": int(n), "mean": round(mean, 6), "median": round(float(np.median(v)), 6),
        "std": round(float(np.std(v, ddof=1)), 6),
        "prob_positive": round(float(np.mean(v > 0)), 4),
        "ci_lower": round(float(lo), 6), "ci_upper": round(float(hi), 6),
        "se": round(se, 6), "effect_z": round(mean / se, 3) if se > 0 else 0.0,
        "block": int(block),
        "verdict": "POSITIVE" if lo > 0 else "NEGATIVE" if hi < 0 else "ZERO_CROSSING",
    }


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _benjamini_hochberg(pvals: List[float], q: float) -> List[bool]:
    m = len(pvals)
    if m == 0:
        return []
    order = np.argsort(pvals)
    sp = np.asarray(pvals)[order]
    thr = q * (np.arange(1, m + 1) / m)
    passed = np.where(sp <= thr)[0]
    k = int(passed.max()) + 1 if passed.size else 0
    out = np.zeros(m, bool)
    if k:
        out[order[:k]] = True
    return list(out)


# --------------------------------------------------------------------------
# Event builders. Each returns (event_bar_index, event_direction, event_magnitude
# in ATR units). Every condition uses info available at bar i only (§18).
# --------------------------------------------------------------------------
def _b_tsmom(df, lookback: int):
    c = df["close"].to_numpy(float); n = len(c)
    i = np.arange(lookback + 14, n)
    prior = np.log(c[i] / c[i - lookback])
    mag = np.abs(prior) / np.where(df["atr_ret"].to_numpy()[i] > 0, df["atr_ret"].to_numpy()[i], np.nan)
    return i, np.sign(prior), mag


def _b_intraday_mom(df, lookback: int = 4, thr_atr: float = 0.5):
    c = df["close"].to_numpy(float); ar = df["atr_ret"].to_numpy(float); n = len(c)
    i = np.arange(lookback + 14, n)
    pr = np.log(c[i] / c[i - lookback])
    scale = ar[i] * math.sqrt(lookback)
    mag = np.where(scale > 0, np.abs(pr) / scale, np.nan)
    keep = mag >= thr_atr
    return i[keep], np.sign(pr[keep]), mag[keep]


def _b_st_reversal(df, pct: float = 0.95):
    r = df["ret"].to_numpy(float); ar = df["atr_ret"].to_numpy(float)
    absr = np.abs(r)
    thr = pd.Series(absr).rolling(500, min_periods=100).quantile(pct).to_numpy()
    n = len(r)
    i = np.arange(100, n)
    keep = np.isfinite(thr[i]) & (absr[i] >= thr[i])
    ii = i[keep]
    mag = np.where(ar[ii] > 0, absr[ii] / ar[ii], np.nan)
    return ii, np.sign(r[ii]), mag


def _b_range_expansion(df, mult: float):
    ta = df["tr_atr"].to_numpy(float); r = df["ret"].to_numpy(float); n = len(ta)
    i = np.arange(20, n)
    keep = np.isfinite(ta[i]) & (ta[i] >= mult)
    ii = i[keep]
    return ii, np.sign(r[ii]), ta[ii]


def _b_vol_compression(df, rank_thr: float = 0.10):
    rk = df["atr_rank"].to_numpy(float); n = len(rk)
    i = np.arange(50, n)
    keep = np.isfinite(rk[i]) & (rk[i] <= rank_thr)
    ii = i[keep]
    return ii, np.zeros(len(ii)), rk[ii]


def _b_vol_expansion(df):
    rk = df["atr_rank"].to_numpy(float); n = len(rk)
    i = np.arange(51, n)
    keep = np.isfinite(rk[i - 1]) & np.isfinite(rk[i]) & (rk[i - 1] < 0.20) & (rk[i] > 0.60)
    ii = i[keep]
    return ii, np.zeros(len(ii)), rk[ii]


def _b_session_open(df, hour: int):
    h = df["hour"].to_numpy(); m = df["minute"].to_numpy(); n = len(h)
    keep = (h == hour) & (m < 30)
    ii = np.where(keep)[0]
    ii = ii[(ii > 20) & (ii < n - 1)]
    return ii, np.zeros(len(ii)), np.ones(len(ii))


def _b_pdh_cross(df):
    c = df["close"].to_numpy(float); pdh = df["pdh"].to_numpy(float)
    atr = df["atr"].to_numpy(float); dt = df["date"].to_numpy(); n = len(c)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    cond = (np.isfinite(pdh) & np.isfinite(atr) & (atr > 0)
            & (prev_c <= pdh) & (c > pdh + 0.1 * atr))
    out, seen = [], set()
    for i in np.where(cond)[0]:
        if i < 20 or i >= n - 1 or dt[i] in seen:
            continue
        out.append(i); seen.add(dt[i])
    ii = np.array(out, int)
    mag = np.where(atr[ii] > 0, (c[ii] - pdh[ii]) / atr[ii], np.nan) if len(ii) else np.array([])
    return ii, np.ones(len(ii)), mag


@dataclass
class Hypothesis:
    hid: str
    phenomenon: str
    literature_ids: Tuple[str, ...]
    null_hypothesis: str
    alternative_hypothesis: str
    timeframes: Tuple[str, ...]
    builder: Callable
    signed: bool
    tier: int
    economic_interpretation: str


HYPOTHESES: List[Hypothesis] = [
    Hypothesis(
        "H1_TSMOM", "time-series momentum", ("L-TSMOM",),
        "the sign of the trailing-24-bar return carries no information about the forward return",
        "positive (negative) trailing-24-bar return predicts a positive (negative) forward return",
        ("1h", "1d"), lambda d: _b_tsmom(d, 24), True, 1,
        "a persistent own-return trend on our instruments/horizons"),
    Hypothesis(
        "H2_INTRADAY_MOM", "intraday momentum", ("L-INTRADAY-MOM",),
        "a standardized recent move (>= 0.5 ATR over 4 bars) does not predict the forward direction",
        "the forward return continues in the direction of the recent standardized move",
        ("15m", "1h"), _b_intraday_mom, True, 1,
        "short-horizon trend continuation after an impulse"),
    Hypothesis(
        "H3_ST_REVERSAL", "short-horizon reversal", ("L-REVERSAL-J", "L-REVERSAL-L"),
        "a single-bar |return| in the top 5% does not predict the sign of the next return",
        "the next return opposes the extreme bar (tested as continuation; NEGATIVE effect_z = reversal)",
        ("15m", "1h"), _b_st_reversal, True, 1,
        "mean reversion / overreaction correction after an extreme bar"),
    Hypothesis(
        "H8_RANGE_EXPANSION_1_5", "range expansion", ("L-DIAG-VOLCYCLE",),
        "a bar with true range >= 1.5 ATR does not predict the forward direction",
        "the forward return continues in the big bar's direction",
        ("15m", "1h"), lambda d: _b_range_expansion(d, 1.5), True, 2,
        "does a large candle indicate directional information or just noise?"),
    Hypothesis(
        "H8_RANGE_EXPANSION_2_0", "range expansion", ("L-DIAG-VOLCYCLE",),
        "a bar with true range >= 2.0 ATR does not predict the forward direction",
        "the forward return continues in the big bar's direction",
        ("15m", "1h"), lambda d: _b_range_expansion(d, 2.0), True, 2,
        "as above, at a more extreme threshold"),
    Hypothesis(
        "H7_VOL_COMPRESSION", "volatility compression", ("L-DIAG-VOLCYCLE", "L-GARCH"),
        "forward |return| after ATR percentile rank <= 0.10 equals the unconditional |return|",
        "forward |return| is elevated after compression (magnitude only, direction-agnostic)",
        ("15m", "1h"), _b_vol_compression, False, 2,
        "does compression precede expansion? (a variance question, not a direction question)"),
    Hypothesis(
        "H6_VOL_EXPANSION", "volatility expansion / clustering", ("L-DIAG-VOLCYCLE", "L-GARCH", "L-LONGMEM"),
        "forward |return| after an ATR rank transition <0.20 -> >0.60 equals the unconditional |return|",
        "forward |return| is elevated and persists after a compression->expansion transition",
        ("15m", "1h"), _b_vol_expansion, False, 2,
        "volatility persistence measured as a forward-|return| event study"),
    Hypothesis(
        "H10_SESSION_LONDON", "session transition", ("L-INTRADAY-VOL",),
        "the 15m bar at the London open (07:00-07:30 UTC) has the unconditional forward |return|",
        "forward |return| / range is elevated around the London open",
        ("15m",), lambda d: _b_session_open(d, 7), False, 1,
        "does a named session boundary create measurable conditional behavior?"),
    Hypothesis(
        "H10_SESSION_NY", "session transition", ("L-INTRADAY-VOL",),
        "the 15m bar at the New York open (12:00-12:30 UTC) has the unconditional forward |return|",
        "forward |return| / range is elevated around the New York open",
        ("15m",), lambda d: _b_session_open(d, 12), False, 1,
        "as above, for the NY open"),
    Hypothesis(
        "H11_PREV_DAY_HIGH", "previous-day level", ("L-DIAG-VOLCYCLE",),
        "the first bar to close >= 0.1 ATR above the previous-day high does not predict the forward direction",
        "continuation follows the break (a rejection shows as NEGATIVE effect_z)",
        ("15m",), _b_pdh_cross, True, 2,
        "purely statistical test of previous-day-high interaction — no liquidity interpretation"),
]


# --------------------------------------------------------------------------
# Event study -> compact per-event records (§6.A)
# --------------------------------------------------------------------------
def study_events(df: pd.DataFrame, i: np.ndarray, direction: np.ndarray, magnitude: np.ndarray,
                 signed: bool, horizons=FWD_HORIZONS, keep_rows: bool = True) -> Dict[str, Any]:
    """Compact: per horizon, an array of ATR-normalised forward returns (signed by
    the event direction when ``signed``). Also returns per-event (year, session,
    regime, h-return) rows for the headline horizon so cross-year / regime work
    needs no re-run."""
    c = df["close"].to_numpy(float); ar = df["atr_ret"].to_numpy(float)
    yr = df["year"].to_numpy(); sess = df["session"].to_numpy(); reg = df["regime"].to_numpy()
    n = len(c)
    i = np.asarray(i, int)
    ok = (i >= 0) & (i < n) & np.isfinite(ar[np.clip(i, 0, n - 1)]) & (ar[np.clip(i, 0, n - 1)] > 0)
    i = i[ok]
    d = (np.asarray(direction, float)[ok] if signed and len(direction) == len(ok) else np.ones(len(i)))
    d = np.where(d == 0, 1.0, d)
    mag = np.asarray(magnitude, float)[ok] if len(magnitude) == len(ok) else np.full(len(i), np.nan)
    res: Dict[str, Any] = {"n_events": int(len(i)), "state": "OK" if len(i) >= 20 else "INSUFFICIENT_SAMPLE",
                           "horizons": {}, "event_rows": []}
    if len(i) < 20:
        return res
    ars = df["atr_ret_stable"].to_numpy(float)      # STABLE denominator for magnitude tests
    lr = np.diff(np.log(c))
    for h in horizons:
        j = i + h
        m = j < n
        fr = np.full(len(i), np.nan)
        if signed:
            raw = np.log(c[j[m]] / c[i[m]]) / ar[i[m]]     # spot-ATR-normalised direction
            fr[m] = raw * d[m]
        else:
            # magnitude / excess: forward |return| normalised by a STABLE trailing
            # ATR (not the spot ATR, which collapses at compression events), minus
            # the unconditional |return| over the same horizon on the same scale.
            hsum = pd.Series(lr).rolling(h).sum().to_numpy()[h - 1:]
            denom = np.nanmean(ars) if np.isfinite(np.nanmean(ars)) else 1.0
            base = float(np.mean(np.abs(hsum))) / denom
            gd = np.where(np.isfinite(ars[i[m]]) & (ars[i[m]] > 0), ars[i[m]], np.nan)
            fr[m] = np.abs(np.log(c[j[m]] / c[i[m]])) / gd - base
        v = fr[np.isfinite(fr)]
        bs = block_bootstrap(v, block=h)
        # cost adjustment (§24): a directional effect must clear the round-trip
        # cost in absolute terms. |effect| shrinks toward zero; the sign is kept
        # only if it survives.
        mn = bs.get("mean")
        if mn is None:
            bs["cost_adj_mean"] = None
        else:
            shrunk = max(0.0, abs(mn) - _COST_ATR_PROXY)
            bs["cost_adj_mean"] = round(math.copysign(shrunk, mn) if shrunk > 0 else 0.0, 6)
        bs["test_kind"] = "signed_continuation" if signed else "abs_return_excess"
        res["horizons"][f"h{h}"] = bs
    # per-event rows at the headline horizon
    hh = _headline_h(df.attrs.get("tf", "15m"))
    hj = i + hh
    if keep_rows:
        hm = hj < n
        hr = np.full(len(i), np.nan)
        if signed:
            hr[hm] = np.log(c[hj[hm]] / c[i[hm]]) / ar[i[hm]] * d[hm]
        else:
            ars2 = df["atr_ret_stable"].to_numpy(float)
            lr2 = np.diff(np.log(c))
            denom2 = np.nanmean(ars2) if np.isfinite(np.nanmean(ars2)) else 1.0
            base2 = float(np.mean(np.abs(
                pd.Series(lr2).rolling(hh).sum().to_numpy()[hh - 1:]))) / denom2
            gd2 = np.where(np.isfinite(ars2[i[hm]]) & (ars2[i[hm]] > 0), ars2[i[hm]], np.nan)
            hr[hm] = np.abs(np.log(c[hj[hm]] / c[i[hm]])) / gd2 - base2
        res["event_rows"] = [
            {"year": int(yr[k]), "session": str(sess[k]), "regime": str(reg[k]),
             "mag_atr": (round(float(mag[n2]), 4) if np.isfinite(mag[n2]) else None),
             "fwd_r": round(float(hr[n2]), 6)}
            for n2, k in enumerate(i) if np.isfinite(hr[n2])]
    return res


_HEADLINE = {"15m": 4, "1h": 4, "1d": 2, "4h": 4}


def _headline_h(tf: str) -> int:
    return _HEADLINE.get(tf, 4)


# --------------------------------------------------------------------------
# Diagnostics: volatility clustering (H5) + momentum/reversal horizon map (H4)
# --------------------------------------------------------------------------
def vol_clustering(df: pd.DataFrame) -> Dict[str, Any]:
    r = df["ret"].to_numpy(float); r = r[np.isfinite(r)]
    if len(r) < 500:
        return {"state": "INSUFFICIENT_SAMPLE"}

    def acf(x, lags):
        x = x - x.mean(); d0 = np.dot(x, x)
        return {f"lag{k}": round(float(np.dot(x[:-k], x[k:]) / d0), 4) for k in lags}

    lags = [1, 2, 3, 5, 10, 20, 40]
    atr = df["atr"].to_numpy(float); atr = atr[np.isfinite(atr)]
    ar1 = float(np.corrcoef(atr[:-1], atr[1:])[0, 1]) if len(atr) > 100 else None
    reg = df["regime"].to_numpy()
    persist = float(np.mean(reg[1:] == reg[:-1])) if len(reg) > 10 else None
    # regime run length
    runs = []
    if len(reg) > 10:
        cur = 1
        for a, b in zip(reg[:-1], reg[1:]):
            if a == b:
                cur += 1
            else:
                runs.append(cur); cur = 1
        runs.append(cur)
    return {
        "state": "OK",
        "abs_return_acf": acf(np.abs(r), lags),
        "squared_return_acf": acf(r ** 2, lags),
        "raw_return_acf": acf(r, [1, 2, 3]),
        "atr_ar1": round(ar1, 4) if ar1 is not None else None,
        "regime_same_bar_persistence": round(persist, 4) if persist is not None else None,
        "regime_median_run_bars": int(np.median(runs)) if runs else None,
        "clustering_present": bool(ar1 and ar1 > 0.5 and acf(np.abs(r), [1])["lag1"] > 0.05),
    }


def horizon_map(df: pd.DataFrame) -> Dict[str, Any]:
    c = df["close"].to_numpy(float); n = len(c)
    if n < 2000:
        return {"state": "INSUFFICIENT_SAMPLE"}
    by_k = {}
    for k in HORIZON_MAP_K:
        if 2 * k >= n:
            continue
        i = np.arange(k, n - k)
        prior = np.log(c[i] / c[i - k]); fwd = np.log(c[i + k] / c[i])
        mm = np.isfinite(prior) & np.isfinite(fwd)
        if mm.sum() < 100:
            continue
        rho = float(np.corrcoef(prior[mm], fwd[mm])[0, 1])
        bs = block_bootstrap(fwd[mm] * np.sign(prior[mm]), block=k)
        by_k[f"k{k}"] = {"corr": round(rho, 4), "cont_effect_z": bs.get("effect_z"),
                         "cont_ci": [bs.get("ci_lower"), bs.get("ci_upper")],
                         "n": int(mm.sum()),
                         "behavior": "MOMENTUM" if rho > 0.02 else "REVERSAL" if rho < -0.02 else "NONE"}
    behs = [v["behavior"] for v in by_k.values() if v["behavior"] != "NONE"]
    return {"state": "OK", "by_k": by_k, "sign_flips": len(set(behs)) > 1,
            "shortest_behavior": next(iter(by_k.values()), {}).get("behavior") if by_k else None}


# --------------------------------------------------------------------------
# §30 discovery score — FROZEN weights, not tuned after seeing rankings
# --------------------------------------------------------------------------
DISCOVERY_WEIGHTS = {
    "effect_z": 0.28, "ci_excl_zero": 0.14, "oos_consistent": 0.22,
    "cross_year": 0.14, "cross_asset": 0.14, "cost_survival": 0.08,
}


def _keeps_sign(a, b) -> bool:
    return a is not None and b is not None and a != 0 and b != 0 and (a > 0) == (b > 0)


def discovery_score(dev, oos, cross_year_frac, cross_asset_frac, cost_adj) -> Dict[str, Any]:
    z = abs(dev.get("effect_z") or 0.0)
    dm, om = dev.get("mean"), oos.get("mean")
    oos_c = 0.0
    if dm and om and (dm > 0) == (om > 0):
        oos_c = 1.0 if abs(om) >= 0.4 * abs(dm) else 0.5
    comp = {
        "effect_z": round(min(z, 5.0) / 5.0, 4),
        "ci_excl_zero": 1.0 if dev.get("verdict") in ("POSITIVE", "NEGATIVE") else 0.0,
        "oos_consistent": oos_c,
        "cross_year": round(cross_year_frac or 0.0, 4),
        "cross_asset": round(cross_asset_frac or 0.0, 4),
        "cost_survival": 1.0 if _keeps_sign(dm, cost_adj) else 0.0,
    }
    return {"score": round(sum(DISCOVERY_WEIGHTS[k] * comp[k] for k in DISCOVERY_WEIGHTS), 4),
            "components": comp, "weights": DISCOVERY_WEIGHTS}


# --------------------------------------------------------------------------
# Classification (§1 statuses) + candidate gate (§34)
# --------------------------------------------------------------------------
def _classify(dev, oos, score, cost_adj, n_events, signed: bool = True) -> str:
    if dev.get("verdict") == "INSUFFICIENT_SAMPLE" or n_events < 30:
        return "INSUFFICIENT_SAMPLE"
    dv, ov = dev.get("verdict"), oos.get("verdict")
    dm, om = dev.get("mean"), oos.get("mean")
    same = _keeps_sign(dm, om)
    econ = _keeps_sign(dm, cost_adj) and abs(dm or 0) >= 1.3 * _COST_ATR_PROXY
    if not signed:
        # magnitude / volatility phenomenon — "economic significance" and
        # "cost" do not apply (there is no direction to trade).
        if dv in ("POSITIVE", "NEGATIVE") and ov in ("POSITIVE", "NEGATIVE") and same:
            return "REAL_PHENOMENON_NON_DIRECTIONAL"
        if dv in ("POSITIVE", "NEGATIVE"):
            return "STATISTICALLY_DETECTABLE_BUT_UNSTABLE"
        return "NO_EVIDENCE"
    if dv in ("POSITIVE", "NEGATIVE") and ov in ("POSITIVE", "NEGATIVE") and same:
        return "REAL_AND_ECONOMICALLY_MEANINGFUL" if (econ and score >= 0.55) else "REAL_BUT_SUB_COST"
    if dv in ("POSITIVE", "NEGATIVE") and same and score >= 0.42:
        return "PROMISING_BUT_UNCERTAIN"
    if dv in ("POSITIVE", "NEGATIVE"):
        return "STATISTICALLY_DETECTABLE_BUT_UNSTABLE"
    if abs(dev.get("effect_z") or 0) >= 2.0:
        return "LIKELY_ARTIFACT"
    return "NO_EVIDENCE"


def _candidate_gate(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    fails = []
    # §13: a magnitude / volatility phenomenon (signed=False) is NEVER a trading
    # candidate — "volatility will be higher" is not a direction and cannot be
    # traded without an options structure this project does not have.
    if not row.get("signed", True):
        fails.append("magnitude_phenomenon_not_a_directional_candidate")
    if row["status"] not in ("REAL_AND_ECONOMICALLY_MEANINGFUL", "PROMISING_BUT_UNCERTAIN"):
        fails.append(f"status={row['status']}")
    if (row["dev_n"] or 0) < 200:
        fails.append(f"dev_n={row['dev_n']}<200")
    if row["dev_verdict"] not in ("POSITIVE", "NEGATIVE"):
        fails.append(f"dev_verdict={row['dev_verdict']}")
    if not _keeps_sign(row["dev_mean"], row["oos_mean"]):
        fails.append("oos_sign_flip")
    # OOS magnitude must be in a stable band around dev — a huge OOS jump is
    # instability (a lucky/volatile OOS window), a tiny one is decay (§20).
    dm, om = abs(row["dev_mean"] or 0), abs(row["oos_mean"] or 0)
    if dm > 0 and not (0.4 <= om / dm <= 2.5):
        fails.append(f"oos/dev magnitude ratio {om/dm:.2f} outside [0.4, 2.5]")
    if (row["cross_year_frac"] or 0) < 0.6:
        fails.append(f"cross_year={row['cross_year_frac']}<0.6")
    # a single-instrument result is not promoted — the phenomenon must show the
    # same significant sign on at least half the tested instruments (§15, §19).
    if (row.get("cross_asset_frac") or 0) < 0.5:
        fails.append(f"cross_asset={row.get('cross_asset_frac')}<0.5 (single-instrument)")
    if not _keeps_sign(row["dev_mean"], row["cost_adj_mean"]):
        fails.append("cost_kills_sign")
    if abs(row["dev_mean"] or 0) < 1.3 * _COST_ATR_PROXY:
        fails.append(f"|effect|={abs(row['dev_mean'] or 0):.4f}<cost_proxy")
    return (len(fails) == 0, fails)


# --------------------------------------------------------------------------
# Full run (§6 memory-bounded: one instrument at a time)
# --------------------------------------------------------------------------
@dataclass
class Phase76Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    instruments: List[str]
    literature: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    dataset_manifests: Dict[str, Optional[str]]
    data_integrity: Dict[str, Any]
    dev_oos_split: str
    diagnostics: Dict[str, Any]
    scorecard: List[Dict[str, Any]]
    interaction_diagnostics: List[Dict[str, Any]]
    multiple_testing: Dict[str, Any]
    negative_knowledge: List[Dict[str, Any]]
    promising_research_queue: List[Dict[str, Any]]
    ml_readiness: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    verdict: str
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


def run(instruments: Tuple[str, ...] = ALL_INSTRUMENTS) -> Phase76Result:
    t0 = datetime.now(timezone.utc)
    tfs_needed = sorted({tf for hy in HYPOTHESES for tf in hy.timeframes})
    manifests = {}
    integrity = {}
    diagnostics = {"vol_clustering": {}, "horizon_map": {}}
    # raw[(hid, tf, inst)] = {"dev": study, "oos": study}
    raw: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for inst in instruments:
        try:
            manifests[inst] = (dataset_manifest.get_manifest(inst) or {}).get("dataset_id")
        except Exception:
            manifests[inst] = None
        for tf in tfs_needed:
            integrity[f"{inst}:{tf}"] = data_integrity(inst, tf)
        frames: Dict[str, pd.DataFrame] = {}
        for tf in tfs_needed:
            df = load_bars(inst, tf)
            if df.empty or len(df) < 500:
                continue
            df.attrs["tf"] = tf
            frames[tf] = df
        for tf in ("15m", "1h"):
            if tf in frames:
                diagnostics["vol_clustering"][f"{inst}:{tf}"] = vol_clustering(frames[tf])
                diagnostics["horizon_map"][f"{inst}:{tf}"] = horizon_map(frames[tf])
        for hy in HYPOTHESES:
            for tf in hy.timeframes:
                df = frames.get(tf)
                if df is None:
                    continue
                bound = int(len(df) * _DEV_RATIO)
                dev_df = df.iloc[:bound]
                oos_df = df.iloc[bound:].reset_index(drop=True)
                dev_df.attrs["tf"] = tf
                oos_df.attrs["tf"] = tf
                dev = study_events(dev_df, *hy.builder(dev_df), signed=hy.signed)
                oos = study_events(oos_df, *hy.builder(oos_df), signed=hy.signed, keep_rows=False)
                raw[(hy.hid, tf, inst)] = {"dev": dev, "oos": oos}
        frames.clear()
        del frames
        gc.collect()

    # ---- aggregate into a scorecard (§30)
    scorecard: List[Dict[str, Any]] = []
    per_hyp_signs: Dict[Tuple[str, str], Dict[int, int]] = {}
    for (hid, tf, inst), rr in raw.items():
        hh = _headline_h(tf)
        dev = rr["dev"]["horizons"].get(f"h{hh}", {})
        oos = rr["oos"]["horizons"].get(f"h{hh}", {})
        rows = rr["dev"].get("event_rows", [])
        # cross-year from cached dev event rows (§6.B)
        cyf = _cross_year_from_rows(rows)
        regime_dep = _regime_dependence(rows)
        dm = dev.get("mean")
        if dev.get("verdict") in ("POSITIVE", "NEGATIVE") and dm:
            per_hyp_signs.setdefault((hid, tf), {}).setdefault(1 if dm > 0 else -1, 0)
            per_hyp_signs[(hid, tf)][1 if dm > 0 else -1] += 1
        scorecard.append({
            "hypothesis": hid, "instrument": inst, "timeframe": tf, "headline_horizon": f"h{hh}",
            "tier": next(h.tier for h in HYPOTHESES if h.hid == hid),
            "phenomenon": next(h.phenomenon for h in HYPOTHESES if h.hid == hid),
            "N_dev": rr["dev"].get("n_events"), "N_oos": rr["oos"].get("n_events"),
            "dev": dev, "oos": oos,
            "dev_all_horizons": rr["dev"].get("horizons"),
            "cross_year_same_sign_frac": cyf, "regime_dependence": regime_dep,
        })

    # cross-asset fraction per (hid, tf)
    for sc in scorecard:
        signs = per_hyp_signs.get((sc["hypothesis"], sc["timeframe"]), {})
        total = len([s for s in scorecard
                     if s["hypothesis"] == sc["hypothesis"] and s["timeframe"] == sc["timeframe"]])
        dom = max(signs.values()) if signs else 0
        sc["cross_asset_frac"] = round(dom / max(1, total), 3)
        d, o = sc["dev"], sc["oos"]
        ca = d.get("cost_adj_mean")
        sc["discovery"] = discovery_score(d, o, sc["cross_year_same_sign_frac"],
                                          sc["cross_asset_frac"], ca)
        _sgn = next(h.signed for h in HYPOTHESES if h.hid == sc["hypothesis"])
        sc["status"] = _classify(d, o, sc["discovery"]["score"], ca, sc["N_dev"] or 0, signed=_sgn)
        sc["economic"] = {
            "gross_dev_effect_atr": d.get("mean"),
            "cost_proxy_atr": _COST_ATR_PROXY,
            "cost_adjusted_effect_atr": ca,
            "label": "COST_ADJUSTED_PROXY",
            "meaningful": bool(_keeps_sign(d.get("mean"), ca) and abs(d.get("mean") or 0) >= _COST_ATR_PROXY),
        }

    # ---- interaction diagnostics (§26)
    interactions = _interaction_diagnostics(raw)

    # ---- multiple testing (§23)
    tier1 = [h.hid for h in HYPOTHESES if h.tier == 1]
    m1 = len(tier1)
    diag_p = []
    for sc in scorecard:
        z = sc["dev"].get("effect_z")
        if z is not None and (sc["N_dev"] or 0) >= 20:
            diag_p.append((sc["hypothesis"], sc["instrument"], sc["timeframe"],
                           2 * (1 - _norm_cdf(abs(z)))))
    m2 = len(diag_p)
    bh = _benjamini_hochberg([p for *_x, p in diag_p], q=0.10)
    tier1_head = []
    for hid in tier1:
        cells = [s for s in scorecard if s["hypothesis"] == hid]
        nsig = sum(1 for s in cells if s["dev"].get("verdict") in ("POSITIVE", "NEGATIVE"))
        # Bonferroni-adjusted: significant at alpha/m1 ?
        bonf_sig = sum(1 for s in cells if (s["dev"].get("effect_z") is not None)
                       and 2 * (1 - _norm_cdf(abs(s["dev"]["effect_z"]))) <= 0.05 / m1)
        tier1_head.append({"hypothesis": hid, "cells": len(cells),
                           "cells_ci_excl_zero": nsig, "cells_pass_bonferroni": bonf_sig})
    mt = {
        "tier1_primary_hypotheses": m1,
        "tier1_bonferroni_alpha": round(0.05 / m1, 6),
        "tier1_headline": tier1_head,
        "tier2_diagnostic_tests": m2,
        "tier2_bh_fdr_q": 0.10,
        "tier2_surviving_bh": int(sum(bh)),
        "tier3_exploratory_tests": 0,
        "note": "no post-hoc / data-mined hypotheses were added; Tier 3 is empty by design (§5).",
    }

    # ---- negative knowledge (§32)
    negative = [{
        "hypothesis": sc["hypothesis"], "instrument": sc["instrument"], "timeframe": sc["timeframe"],
        "reason_rejected": sc["status"], "N_dev": sc["N_dev"], "N_oos": sc["N_oos"],
        "dev_effect_z": sc["dev"].get("effect_z"), "dev_verdict": sc["dev"].get("verdict"),
        "oos_verdict": sc["oos"].get("verdict"),
        "cost_adjusted_effect_atr": sc["dev"].get("cost_adj_mean"),
        "recorded": t0.date().isoformat(),
    } for sc in scorecard if sc["status"] in ("NO_EVIDENCE", "LIKELY_ARTIFACT",
                                              "STATISTICALLY_DETECTABLE_BUT_UNSTABLE",
                                              "REAL_BUT_SUB_COST")]

    # ---- promising research queue (§33) — ranked, max 5
    queue_rows = sorted(scorecard, key=lambda s: s["discovery"]["score"], reverse=True)
    queue = []
    for s in queue_rows:
        if s["status"] in ("INSUFFICIENT_SAMPLE", "NO_EVIDENCE"):
            continue
        prio = ("TOP_PRIORITY" if s["discovery"]["score"] >= 0.55 else
                "SECONDARY" if s["discovery"]["score"] >= 0.42 else
                "WATCHLIST" if s["discovery"]["score"] >= 0.30 else "NOT_WORTH_PURSUING")
        queue.append({"rank": len(queue) + 1, "hypothesis": s["hypothesis"],
                      "instrument": s["instrument"], "timeframe": s["timeframe"],
                      "phenomenon": s["phenomenon"], "score": s["discovery"]["score"],
                      "status": s["status"], "priority": prio,
                      "dev_effect_atr": s["dev"].get("mean"), "oos_effect_atr": s["oos"].get("mean"),
                      "cross_year": s["cross_year_same_sign_frac"],
                      "regime_dependence": s["regime_dependence"].get("class")})
        if len(queue) >= 5:
            break

    # ---- candidate gate (§34) — max 3
    candidates = []
    for s in sorted(scorecard, key=lambda x: x["discovery"]["score"], reverse=True):
        _signed = next(h.signed for h in HYPOTHESES if h.hid == s["hypothesis"])
        row = {"hypothesis": s["hypothesis"], "instrument": s["instrument"],
               "timeframe": s["timeframe"], "status": s["status"], "dev_n": s["N_dev"],
               "signed": _signed,
               "dev_verdict": s["dev"].get("verdict"), "dev_mean": s["dev"].get("mean"),
               "oos_mean": s["oos"].get("mean"), "cost_adj_mean": s["dev"].get("cost_adj_mean"),
               "cross_year_frac": s["cross_year_same_sign_frac"],
               "cross_asset_frac": s.get("cross_asset_frac"), "score": s["discovery"]["score"]}
        ok, fails = _candidate_gate(row)
        row["gate_pass"] = ok
        row["gate_fails"] = fails
        if ok:
            candidates.append(row)
        if len(candidates) >= 3:
            break

    # ---- ML readiness (§27)
    ml = _ml_readiness(scorecard, interactions, diagnostics, candidates)

    # ---- verdict (§43)
    _meaningful = {"REAL_AND_ECONOMICALLY_MEANINGFUL", "PROMISING_BUT_UNCERTAIN",
                   "REAL_BUT_SUB_COST", "REAL_PHENOMENON_NON_DIRECTIONAL"}
    if candidates:
        verdict = "ACTIONABLE PHENOMENA FOUND"
    elif any(s["status"] in _meaningful for s in scorecard):
        verdict = "PROMISING BUT UNCERTAIN"
    elif all((s["N_dev"] or 0) < 30 for s in scorecard):
        verdict = "INSUFFICIENT_DATA"
    else:
        verdict = "NO_ACTIONABLE_PHENOMENA"

    ident = json.dumps({"inst": list(instruments), "schema": SCHEMA_VERSION,
                        "verdict": verdict, "n_candidates": len(candidates),
                        "ml": ml["level"],
                        "rows": sorted((s["hypothesis"], s["instrument"], s["timeframe"],
                                        s["N_dev"], s["status"],
                                        round(s["discovery"]["score"], 3)) for s in scorecard)},
                       sort_keys=True)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase76Result(
        schema_version=SCHEMA_VERSION,
        generated_at=t0.isoformat(),
        git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        instruments=list(instruments), literature=LITERATURE,
        hypotheses=[{
            "hid": h.hid, "phenomenon": h.phenomenon, "literature_ids": list(h.literature_ids),
            "null_hypothesis": h.null_hypothesis, "alternative_hypothesis": h.alternative_hypothesis,
            "timeframes": list(h.timeframes), "signed": h.signed, "tier": h.tier,
            "forward_horizons_bars": list(FWD_HORIZONS),
            "economic_interpretation": h.economic_interpretation} for h in HYPOTHESES],
        dataset_manifests=manifests, data_integrity=integrity,
        dev_oos_split=f"chronological {int(_DEV_RATIO*100)}/{100-int(_DEV_RATIO*100)} on bar index",
        diagnostics=diagnostics, scorecard=scorecard, interaction_diagnostics=interactions,
        multiple_testing=mt, negative_knowledge=negative,
        promising_research_queue=queue, ml_readiness=ml, candidates=candidates,
        verdict=verdict, runtime_seconds=round(rt, 1), content_hash=chash,
    )


# --- aggregation helpers ------------------------------------------------
def _cross_year_from_rows(rows: List[Dict[str, Any]]) -> Optional[float]:
    if not rows:
        return None
    by_year: Dict[int, List[float]] = {}
    for r in rows:
        by_year.setdefault(r["year"], []).append(r["fwd_r"])
    yrs = {y: v for y, v in by_year.items() if len(v) >= 20}
    if len(yrs) < 3:
        return None
    signs = [1 if (sum(v) / len(v)) > 0 else -1 for v in yrs.values()]
    dom = max(set(signs), key=signs.count)
    return round(signs.count(dom) / len(signs), 3)


def _regime_dependence(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"class": "UNKNOWN"}
    by_reg: Dict[str, List[float]] = {}
    for r in rows:
        by_reg.setdefault(r["regime"], []).append(r["fwd_r"])
    means = {k: round(sum(v) / len(v), 5) for k, v in by_reg.items() if len(v) >= 20}
    if len(means) < 2:
        return {"class": "UNKNOWN", "by_regime_mean": means}
    vals = list(means.values())
    span = max(vals) - min(vals)
    signs = set(1 if v > 0 else -1 for v in vals)
    cls = ("SIGN_FLIPS_BY_REGIME" if len(signs) > 1 and span > 0.05 else
           "MAGNITUDE_VARIES_BY_REGIME" if span > 0.05 else "REGIME_INVARIANT")
    return {"class": cls, "by_regime_mean": means, "span": round(span, 5)}


def _interaction_diagnostics(raw: Dict[Tuple[str, str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """§26 pre-declared: does an effect flip sign or materially change magnitude when
    conditioned on regime or session? Uses the cached dev event rows only."""
    out = []
    pairs = [("H2_INTRADAY_MOM", "15m", "regime"), ("H2_INTRADAY_MOM", "15m", "session"),
             ("H3_ST_REVERSAL", "15m", "regime"), ("H3_ST_REVERSAL", "15m", "session"),
             ("H8_RANGE_EXPANSION_1_5", "15m", "regime"),
             ("H11_PREV_DAY_HIGH", "15m", "session")]
    for hid, tf, cond in pairs:
        cells = []
        for (h2, t2, inst), rr in raw.items():
            if h2 != hid or t2 != tf:
                continue
            rows = rr["dev"].get("event_rows", [])
            buckets: Dict[str, List[float]] = {}
            for r in rows:
                buckets.setdefault(r[cond], []).append(r["fwd_r"])
            means = {k: round(sum(v) / len(v), 5) for k, v in buckets.items() if len(v) >= 25}
            if len(means) >= 2:
                v = list(means.values())
                cells.append({"instrument": inst, "by_" + cond: means,
                              "sign_flip": len(set(1 if x > 0 else -1 for x in v)) > 1,
                              "span": round(max(v) - min(v), 5)})
        if cells:
            out.append({"hypothesis": hid, "timeframe": tf, "conditioner": cond,
                        "n_instruments": len(cells),
                        "instruments_with_sign_flip": sum(1 for c in cells if c["sign_flip"]),
                        "cells": cells})
    return out


def _ml_readiness(scorecard, interactions, diagnostics, candidates) -> Dict[str, Any]:
    _dir = {h.hid for h in HYPOTHESES if h.signed}
    # a modelling *target* needs a robust DIRECTIONAL phenomenon
    directional_strong = [s for s in scorecard if s["hypothesis"] in _dir
                          and s["status"] == "REAL_AND_ECONOMICALLY_MEANINGFUL"]
    strong = [s for s in scorecard if s["status"] in
              ("REAL_AND_ECONOMICALLY_MEANINGFUL", "PROMISING_BUT_UNCERTAIN",
               "REAL_PHENOMENON_NON_DIRECTIONAL")]
    detectable = [s for s in scorecard if s["status"] not in
                  ("INSUFFICIENT_SAMPLE", "NO_EVIDENCE")]
    conditional = [i for i in interactions if i["instruments_with_sign_flip"] >= 2]
    total_events = sum((s["N_dev"] or 0) + (s["N_oos"] or 0) for s in scorecard)
    clustering = any(v.get("clustering_present") for v in diagnostics["vol_clustering"].values())
    if candidates and directional_strong:
        level = "PROMISING"
    elif (strong or conditional) and detectable:
        level = "DATA_READY_BUT_EDGE_UNCLEAR"
    else:
        level = "NOT_READY"
    return {
        "level": level,
        "phenomena_with_meaningful_evidence": [f"{s['hypothesis']}:{s['instrument']}:{s['timeframe']}"
                                               for s in strong],
        "detectable_but_weak_count": len(detectable),
        "conditional_effects_found": [f"{i['hypothesis']} x {i['conditioner']}" for i in conditional],
        "total_events_all_cells": int(total_events),
        "volatility_clustering_usable_as_context": bool(clustering),
        "recommended_ml_use": (
            ["regime/context classification", "abstention / no-trade decisions",
             "probability calibration of a deterministic candidate"] if level != "NOT_READY"
            else ["none yet — establish at least one robust phenomenon first"]),
        "do_not_model_yet": ["raw candles -> BUY/SELL", "position sizing", "multi-asset joint policy",
                             "any sequence model (LSTM/Transformer) on this evidence base"],
        "architecture_thesis_supported": bool(conditional),
        "architecture_note": (
            "conditional effects (effect changes sign/magnitude by regime or session) were "
            + ("found" if conditional else "NOT found") + " — this "
            + ("supports" if conditional else "does not yet support")
            + " a 'market-state + validated-phenomenon + context -> probability' architecture "
              "over 'candles -> BUY/SELL'."),
        "data_gaps": ["native 1m depth (XAUUSD ~3.4mo cap) limits sub-15m event studies",
                      "no historical high-impact-event calendar for news conditioning",
                      "~4.1y of 15m limits cross-year replication to 4-5 segments"],
    }


# --------------------------------------------------------------------------
def persist(result: Optional[Phase76Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase76_market_behavior_discovery",
                               result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 76 — literature-guided market behavior discovery ...", flush=True)
    res = run()
    print(f"\n=== PHASE 76 ({len(res.instruments)} instruments, {res.runtime_seconds}s) ===")
    print("\nSCORECARD (headline horizon, dev vs OOS):")
    print(f"{'HYP':<24}{'INST':<8}{'TF':<5}{'Ndev':>6}{'DEVmean':>9}{'z':>6}{'DEVv':>13}"
          f"{'OOSmean':>9}{'OOSv':>13}{'cy':>5}{'score':>6} STATUS")
    for s in sorted(res.scorecard, key=lambda x: x["discovery"]["score"], reverse=True):
        d, o = s["dev"], s["oos"]
        print(f"{s['hypothesis']:<24}{s['instrument']:<8}{s['timeframe']:<5}{str(s['N_dev']):>6}"
              f"{str(d.get('mean')):>9}{str(d.get('effect_z')):>6}{str(d.get('verdict')):>13}"
              f"{str(o.get('mean')):>9}{str(o.get('verdict')):>13}"
              f"{str(s['cross_year_same_sign_frac']):>5}{str(s['discovery']['score']):>6} {s['status']}")
    print("\nHORIZON MAP (15m, XAUUSD):", res.diagnostics["horizon_map"].get("XAUUSD:15m", {}).get("by_k"))
    print("VOL CLUSTERING (15m, XAUUSD):", {k: v for k, v in
          res.diagnostics["vol_clustering"].get("XAUUSD:15m", {}).items()
          if k in ("atr_ar1", "abs_return_acf", "clustering_present")})
    print(f"\nMULTIPLE TESTING: {res.multiple_testing['tier1_primary_hypotheses']} primary "
          f"(bonf a={res.multiple_testing['tier1_bonferroni_alpha']}), "
          f"{res.multiple_testing['tier2_diagnostic_tests']} diag, "
          f"BH survivors={res.multiple_testing['tier2_surviving_bh']}")
    print(f"\nPROMISING QUEUE ({len(res.promising_research_queue)}):")
    for q in res.promising_research_queue:
        print(f"  #{q['rank']} {q['hypothesis']} {q['instrument']} {q['timeframe']} "
              f"score={q['score']} {q['priority']} ({q['status']})")
    print(f"\nCANDIDATES ({len(res.candidates)}):")
    for c in res.candidates:
        print(f"  {c['hypothesis']} {c['instrument']} {c['timeframe']} score={c['score']}")
    print(f"\nML_READINESS = {res.ml_readiness['level']}")
    print(f"VERDICT: {res.verdict}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["run", "persist", "get_result", "load_bars", "study_events", "block_bootstrap",
           "vol_clustering", "horizon_map", "discovery_score", "data_integrity",
           "HYPOTHESES", "LITERATURE", "ARTIFACT_KEY", "SCHEMA_VERSION", "Phase76Result",
           "PRIMARY_INSTRUMENTS", "ALL_INSTRUMENTS", "FWD_HORIZONS"]
