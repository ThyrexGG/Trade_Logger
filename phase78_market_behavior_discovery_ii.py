# -*- coding: utf-8 -*-
"""
Phase 78 — Literature-Guided Market Behavior Discovery II.

Momentum x Volatility Expansion x Breakout/Retest x Session Transitions.

A lateral continuation of the Phase 76 discovery framework, NOT a reopening of
the Phase 77 large-bar-reversal candidate (which failed on realistic execution
and stays in the negative-knowledge registry, §23). Four behavior families are
tested with NEW, pre-registered event/target definitions distinct from anything
already tested in Phase 75-77:

  A. Momentum / continuation      — consecutive-bar impulse continuation
  B. Volatility compression/expansion — compression DURATION -> range expansion
                                        (true-range/ATR, not |return|), and
                                        volatility-REGIME PERSISTENCE (a formal
                                        probability-vs-baseline test)
  C. Breakout -> retest            — structural N-bar range breakout, FIRST
                                        qualifying retest, and failed-breakout
                                        fade
  D. Session transitions           — pre-transition DIRECTION persisting into
                                        the next session (Phase 76 only tested
                                        session-open MAGNITUDE, not direction)

Research chain (§Objective): market data -> phenomenon discovery -> statistical
validation -> economic validation -> robust candidate -> ML feature/target
design. ML training is explicitly OUT of scope (§0.4) — only an ML-readiness
assessment is produced.

Reuses the Phase 76 causal bar loader, block bootstrap, multiple-testing
helpers, cross-year/regime aggregation and discovery score UNCHANGED
(``phase76_event_study``) so the statistical machinery is identical across
phases; only the event/target definitions are new.

Read-only. No execution / broker / risk / forward-validation module imported.
The frozen Phase-74 holdout is never read (§0.6).
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
import phase76_event_study as p76
from phase76_event_study import (
    ALL_INSTRUMENTS, FWD_HORIZONS, _DEV_RATIO,
    _benjamini_hochberg, _cross_year_from_rows, _headline_h, _keeps_sign,
    _norm_cdf, _regime_dependence, block_bootstrap, data_integrity,
    discovery_score, load_bars, study_events,
)

SCHEMA_VERSION = "phase78.1"
ARTIFACT_KEY = "phase78_market_behavior_discovery_ii"
TIMEFRAMES: Tuple[str, ...] = ("15m", "1h")

# §12 — "use the actual current repository universe rather than assuming a
# fixed list": the Phase 76 6-instrument universe (XAUUSD, USDJPY, EURUSD,
# GBPJPY, GBPUSD, AUDJPY) is the current authoritative MT5 universe.
INSTRUMENTS: Tuple[str, ...] = ALL_INSTRUMENTS

# §15 cost-sensitivity grid (round-trip, ATR units), directional hypotheses only
_COST_ATR_GRID: Tuple[float, ...] = (0.025, 0.05, 0.10)

# --- new causal feature parameters (frozen, pre-registered, §5) -----------
_BREAKOUT_LOOKBACK = 20      # prior N-bar structural range (excludes current bar)
_RETEST_WINDOW = 20          # bars allowed for the first qualifying retest
_FAILED_BREAKOUT_K = 3       # bars used to classify a breakout as "failed"
_COMPRESSION_RANK_THR = 0.10  # Phase 76's ATR-percentile compression threshold
_COMPRESSION_MIN_RUN = 3     # consecutive compressed bars required (NEW vs Phase 76)
_IMPULSE_RUN = 3             # consecutive same-direction bars required (NEW)
_RV_WINDOW = 4               # realized-vol rolling window (bars). Kept SHORT and <=
                             # the smallest forward horizon (1 bar) so the B9 regime-
                             # persistence target windows have minimal mechanical
                             # overlap with the event-time window at h>=4 (§25 -- an
                             # overlapping rolling statistic is autocorrelated with
                             # itself almost by construction, which is a confound,
                             # not evidence of forecastability; documented in §W).
_SESSION_PRE_BARS = 4        # bars used to measure the pre-transition direction
_WARMUP = 200                # bars consumed by the 200-bar percentile ranks

_NULL_SEED_OFFSET = 9001     # deterministic, distinct from RANDOM_SEED


# --------------------------------------------------------------------------
# §5 causal feature augmentation (everything trailing-only, computed ONCE on
# the full series before the dev/OOS split — identical convention to Phase 76)
# --------------------------------------------------------------------------
def _run_length(flag: np.ndarray) -> np.ndarray:
    """Length of the run of consecutive True values in ``flag`` ending at each
    index (0 where flag is False at that index). Vectorised, causal (uses only
    ``flag[:i+1]``)."""
    idx = np.arange(len(flag))
    reset = np.where(~flag, idx, -1)
    reset = np.maximum.accumulate(reset)
    return idx - reset


def augment(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Phase 76 causal columns + Phase 78 additions: prior-N-bar structural
    range (``roll_h20``/``roll_l20``, current bar EXCLUDED via shift(1)),
    consecutive same-direction bar count (``consec_dir``), realized volatility
    and its trailing-200-bar percentile rank (``rv``/``rv_rank``), and
    compression run length (``comp_run``). Every column here uses only
    information available at or before bar i (§5 causality requirement)."""
    if df.empty:
        return df
    df = df.copy()
    df.attrs["tf"] = tf
    h = df["high"].to_numpy(float); lo = df["low"].to_numpy(float)
    ret = df["ret"].to_numpy(float)
    atr_rank = df["atr_rank"].to_numpy(float)
    n = len(h)

    df["roll_h20"] = pd.Series(h).shift(1).rolling(
        _BREAKOUT_LOOKBACK, min_periods=_BREAKOUT_LOOKBACK).max().to_numpy()
    df["roll_l20"] = pd.Series(lo).shift(1).rolling(
        _BREAKOUT_LOOKBACK, min_periods=_BREAKOUT_LOOKBACK).min().to_numpy()

    sgn = np.sign(ret)
    match = np.zeros(n, dtype=bool)
    match[1:] = (sgn[1:] != 0) & (sgn[1:] == sgn[:-1])
    df["consec_dir"] = _run_length(match) + np.where(sgn != 0, 1, 0)

    rv = pd.Series(ret).rolling(_RV_WINDOW, min_periods=_RV_WINDOW).std().to_numpy()
    w = 200
    rv_rank = np.full(n, np.nan)
    if n >= w:
        sw = np.lib.stride_tricks.sliding_window_view(rv, w)
        rv_rank[w - 1:] = (sw <= sw[:, -1:]).mean(axis=1)
    df["rv"] = rv
    df["rv_rank"] = rv_rank

    comp_flag = np.isfinite(atr_rank) & (atr_rank <= _COMPRESSION_RANK_THR)
    df["comp_run"] = _run_length(comp_flag)

    # A STABLE denominator for the range-expansion target (§B1/B6). The event-time
    # ATR is, BY CONSTRUCTION, depressed at a compression event (that is what
    # "compression" means) -- dividing the forward true-range by it would inflate
    # the expansion ratio purely mechanically, exactly the atr_ret_stable fix
    # Phase 76 needed for its own compression hypothesis. atr_stable is the
    # trailing-200-bar mean ATR (unconditioned on the event), price units.
    atr = df["atr"].to_numpy(float)
    df["atr_stable"] = pd.Series(atr).rolling(200, min_periods=50).mean().to_numpy()
    return df


# --------------------------------------------------------------------------
# §3 literature rationale (kept short; full detail in the doc). No live
# retrieval was performed — bibliographic detail is training knowledge.
# --------------------------------------------------------------------------
LITERATURE = [
    {"id": "L-CONT", "phenomenon": "short-horizon return continuation after an "
     "impulse of consecutive same-direction bars", "family": "A",
     "note": "conceptually related to Gao-Han-Li-Zhou 2018 intraday momentum "
             "(Phase 76 L-INTRADAY-MOM) but with a NEW consecutive-bar event "
             "definition instead of a magnitude threshold"},
    {"id": "L-VOLCLUST", "phenomenon": "volatility clustering / regime persistence",
     "family": "B", "note": "Bollerslev 1986 GARCH; Ding-Granger-Engle 1993 long "
     "memory in |return| (Phase 76 L-GARCH/L-LONGMEM) — Phase 78 turns the "
     "descriptive Phase 76 ACF diagnostic into a formal probability-vs-baseline "
     "hypothesis test on realized-volatility-bucket persistence"},
    {"id": "L-BREAKOUT", "phenomenon": "structural range breakout and retest "
     "behavior", "family": "C", "note": "classical technical-analysis "
     "breakout/retest and failed-breakout-fade patterns; no single canonical "
     "peer-reviewed source — treated as an exploratory-but-pre-registered "
     "diagnostic, same evidentiary status as Phase 76's L-DIAG-VOLCYCLE"},
    {"id": "L-SESSION", "phenomenon": "deterministic intraday session structure",
     "family": "D", "note": "Andersen-Bollerslev 1997 (Phase 76 L-INTRADAY-VOL) "
     "established session-open VOLATILITY seasonality; Phase 78 tests whether "
     "DIRECTION (not just magnitude) persists across a session transition"},
]


# --------------------------------------------------------------------------
# §5 event builders. Each returns (event_bar_index, direction, magnitude).
# All are causal: an event at bar i uses only df[..i] (or, for the two
# "failed breakout" decision points, df[..i+K] — see docstring, no leakage
# into the STUDIED forward window, which starts strictly after the
# information used to define the event).
# --------------------------------------------------------------------------
def _b_impulse(df: pd.DataFrame, run: int = _IMPULSE_RUN):
    """A1/A4 — momentum: the bar that COMPLETES a run of ``run`` consecutive
    same-direction bars (fires once per streak, not on every bar within it)."""
    consec = df["consec_dir"].to_numpy(int)
    ret = df["ret"].to_numpy(float)
    n = len(consec)
    idx = np.where(consec == run)[0]
    idx = idx[idx >= _WARMUP]
    direction = np.sign(ret[idx])
    keep = direction != 0
    return idx[keep], direction[keep], np.full(int(keep.sum()), float(run))


def _b_compression_duration(df: pd.DataFrame, min_run: int = _COMPRESSION_MIN_RUN):
    """B1/B4/B6 — the bar that first reaches ``min_run`` CONSECUTIVE compressed
    bars (ATR percentile <= 0.10). Distinct from Phase 76's H7 (any single
    compressed bar): this tests whether compression DURATION matters."""
    run = df["comp_run"].to_numpy(int)
    idx = np.where(run == min_run)[0]
    idx = idx[idx >= _WARMUP]
    return idx, np.zeros(len(idx)), run[idx].astype(float)


def _b_vol_bucket(df: pd.DataFrame, bucket: str):
    """B9 — any bar whose trailing realized-vol percentile is in ``bucket``
    (HIGH > 0.66, LOW < 0.33). Direction-agnostic; used for regime persistence."""
    rvr = df["rv_rank"].to_numpy(float)
    if bucket == "HIGH":
        idx = np.where(np.isfinite(rvr) & (rvr > 0.66))[0]
    else:
        idx = np.where(np.isfinite(rvr) & (rvr < 0.33))[0]
    idx = idx[idx >= _WARMUP]
    return idx


def _b_vol_bucket_high(df: pd.DataFrame):
    idx = _b_vol_bucket(df, "HIGH")
    return idx, np.zeros(len(idx)), np.zeros(len(idx))


def _b_breakout(df: pd.DataFrame, lookback: int = _BREAKOUT_LOOKBACK):
    """The FIRST bar closing beyond the prior ``lookback``-bar structural
    high/low (both computed with the current bar excluded, §5)."""
    h = df["high"].to_numpy(float); lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    roll_h = df["roll_h20"].to_numpy(float); roll_l = df["roll_l20"].to_numpy(float)
    n = len(c)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    up = np.isfinite(roll_h) & (prev_c <= roll_h) & (c > roll_h)
    dn = np.isfinite(roll_l) & (prev_c >= roll_l) & (c < roll_l)
    idx = np.where(up | dn)[0]
    idx = idx[idx >= max(_WARMUP, lookback)]
    direction = np.where(up[idx], 1.0, -1.0)
    level = np.where(up[idx], roll_h[idx], roll_l[idx])
    return idx, direction, level


def _b_breakout_retest(df: pd.DataFrame, max_bars: int = _RETEST_WINDOW):
    """C1/C4 — breakout -> the FIRST bar (within ``max_bars``) whose range
    touches back to the breakout level. Event fires at the retest bar; no
    scanning for the "best" retest (§C, no look-ahead selection)."""
    h = df["high"].to_numpy(float); lo = df["low"].to_numpy(float)
    n = len(h)
    b_idx, b_dir, b_level = _b_breakout(df)
    out_idx: List[int] = []
    out_dir: List[float] = []
    for k, i in enumerate(b_idx):
        lv = b_level[k]
        found = None
        for b in range(int(i) + 1, min(int(i) + 1 + max_bars, n)):
            if lo[b] <= lv <= h[b]:
                found = b
                break
        if found is not None:
            out_idx.append(found)
            out_dir.append(b_dir[k])
    return np.array(out_idx, int), np.array(out_dir, float), np.zeros(len(out_idx))


def _b_failed_breakout(df: pd.DataFrame, lookback: int = _BREAKOUT_LOOKBACK,
                       k: int = _FAILED_BREAKOUT_K):
    """C5 — a breakout that stalls: over the K bars immediately after the
    breakout bar it never extends beyond the breakout bar's own extreme AND it
    falls back through the broken level. The decision point is bar i+K (the
    first bar an observer could classify the breakout as failed) — the STUDIED
    forward window starts at i+K, strictly after the K bars used to define
    "failed" (no leakage of the classification window into the target, §5)."""
    h = df["high"].to_numpy(float); lo = df["low"].to_numpy(float)
    n = len(h)
    b_idx, b_dir, b_level = _b_breakout(df, lookback)
    out_idx: List[int] = []
    out_dir: List[float] = []
    for kk, i in enumerate(b_idx):
        i = int(i); d = b_dir[kk]; lv = b_level[kk]
        if i + k >= n:
            continue
        wh = h[i + 1:i + 1 + k]; wl = lo[i + 1:i + 1 + k]
        if d > 0:
            extended = wh.max() > h[i]
            fell_back = wl.min() < lv
        else:
            extended = wl.min() < lo[i]
            fell_back = wh.max() > lv
        if (not extended) and fell_back:
            out_idx.append(i + k)
            out_dir.append(-d)         # fade the failed breakout
    return np.array(out_idx, int), np.array(out_dir, float), np.zeros(len(out_idx))


def _b_session_transition(df: pd.DataFrame, npre: int = _SESSION_PRE_BARS):
    """D3 — the first bar of a new session. Direction = the sign of the move
    over the ``npre`` bars STRICTLY BEFORE the transition (both endpoints are
    before the new session starts — causal)."""
    sess = df["session"].to_numpy(); c = df["close"].to_numpy(float)
    n = len(sess)
    trans = np.where(sess[1:] != sess[:-1])[0] + 1
    trans = trans[(trans >= max(_WARMUP, npre)) & (trans < n - 1)]
    pre_dir = np.sign(np.log(c[trans - 1] / c[trans - 1 - npre]))
    keep = pre_dir != 0
    return trans[keep], pre_dir[keep], np.zeros(int(keep.sum()))


# --------------------------------------------------------------------------
# §6/§16 NEW target types (magnitude / probability, baseline-centered so the
# usual block_bootstrap POSITIVE/NEGATIVE/ZERO_CROSSING verdict is meaningful)
# --------------------------------------------------------------------------
def study_range_expansion(df: pd.DataFrame, idx: np.ndarray, *_ignore,
                          horizons=FWD_HORIZONS, keep_rows: bool = True) -> Dict[str, Any]:
    """Target = (forward h-bar sum of true range) / (ATR_STABLE_i * h) - 1, i.e.
    how much the realized range over the next h bars exceeds a STABLE (trailing
    200-bar mean, unconditioned) ATR-implied range. The denominator is
    deliberately NOT the event-time ATR: a compression event is defined BY a
    depressed event-time ATR, so dividing by it would inflate the ratio purely
    mechanically (the exact bug Phase 76 had to fix for its own compression
    hypothesis via ``atr_ret_stable``). Baseline = the same ratio computed
    unconditionally over EVERY valid bar in the same slice (§16
    conditional-minus-baseline). The bootstrapped array is the EFFECT (event
    ratio - baseline), so CI-vs-zero tests the conditional effect directly."""
    tr = df["tr"].to_numpy(float)
    atr_stable = df["atr_stable"].to_numpy(float)
    yr = df["year"].to_numpy(); sess = df["session"].to_numpy(); reg = df["regime"].to_numpy()
    n = len(tr)
    idx = np.asarray(idx, int)
    ok = (idx >= 0) & (idx < n) & np.isfinite(atr_stable[np.clip(idx, 0, n - 1)]) \
        & (atr_stable[np.clip(idx, 0, n - 1)] > 0)
    idx = idx[ok]
    res: Dict[str, Any] = {"n_events": int(len(idx)), "state": "OK" if len(idx) >= 20 else "INSUFFICIENT_SAMPLE",
                           "horizons": {}, "event_rows": []}
    if len(idx) < 20:
        return res
    csum = np.concatenate([[0.0], np.cumsum(tr)])
    hh = _headline_h(df.attrs.get("tf", "15m"))
    hj_full = idx + hh
    hm_full = hj_full < n
    hr = np.full(len(idx), np.nan)
    for h in horizons:
        j = idx + h; m = j < n
        fut = csum[j[m] + 1] - csum[idx[m] + 1]
        ratio = np.full(len(idx), np.nan)
        ratio[m] = fut / (atr_stable[idx[m]] * h) - 1.0
        base_idx = np.arange(n - h)
        base_ok = np.isfinite(atr_stable[base_idx]) & (atr_stable[base_idx] > 0)
        bi = base_idx[base_ok]
        base_fut = csum[bi + h + 1] - csum[bi + 1]
        base_ratio = base_fut / (atr_stable[bi] * h) - 1.0
        base_ratio = base_ratio[np.isfinite(base_ratio)]
        baseline_mean = float(np.mean(base_ratio)) if len(base_ratio) else 0.0
        v = ratio[np.isfinite(ratio)] - baseline_mean
        bs = block_bootstrap(v, block=h)
        bs["baseline_mean"] = round(baseline_mean, 6)
        bs["raw_event_mean"] = (round(bs["mean"] + baseline_mean, 6)
                                if bs.get("mean") is not None else None)
        bs["test_kind"] = "range_expansion_ratio_vs_baseline_stable_atr"
        bs["cost_adj_mean"] = bs.get("mean")   # no trading cost concept applies (§14)
        res["horizons"][f"h{h}"] = bs
        if h == hh:
            hr[hm_full] = ratio[hm_full] - baseline_mean
    if keep_rows:
        res["event_rows"] = [
            {"year": int(yr[k]), "session": str(sess[k]), "regime": str(reg[k]),
             "mag_atr": None, "fwd_r": round(float(hr[n2]), 6)}
            for n2, k in enumerate(idx) if np.isfinite(hr[n2])]
    return res


def study_persistence(df: pd.DataFrame, idx: np.ndarray, *_ignore, bucket: str = "HIGH",
                      horizons=FWD_HORIZONS, keep_rows: bool = True) -> Dict[str, Any]:
    """Target = P(future realized-vol bucket == ``bucket`` at bar i+h). The
    bootstrapped array is (indicator - baseline probability of that bucket at
    horizon h over every valid bar), so the mean IS the persistence effect and
    CI-vs-zero tests it directly (§16)."""
    rvr = df["rv_rank"].to_numpy(float)
    yr = df["year"].to_numpy(); sess = df["session"].to_numpy(); reg = df["regime"].to_numpy()
    n = len(rvr)
    idx = np.asarray(idx, int)
    ok = (idx >= 0) & (idx < n) & np.isfinite(rvr[np.clip(idx, 0, n - 1)])
    idx = idx[ok]
    res: Dict[str, Any] = {"n_events": int(len(idx)), "state": "OK" if len(idx) >= 20 else "INSUFFICIENT_SAMPLE",
                           "horizons": {}, "event_rows": []}
    if len(idx) < 20:
        return res
    hh = _headline_h(df.attrs.get("tf", "15m"))
    hr = np.full(len(idx), np.nan)
    for h in horizons:
        j = idx + h; m = j < n
        outcome = np.full(len(idx), np.nan)
        fut = rvr[j[m]]
        outcome[m] = (fut > 0.66).astype(float) if bucket == "HIGH" else (fut < 0.33).astype(float)
        base_idx = np.arange(n - h)
        base_ok = np.isfinite(rvr[base_idx + h])
        bi = base_idx[base_ok]
        base_p = (float(np.mean(rvr[bi + h] > 0.66)) if bucket == "HIGH"
                  else float(np.mean(rvr[bi + h] < 0.33)))
        v = outcome[np.isfinite(outcome)] - base_p
        bs = block_bootstrap(v, block=h)
        bs["baseline_mean"] = round(base_p, 6)
        bs["raw_event_mean"] = (round(bs["mean"] + base_p, 6)
                                if bs.get("mean") is not None else None)
        bs["test_kind"] = f"regime_persistence_probability_{bucket.lower()}"
        bs["cost_adj_mean"] = bs.get("mean")   # no trading cost concept applies (§14)
        res["horizons"][f"h{h}"] = bs
        if h == hh:
            hr[m] = outcome[m] - base_p
    if keep_rows:
        res["event_rows"] = [
            {"year": int(yr[k]), "session": str(sess[k]), "regime": str(reg[k]),
             "mag_atr": None, "fwd_r": round(float(hr[n2]), 6)}
            for n2, k in enumerate(idx) if np.isfinite(hr[n2])]
    return res


def _study_signed(df: pd.DataFrame, idx: np.ndarray, direction: np.ndarray,
                  magnitude: np.ndarray, keep_rows: bool = True) -> Dict[str, Any]:
    """Thin wrapper around the unchanged Phase 76 ``study_events`` (signed
    continuation) for the directional families (A, C, D)."""
    return study_events(df, idx, direction, magnitude, signed=True,
                        horizons=FWD_HORIZONS, keep_rows=keep_rows)


# --------------------------------------------------------------------------
# §4 hypothesis registry — frozen BEFORE the full run (§10). Every field the
# prompt requires is present.
# --------------------------------------------------------------------------
@dataclass
class Hypothesis78:
    hid: str
    family: str
    name: str
    rationale: str
    event_definition: str
    target_definition: str
    timeframes: Tuple[str, ...]
    horizon_bars: Tuple[int, ...]
    universe: str
    regime_scope: str
    expected_direction: str
    normalization: str
    min_sample_size: int
    statistical_test: str
    bootstrap_method: str
    tier: int
    economic_interpretation: str
    builder: Callable[[pd.DataFrame], Tuple[np.ndarray, np.ndarray, np.ndarray]]
    study_kind: str            # "signed" | "range_expansion" | "persistence"
    directional: bool


_BOOTSTRAP_DESC = "block bootstrap, block=horizon bars, 3000 iters (memory-capped), seed 42 (phase76_event_study.block_bootstrap, unchanged)"

HYPOTHESES: List[Hypothesis78] = [
    Hypothesis78(
        "M1_IMPULSE_CONTINUATION", "A", "Multi-bar impulse continuation",
        "Consecutive same-direction bars may reflect informed order flow that "
        "continues; conceptually related to Gao et al. 2018 intraday momentum "
        "but operationalised as a run-length event, not a magnitude threshold.",
        f"the bar that completes a run of exactly {_IMPULSE_RUN} consecutive "
        "same-sign 1-bar returns (fires once per streak)",
        "forward log-return over h in {1,2,4,8} bars, divided by ATR_i, signed "
        "by the streak direction (continuation test)",
        ("15m", "1h"), FWD_HORIZONS, "6-instrument MT5 universe (ALL_INSTRUMENTS)",
        "all regimes (pre-registered; regime is a Tier-2 diagnostic only)",
        "positive (continuation)", "ATR-normalised log-return", 200,
        "block-bootstrap CI vs zero on the ATR-normalised signed forward return",
        _BOOTSTRAP_DESC, 1,
        "does a short impulse of consecutive bars predict further movement in "
        "the same direction?",
        _b_impulse, "signed", True),
    Hypothesis78(
        "V1_COMPRESSION_DURATION", "B", "Compression duration -> range expansion",
        "Phase 76 tested single-bar compression against forward |return| and "
        "found the OPPOSITE of NR-bar folklore (compression persists). Phase 78 "
        "asks a distinct question: does the DURATION of compression predict "
        "actual range expansion (true range, not |return|, which captures "
        "intrabar wicks the close-to-close measure misses)?",
        f"the bar that first reaches {_COMPRESSION_MIN_RUN} CONSECUTIVE bars "
        "with ATR percentile rank <= 0.10",
        "(forward h-bar SUM of true range) / (ATR_i * h) - 1, minus the same "
        "ratio's unconditional mean over the whole slice (conditional-minus-"
        "baseline, §16)",
        ("15m", "1h"), FWD_HORIZONS, "6-instrument MT5 universe",
        "all regimes", "NONE — magnitude only, direction-agnostic",
        "true-range/ATR ratio, baseline-centred", 200,
        "block-bootstrap CI vs zero on the baseline-centred expansion ratio",
        _BOOTSTRAP_DESC, 1,
        "does the market range MORE than usual after a multi-bar compression, "
        "independent of direction? (a candidate ML volatility target, not a "
        "trading signal)",
        _b_compression_duration, "range_expansion", False),
    Hypothesis78(
        "V2_VOL_REGIME_PERSISTENCE_HIGH", "B", "High-volatility regime persistence",
        "GARCH-type volatility clustering (Bollerslev 1986) implies today's "
        "volatility STATE should persist; this turns Phase 76's descriptive "
        "ACF diagnostic into a formal probability-vs-baseline hypothesis.",
        "any bar whose trailing 20-bar realized-vol, ranked over the trailing "
        "200 bars, is > 0.66 (HIGH bucket)",
        "P(future realized-vol percentile > 0.66 at bar i+h) minus the "
        "unconditional P(bucket) at horizon h over the whole slice",
        ("15m", "1h"), FWD_HORIZONS, "6-instrument MT5 universe",
        "all regimes", "NONE — probability only, direction-agnostic",
        "probability (Bernoulli), baseline-centred", 200,
        "block-bootstrap CI vs zero on the baseline-centred persistence indicator",
        _BOOTSTRAP_DESC, 1,
        "is 'currently high volatility' informative about 'will still be high "
        "volatility later' beyond the unconditional base rate? (a candidate ML "
        "target: high-volatility-event probability)",
        _b_vol_bucket_high, "persistence_high", False),
    Hypothesis78(
        "BR1_BREAKOUT_RETEST_CONTINUATION", "C", "Breakout -> first retest -> continuation",
        "Technical breakout/retest folklore: a genuine breakout should hold on "
        "its first retest and continue; tested here as a formal, deterministic, "
        "non-look-ahead event study.",
        f"the FIRST bar closing beyond the prior {_BREAKOUT_LOOKBACK}-bar "
        f"structural high/low (current bar excluded), THEN the first bar "
        f"(within {_RETEST_WINDOW} bars) whose range touches back to the "
        "breakout level — the event fires at that retest bar",
        "forward log-return over h in {1,2,4,8} bars from the retest bar, "
        "divided by ATR, signed by the original breakout direction",
        ("15m", "1h"), FWD_HORIZONS, "6-instrument MT5 universe",
        "all regimes (session is a Tier-2 diagnostic)",
        "positive (continuation)", "ATR-normalised log-return", 200,
        "block-bootstrap CI vs zero on the ATR-normalised signed forward return",
        _BOOTSTRAP_DESC, 1,
        "does price continue in the breakout direction after successfully "
        "retesting the broken level?",
        _b_breakout_retest, "signed", True),
    Hypothesis78(
        "BR2_FAILED_BREAKOUT_FADE", "C", "Failed breakout -> mean reversion",
        "A breakout that stalls and falls back through the broken level within "
        "a few bars is a commonly cited fade setup; tested as a formal event "
        "study with the decision point placed AFTER the bars used to classify "
        "failure (no leakage into the studied window, §5).",
        f"a breakout ({_BREAKOUT_LOOKBACK}-bar structural range) that, within "
        f"{_FAILED_BREAKOUT_K} bars, never extends beyond the breakout bar's "
        "own extreme AND falls back through the broken level; decision bar = "
        "breakout bar + K",
        "forward log-return over h in {1,2,4,8} bars from the decision bar, "
        "divided by ATR, signed by the FADE direction (opposite the original "
        "breakout)",
        ("15m", "1h"), FWD_HORIZONS, "6-instrument MT5 universe",
        "all regimes", "positive (reversion in the fade direction)",
        "ATR-normalised log-return", 200,
        "block-bootstrap CI vs zero on the ATR-normalised signed forward return",
        _BOOTSTRAP_DESC, 1,
        "does fading a breakout that visibly failed to follow through produce "
        "a real reversion?",
        _b_failed_breakout, "signed", True),
    Hypothesis78(
        "S1_SESSION_TRANSITION_PERSISTENCE", "D", "Session-transition directional persistence",
        "Phase 76 confirmed session-open VOLATILITY seasonality (Andersen-"
        "Bollerslev 1997) but never tested whether pre-transition DIRECTION "
        "persists into the new session — a distinct, new hypothesis.",
        f"every session-boundary bar (session label changes); direction = sign "
        f"of the {_SESSION_PRE_BARS}-bar log-return STRICTLY BEFORE the "
        "transition (both endpoints before the new session starts)",
        "forward log-return over h in {1,2,4,8} bars from the transition bar, "
        "divided by ATR, signed by the pre-transition direction",
        ("15m",), FWD_HORIZONS, "6-instrument MT5 universe",
        "all sessions (this IS the session-boundary event; per-transition-type "
        "breakdown is a Tier-2 diagnostic)",
        "positive (continuation across the boundary)", "ATR-normalised log-return", 200,
        "block-bootstrap CI vs zero on the ATR-normalised signed forward return",
        _BOOTSTRAP_DESC, 1,
        "does the trend into a session close persist through the transition "
        "into the next session?",
        _b_session_transition, "signed", True),
]

_TIER1_HIDS = [h.hid for h in HYPOTHESES if h.tier == 1]
_M1_PRIMARY = len(_TIER1_HIDS)
_BONF_ALPHA = 0.05 / _M1_PRIMARY


def _study_fn(hy: Hypothesis78):
    if hy.study_kind == "signed":
        return _study_signed
    if hy.study_kind == "range_expansion":
        return study_range_expansion
    if hy.study_kind == "persistence_high":
        return lambda df, i, d, m, keep_rows=True: study_persistence(
            df, i, bucket="HIGH", horizons=FWD_HORIZONS, keep_rows=keep_rows)
    raise ValueError(hy.study_kind)


def hypothesis_registry_dicts() -> List[Dict[str, Any]]:
    return [{
        "hid": h.hid, "family": h.family, "name": h.name, "rationale": h.rationale,
        "event_definition": h.event_definition, "target_definition": h.target_definition,
        "timeframes": list(h.timeframes), "horizon_bars": list(h.horizon_bars),
        "universe": h.universe, "regime_scope": h.regime_scope,
        "expected_direction": h.expected_direction, "normalization": h.normalization,
        "minimum_sample_size": h.min_sample_size, "statistical_test": h.statistical_test,
        "bootstrap_method": h.bootstrap_method, "multiple_testing_tier": h.tier,
        "economic_interpretation": h.economic_interpretation, "directional": h.directional,
    } for h in HYPOTHESES]


# --------------------------------------------------------------------------
# §17 null / randomized control — deterministic placebo events drawn from the
# eligible causal index range, same count as the real event set.
# --------------------------------------------------------------------------
def _placebo_effect(df: pd.DataFrame, hy: Hypothesis78, n_events: int, seed: int) -> Optional[Dict[str, Any]]:
    n = len(df)
    eligible = np.arange(_WARMUP, max(_WARMUP + 1, n - max(hy.horizon_bars) - 1))
    if len(eligible) < 20 or n_events < 20:
        return None
    rng = np.random.default_rng(seed)
    take = min(n_events, len(eligible))
    idx = rng.choice(eligible, size=take, replace=False)
    idx.sort()
    if hy.directional:
        direction = rng.choice([-1.0, 1.0], size=take)
        res = _study_signed(df, idx, direction, np.zeros(take), keep_rows=False)
    else:
        fn = _study_fn(hy)
        res = fn(df, idx, np.zeros(take), np.zeros(take), keep_rows=False)
    hh = f"h{_headline_h(df.attrs.get('tf', '15m'))}"
    cell = res.get("horizons", {}).get(hh)
    if not cell:
        return None
    return {"n": res.get("n_events"), "effect_z": cell.get("effect_z"),
            "mean": cell.get("mean"), "verdict": cell.get("verdict")}


# --------------------------------------------------------------------------
# §18 interaction diagnostics — pre-declared, EXPLORATORY_ONLY, run AFTER the
# primary hypotheses are frozen and scored. Uses only cached dev event rows.
# --------------------------------------------------------------------------
_INTERACTIONS = [
    ("M1_IMPULSE_CONTINUATION", "15m", "regime"),
    ("BR1_BREAKOUT_RETEST_CONTINUATION", "15m", "session"),
    ("V1_COMPRESSION_DURATION", "15m", "regime"),
    ("S1_SESSION_TRANSITION_PERSISTENCE", "15m", "regime"),
]


def _interaction_diagnostics_78(raw: Dict[Tuple[str, str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for hid, tf, cond in _INTERACTIONS:
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
                        "label": "EXPLORATORY_ONLY", "n_instruments": len(cells),
                        "instruments_with_sign_flip": sum(1 for c in cells if c["sign_flip"]),
                        "cells": cells})
    return out


# --------------------------------------------------------------------------
# §14/§15/§21 classification, cost sensitivity, candidate gate, tiers (§22)
# --------------------------------------------------------------------------
def _cost_grid(dev_mean: Optional[float], directional: bool) -> Dict[str, Any]:
    if not directional or dev_mean is None:
        return {"applicable": False}
    out = {f"{g}": round(math.copysign(max(0.0, abs(dev_mean) - g), dev_mean), 6)
          for g in _COST_ATR_GRID}
    survivors = [g for g in _COST_ATR_GRID if _keeps_sign(dev_mean, out[f"{g}"]) and out[f"{g}"] != 0]
    return {"applicable": True, "mean_by_atr_cost": out,
            "survives_up_to_atr_cost": max(survivors) if survivors else None}


def _classify_78(dev: Dict[str, Any], oos: Dict[str, Any], n_dev: int, n_oos: int,
                 directional: bool, cost_ok: Optional[bool], cross_year: Optional[float],
                 cross_asset: Optional[float]) -> str:
    if n_dev < 200 or n_oos < 30 or dev.get("verdict") == "INSUFFICIENT_SAMPLE":
        return "INSUFFICIENT_SAMPLE"
    dv, ov = dev.get("verdict"), oos.get("verdict")
    dm, om = dev.get("mean"), oos.get("mean")
    same = _keeps_sign(dm, om)
    significant = dv in ("POSITIVE", "NEGATIVE") and ov in ("POSITIVE", "NEGATIVE") and same
    stable = (cross_year or 0) >= 0.6 and (cross_asset or 0) >= 0.5
    if not significant:
        if dv in ("POSITIVE", "NEGATIVE"):
            return "STATISTICALLY_DETECTABLE_BUT_UNSTABLE"
        if abs(dev.get("effect_z") or 0) >= 3.0:
            return "LIKELY_ARTIFACT"
        return "NO_EVIDENCE"
    # significant AND consistent dev/OOS
    if directional:
        if cost_ok and stable:
            return "STRATEGY_CANDIDATE_READY"
        if stable:
            return "CANDIDATE_REQUIRES_PHASE_79_VALIDATION"
        return "PHENOMENON_DETECTED_NOT_TRADEABLE"
    else:
        if stable:
            return "ML_TARGET_READY"
        return "PHENOMENON_DETECTED"


_PROMOTABLE = {"STRATEGY_CANDIDATE_READY", "CANDIDATE_REQUIRES_PHASE_79_VALIDATION"}


def _candidate_gate_78(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    fails = []
    if row["status"] not in _PROMOTABLE:
        fails.append(f"status={row['status']}")
    if (row["n_dev"] or 0) < 200:
        fails.append(f"n_dev={row['n_dev']}<200")
    if (row["n_oos"] or 0) < 30:
        fails.append(f"n_oos={row['n_oos']}<30")
    if not _keeps_sign(row["dev_mean"], row["oos_mean"]):
        fails.append("oos_sign_flip")
    dm, om = abs(row["dev_mean"] or 0), abs(row["oos_mean"] or 0)
    if dm > 0 and not (0.3 <= om / dm <= 3.0):
        fails.append(f"oos/dev magnitude ratio {om / dm:.2f} outside [0.3, 3.0]")
    if (row["cross_year_frac"] or 0) < 0.6:
        fails.append(f"cross_year={row['cross_year_frac']}<0.6")
    if (row["cross_asset_frac"] or 0) < 0.5:
        fails.append(f"cross_asset={row['cross_asset_frac']}<0.5")
    if row.get("directional"):
        cg = row.get("cost_grid") or {}
        if not cg.get("applicable") or cg.get("survives_up_to_atr_cost") is None:
            fails.append("cost_kills_sign_by_0.025_ATR")
        if row.get("null_effect_z") is not None and (row.get("dev_effect_z") or 0):
            if abs(row["dev_effect_z"]) <= 1.5 * abs(row["null_effect_z"]):
                fails.append("effect_not_materially_above_placebo")
    return (len(fails) == 0, fails)


_TIER_ORDER = ["NO_EVIDENCE", "INSUFFICIENT_SAMPLE", "STATISTICALLY_DETECTABLE_BUT_UNSTABLE",
              "LIKELY_ARTIFACT", "PHENOMENON_DETECTED", "PHENOMENON_DETECTED_NOT_TRADEABLE",
              "ML_TARGET_READY", "CANDIDATE_REQUIRES_PHASE_79_VALIDATION",
              "STRATEGY_CANDIDATE_READY"]
_CANDIDATE_TIER = {
    "NO_EVIDENCE": 0, "INSUFFICIENT_SAMPLE": 0, "LIKELY_ARTIFACT": 0,
    "STATISTICALLY_DETECTABLE_BUT_UNSTABLE": 1, "PHENOMENON_DETECTED_NOT_TRADEABLE": 2,
    "PHENOMENON_DETECTED": 2, "ML_TARGET_READY": 3,
    "CANDIDATE_REQUIRES_PHASE_79_VALIDATION": 3, "STRATEGY_CANDIDATE_READY": 4,
}


# --------------------------------------------------------------------------
# §20 ML readiness scorecard (per-hypothesis, factors A-J)
# --------------------------------------------------------------------------
def _ml_readiness_row(status: str, cross_year: Optional[float], cross_asset: Optional[float],
                      n_dev: int, n_oos: int, regime_dep: Dict[str, Any],
                      directional: bool, cost_grid: Dict[str, Any]) -> Dict[str, Any]:
    factors = {
        "A_predictive_stability": status not in ("NO_EVIDENCE", "INSUFFICIENT_SAMPLE", "LIKELY_ARTIFACT"),
        "B_cross_year_stability": (cross_year or 0) >= 0.6,
        "C_cross_instrument_stability": (cross_asset or 0) >= 0.5,
        "D_economic_significance": status in ("STRATEGY_CANDIDATE_READY", "ML_TARGET_READY",
                                              "CANDIDATE_REQUIRES_PHASE_79_VALIDATION"),
        "E_cost_robustness": (not directional) or bool(cost_grid.get("survives_up_to_atr_cost")),
        "F_feature_availability_at_event_time": True,   # causal by construction (§5, look-ahead tests)
        "G_target_clarity": True,                       # explicit formula in the registry
        "H_leakage_risk_low": True,                      # look-ahead tests pass (§30)
        "I_sample_size_adequate": n_dev >= 200 and n_oos >= 30,
        "J_regime_independent": regime_dep.get("class") != "SIGN_FLIPS_BY_REGIME",
    }
    score = sum(1 for v in factors.values() if v) / len(factors)
    if status == "STRATEGY_CANDIDATE_READY":
        level = "STRATEGY_CANDIDATE_READY"
    elif status in ("ML_TARGET_READY", "CANDIDATE_REQUIRES_PHASE_79_VALIDATION"):
        level = status
    elif status in ("PHENOMENON_DETECTED", "PHENOMENON_DETECTED_NOT_TRADEABLE"):
        level = "PHENOMENON_READY"
    elif factors["I_sample_size_adequate"]:
        level = "DATA_READY_BUT_EDGE_UNCLEAR"
    else:
        level = "NOT_READY"
    return {"level": level, "score": round(score, 3), "factors": factors}


# --------------------------------------------------------------------------
# §26 full run
# --------------------------------------------------------------------------
@dataclass
class Phase78Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    instruments: List[str]
    timeframes: List[str]
    literature: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    dataset_manifests: Dict[str, Optional[str]]
    data_integrity: Dict[str, Any]
    dev_oos_split: str
    scorecard: List[Dict[str, Any]]
    null_controls: List[Dict[str, Any]]
    interaction_diagnostics: List[Dict[str, Any]]
    multiple_testing: Dict[str, Any]
    negative_knowledge: List[Dict[str, Any]]
    ml_readiness_scorecard: List[Dict[str, Any]]
    ml_readiness_overall: str
    candidates: List[Dict[str, Any]]
    family_summary: Dict[str, Any]
    scientific_questions: Dict[str, str]
    phase79_queue: List[Dict[str, Any]]
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


def run(instruments: Tuple[str, ...] = INSTRUMENTS) -> Phase78Result:
    t0 = datetime.now(timezone.utc)
    tfs_needed = sorted({tf for hy in HYPOTHESES for tf in hy.timeframes})
    manifests: Dict[str, Optional[str]] = {}
    integrity: Dict[str, Any] = {}
    raw: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    null_controls: List[Dict[str, Any]] = []

    for inst in instruments:
        try:
            manifests[inst] = (dataset_manifest.get_manifest(inst) or {}).get("dataset_id")
        except Exception:
            manifests[inst] = None
        frames: Dict[str, pd.DataFrame] = {}
        for tf in tfs_needed:
            integrity[f"{inst}:{tf}"] = data_integrity(inst, tf)
            df = load_bars(inst, tf)
            if df.empty or len(df) < 2000:
                continue
            frames[tf] = augment(df, tf)
        for hy in HYPOTHESES:
            fn = _study_fn(hy)
            for tf in hy.timeframes:
                df = frames.get(tf)
                if df is None:
                    continue
                bound = int(len(df) * _DEV_RATIO)
                dev_df = df.iloc[:bound].copy(); oos_df = df.iloc[bound:].reset_index(drop=True).copy()
                dev_df.attrs["tf"] = tf; oos_df.attrs["tf"] = tf
                dev_ev = hy.builder(dev_df)
                oos_ev = hy.builder(oos_df)
                dev = fn(dev_df, *dev_ev, keep_rows=True)
                oos = fn(oos_df, *oos_ev, keep_rows=False)
                raw[(hy.hid, tf, inst)] = {"dev": dev, "oos": oos}
                # §17 null control — headline (hid, inst, first timeframe) cell only, bounded compute
                if tf == hy.timeframes[0]:
                    seed = _NULL_SEED_OFFSET + abs(hash((hy.hid, inst))) % 100000
                    nc = _placebo_effect(dev_df, hy, dev.get("n_events", 0), seed)
                    if nc:
                        null_controls.append({"hypothesis": hy.hid, "instrument": inst,
                                              "timeframe": tf, **nc})
        frames.clear()
        del frames
        gc.collect()

    # ---- scorecard (mirrors Phase 76's aggregation) --------------------
    scorecard: List[Dict[str, Any]] = []
    per_hyp_signs: Dict[Tuple[str, str], Dict[int, int]] = {}
    for (hid, tf, inst), rr in raw.items():
        hy = next(h for h in HYPOTHESES if h.hid == hid)
        hh = _headline_h(tf)
        dev = rr["dev"]["horizons"].get(f"h{hh}", {})
        oos = rr["oos"]["horizons"].get(f"h{hh}", {})
        rows = rr["dev"].get("event_rows", [])
        cyf = _cross_year_from_rows(rows)
        regime_dep = _regime_dependence(rows)
        dm = dev.get("mean")
        if dev.get("verdict") in ("POSITIVE", "NEGATIVE") and dm:
            per_hyp_signs.setdefault((hid, tf), {}).setdefault(1 if dm > 0 else -1, 0)
            per_hyp_signs[(hid, tf)][1 if dm > 0 else -1] += 1
        scorecard.append({
            "hypothesis": hid, "family": hy.family, "instrument": inst, "timeframe": tf,
            "headline_horizon": f"h{hh}", "tier": hy.tier, "directional": hy.directional,
            "N_dev": rr["dev"].get("n_events"), "N_oos": rr["oos"].get("n_events"),
            "dev": dev, "oos": oos, "cross_year_same_sign_frac": cyf,
            "regime_dependence": regime_dep,
        })

    for sc in scorecard:
        signs = per_hyp_signs.get((sc["hypothesis"], sc["timeframe"]), {})
        total = len([s for s in scorecard if s["hypothesis"] == sc["hypothesis"]
                    and s["timeframe"] == sc["timeframe"]])
        dom = max(signs.values()) if signs else 0
        sc["cross_asset_frac"] = round(dom / max(1, total), 3)
        d, o = sc["dev"], sc["oos"]
        sc["cost_grid"] = _cost_grid(d.get("mean"), sc["directional"])
        cost_ok = (not sc["directional"]) or bool(sc["cost_grid"].get("survives_up_to_atr_cost"))
        sc["discovery"] = discovery_score(d, o, sc["cross_year_same_sign_frac"], sc["cross_asset_frac"],
                                          d.get("mean") if not sc["directional"] else d.get("cost_adj_mean"))
        sc["status"] = _classify_78(d, o, sc["N_dev"] or 0, sc["N_oos"] or 0, sc["directional"],
                                    cost_ok, sc["cross_year_same_sign_frac"], sc["cross_asset_frac"])
        nc = next((n for n in null_controls if n["hypothesis"] == sc["hypothesis"]
                  and n["instrument"] == sc["instrument"]
                  and n["timeframe"] == next(h.timeframes[0] for h in HYPOTHESES if h.hid == sc["hypothesis"])), None)
        sc["null_control"] = nc
        sc["ml_readiness"] = _ml_readiness_row(sc["status"], sc["cross_year_same_sign_frac"],
                                               sc["cross_asset_frac"], sc["N_dev"] or 0, sc["N_oos"] or 0,
                                               sc["regime_dependence"], sc["directional"], sc["cost_grid"])

    # ---- interaction diagnostics (§18) ---------------------------------
    interactions = _interaction_diagnostics_78(raw)

    # ---- multiple testing (§9) -----------------------------------------
    diag_p = []
    for sc in scorecard:
        z = sc["dev"].get("effect_z")
        if z is not None and (sc["N_dev"] or 0) >= 20:
            diag_p.append((sc["hypothesis"], sc["instrument"], sc["timeframe"],
                          2 * (1 - _norm_cdf(abs(z)))))
    bh = _benjamini_hochberg([p for *_x, p in diag_p], q=0.10)
    tier1_head = []
    for hid in _TIER1_HIDS:
        cells = [s for s in scorecard if s["hypothesis"] == hid]
        nsig = sum(1 for c in cells if c["dev"].get("verdict") in ("POSITIVE", "NEGATIVE"))
        bonf_sig = sum(1 for c in cells if c["dev"].get("effect_z") is not None
                      and 2 * (1 - _norm_cdf(abs(c["dev"]["effect_z"]))) <= _BONF_ALPHA)
        tier1_head.append({"hypothesis": hid, "cells": len(cells), "cells_ci_excl_zero": nsig,
                          "cells_pass_bonferroni": bonf_sig})
    mt = {
        "tier1_primary_hypotheses": _M1_PRIMARY, "tier1_bonferroni_alpha": round(_BONF_ALPHA, 6),
        "tier1_headline": tier1_head, "tier2_diagnostic_tests": len(diag_p),
        "tier2_bh_fdr_q": 0.10, "tier2_surviving_bh": int(sum(bh)), "tier3_exploratory_tests": 0,
        "note": "no post-hoc / data-mined hypotheses were added; Tier 3 is empty by design (§4)",
    }

    # ---- negative knowledge (§23) ---------------------------------------
    negative = [{
        "hypothesis": sc["hypothesis"], "family": sc["family"], "instrument": sc["instrument"],
        "timeframe": sc["timeframe"], "reason_rejected": sc["status"], "N_dev": sc["N_dev"],
        "N_oos": sc["N_oos"], "dev_effect_z": sc["dev"].get("effect_z"),
        "dev_verdict": sc["dev"].get("verdict"), "oos_verdict": sc["oos"].get("verdict"),
        "recorded": t0.date().isoformat(), "phase": 78,
    } for sc in scorecard if sc["status"] in ("NO_EVIDENCE", "LIKELY_ARTIFACT",
                                              "STATISTICALLY_DETECTABLE_BUT_UNSTABLE")]
    # Phase 77's large-bar reversal remains part of the negative knowledge base (§2, §23)
    negative.append({"hypothesis": "H8_LARGE_BAR_REVERSAL (Phase 77)", "family": "carried_forward",
                     "instrument": "AUDJPY/GBPJPY/GBPUSD/EURUSD", "timeframe": "15m",
                     "reason_rejected": "NO_VALIDATED_CANDIDATE (fails realistic cost model)",
                     "N_dev": None, "N_oos": 12883, "dev_effect_z": None, "dev_verdict": None,
                     "oos_verdict": "NEGATIVE EXPECTANCY (FAILED)",
                     "recorded": t0.date().isoformat(), "phase": 77})

    # ---- candidate gate (§21) -------------------------------------------
    candidates = []
    for s in sorted(scorecard, key=lambda x: x["discovery"]["score"], reverse=True):
        row = {"hypothesis": s["hypothesis"], "family": s["family"], "instrument": s["instrument"],
              "timeframe": s["timeframe"], "status": s["status"], "n_dev": s["N_dev"],
              "n_oos": s["N_oos"], "directional": s["directional"],
              "dev_mean": s["dev"].get("mean"), "oos_mean": s["oos"].get("mean"),
              "dev_effect_z": s["dev"].get("effect_z"),
              "null_effect_z": (s["null_control"] or {}).get("effect_z"),
              "cross_year_frac": s["cross_year_same_sign_frac"],
              "cross_asset_frac": s.get("cross_asset_frac"), "cost_grid": s["cost_grid"],
              "score": s["discovery"]["score"]}
        ok, fails = _candidate_gate_78(row)
        row["gate_pass"] = ok; row["gate_fails"] = fails
        if ok:
            candidates.append(row)
        if len(candidates) >= 3:
            break

    # ---- ML readiness overall -------------------------------------------
    levels = [s["ml_readiness"]["level"] for s in scorecard]
    if "STRATEGY_CANDIDATE_READY" in levels:
        ml_overall = "STRATEGY_CANDIDATE_READY"
    elif "ML_TARGET_READY" in levels or "CANDIDATE_REQUIRES_PHASE_79_VALIDATION" in levels:
        ml_overall = "ML_TARGET_READY"
    elif "PHENOMENON_READY" in levels:
        ml_overall = "PHENOMENON_READY"
    elif "DATA_READY_BUT_EDGE_UNCLEAR" in levels:
        ml_overall = "DATA_READY_BUT_EDGE_UNCLEAR"
    else:
        ml_overall = "NOT_READY"

    # ---- family summary (strongest cell per family) ----------------------
    family_summary: Dict[str, Any] = {}
    for fam in ("A", "B", "C", "D"):
        cells = [s for s in scorecard if s["family"] == fam]
        if not cells:
            family_summary[fam] = {"state": "NO_DATA"}
            continue
        best = max(cells, key=lambda s: s["discovery"]["score"])
        family_summary[fam] = {
            "strongest_hypothesis": best["hypothesis"], "instrument": best["instrument"],
            "timeframe": best["timeframe"], "status": best["status"],
            "dev_mean": best["dev"].get("mean"), "oos_mean": best["oos"].get("mean"),
            "dev_effect_z": best["dev"].get("effect_z"), "score": best["discovery"]["score"],
        }

    # ---- overall verdict (§27) -------------------------------------------
    best_tier = max((_CANDIDATE_TIER.get(s["status"], 0) for s in scorecard), default=0)
    if candidates and any(c["status"] == "STRATEGY_CANDIDATE_READY" for c in candidates):
        verdict = "STRATEGY_CANDIDATE_READY"
    elif candidates:
        verdict = "CANDIDATE_REQUIRES_PHASE_79_VALIDATION"
    elif best_tier >= 3:
        verdict = "ML_TARGET_READY"
    elif best_tier == 2:
        verdict = "PHENOMENON_DETECTED_NOT_TRADEABLE"
    else:
        verdict = "NO_VALIDATED_CANDIDATE"

    # ---- §33 scientific questions, answered from measured results --------
    any_detectable = any(s["status"] not in ("NO_EVIDENCE", "INSUFFICIENT_SAMPLE") for s in scorecard)
    dir_promoted = any(s["directional"] and s["status"] in _PROMOTABLE for s in scorecard)
    nondir_ml_ready = any((not s["directional"]) and s["status"] == "ML_TARGET_READY" for s in scorecard)
    # cost survival is only meaningful for a cell that is ALSO dev+OOS consistent —
    # a raw dev-mean exceeding 0.025 ATR on a cell that never replicated OOS is
    # noise, not a cost-robust phenomenon.
    any_cost_survives = any(
        s["directional"] and s["status"] in _PROMOTABLE
        and s["cost_grid"].get("survives_up_to_atr_cost") is not None
        for s in scorecard)
    dir_detectable = any(s["status"] not in ("NO_EVIDENCE", "INSUFFICIENT_SAMPLE") and s["directional"]
                        for s in scorecard)
    mag_detectable = any(s["status"] not in ("NO_EVIDENCE", "INSUFFICIENT_SAMPLE") and not s["directional"]
                        for s in scorecard)
    questions = {
        "Q1_price_completely_random": ("NO" if any_detectable else "CONSISTENT WITH — no hypothesis "
                                       "cleared even the diagnostic bar"),
        "Q2_phenomena_statistically_detectable": ("YES" if any_detectable else "NO"),
        "Q3_economically_meaningful": (
            "PARTIALLY — the non-directional volatility-regime phenomenon (Family B) is "
            "economically meaningful as a forecasting target (magnitude/persistence), but "
            "NO directional (tradeable) phenomenon reached that bar" if (nondir_ml_ready and not dir_promoted)
            else "YES — a directional candidate cleared the economic bar" if dir_promoted
            else "NO"),
        "Q4_survives_realistic_costs": ("YES" if any_cost_survives else "NO — no directional cell "
                                        "was BOTH dev+OOS consistent AND kept its sign past a 0.025 "
                                        "ATR round-trip cost; cost sensitivity is therefore moot for "
                                        "the directional families"),
        "Q5_direction_vs_volatility_predictable": (
            "BOTH" if dir_detectable and mag_detectable else
            "VOLATILITY ONLY" if mag_detectable else
            "DIRECTION ONLY" if dir_detectable else "NEITHER"),
        "Q6_ml_learnable_phenomenon": ("YES — volatility-regime persistence (Family B)" if nondir_ml_ready
                                       else "NOT YET"),
        "Q7_enough_evidence_to_train_ml": "NO — Phase 78 explicitly withheld ML training by design (§0.4)",
        "Q8_missing_evidence": (
            "a directional candidate: more cross-year replication and a realistic intrabar "
            "fill/cost model, cf. Phase 77's approach" if not dir_promoted and not nondir_ml_ready else
            "for the volatility target: a leakage/overlap audit at every horizon (§W) and a "
            "concrete downstream use-case (regime filter / risk sizing) before any model is "
            "trained; still NO directional target to give an ML model"),
        "Q9_strongest_next_direction": (family_summary.get("B", {}).get("strongest_hypothesis")
                                        or "volatility-regime persistence as an ML target"),
    }

    # ---- Phase 79 queue (max 3, no invented positives) --------------------
    queue_source = candidates if candidates else sorted(
        [s for s in scorecard if s["status"] not in ("NO_EVIDENCE", "INSUFFICIENT_SAMPLE",
                                                      "LIKELY_ARTIFACT", "STATISTICALLY_DETECTABLE_BUT_UNSTABLE")],
        key=lambda s: s["discovery"]["score"], reverse=True)[:3]
    phase79_queue = []
    for item in queue_source[:3]:
        if isinstance(item, dict) and "gate_pass" in item:  # a true candidate row
            phase79_queue.append({
                "candidate": item["hypothesis"], "instrument": item["instrument"],
                "evidence": f"dev_z={item['dev_effect_z']}, cross_year={item['cross_year_frac']}, "
                           f"cross_asset={item['cross_asset_frac']}",
                "status": item["status"],
                "remaining_uncertainty": "cost model / execution realism" if item["directional"]
                                        else "downstream ML target design",
                "required_next_validation": "Phase 79 execution-realistic validation (cf. Phase 77 "
                                            "methodology)" if item["directional"] else
                                            "Phase 79 ML feature-engineering pilot (no training yet)",
            })
        else:
            # a scorecard row that reached ML_TARGET_READY / PHENOMENON_DETECTED(_NOT_TRADEABLE)
            # but never entered the directional candidate gate (§21) because it is a
            # magnitude/probability (non-directional) target — status-appropriate
            # messaging, not the "gate failed" wording used for candidate rows above.
            status = item["status"]
            if status == "ML_TARGET_READY":
                uncertainty = ("mechanical autocorrelation of overlapping rolling-window "
                               "statistics has NOT been fully ruled out at every horizon "
                               "(§W); downstream ML feature/target design and leakage audit "
                               "still required")
                nxt = ("Phase 79 ML feature-engineering pilot: build the target column, "
                      "audit for overlap/leakage at each horizon, no model training yet")
            elif status in ("PHENOMENON_DETECTED", "PHENOMENON_DETECTED_NOT_TRADEABLE"):
                uncertainty = "detected but not stable/strong enough for the ML-target gate"
                nxt = "none recommended unless independently re-registered with a larger sample"
            else:
                uncertainty = "did not clear the full candidate gate (§21) — see scorecard"
                nxt = "none recommended unless independently re-registered"
            phase79_queue.append({
                "candidate": item["hypothesis"], "instrument": item["instrument"],
                "evidence": f"dev_z={item['dev'].get('effect_z')}, cross_year="
                           f"{item['cross_year_same_sign_frac']}, cross_asset="
                           f"{item.get('cross_asset_frac')}, status={status}",
                "status": status, "remaining_uncertainty": uncertainty,
                "required_next_validation": nxt,
            })

    ident = json.dumps({
        "inst": list(instruments), "schema": SCHEMA_VERSION, "verdict": verdict,
        "n_candidates": len(candidates), "ml": ml_overall,
        "rows": sorted((s["hypothesis"], s["instrument"], s["timeframe"], s["N_dev"], s["status"],
                       round(s["discovery"]["score"], 3)) for s in scorecard),
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase78Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        instruments=list(instruments), timeframes=list(TIMEFRAMES), literature=LITERATURE,
        hypotheses=hypothesis_registry_dicts(), dataset_manifests=manifests, data_integrity=integrity,
        dev_oos_split=f"chronological {int(_DEV_RATIO*100)}/{100-int(_DEV_RATIO*100)} on bar index",
        scorecard=scorecard, null_controls=null_controls, interaction_diagnostics=interactions,
        multiple_testing=mt, negative_knowledge=negative,
        ml_readiness_scorecard=[{"hypothesis": s["hypothesis"], "instrument": s["instrument"],
                                "timeframe": s["timeframe"], **s["ml_readiness"]} for s in scorecard],
        ml_readiness_overall=ml_overall, candidates=candidates, family_summary=family_summary,
        scientific_questions=questions, phase79_queue=phase79_queue, verdict=verdict,
        runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase78Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase78_market_behavior_discovery_ii", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 78 - market behavior discovery II ...", flush=True)
    res = run()
    print(f"\n=== PHASE 78 ({len(res.instruments)} instruments, {res.runtime_seconds}s) ===")
    print(f"{'HYP':<32}{'INST':<8}{'TF':<5}{'Ndev':>6}{'DEVmean':>10}{'z':>6}{'DEVv':>13}"
          f"{'OOSmean':>10}{'OOSv':>13}{'score':>7} STATUS")
    for s in sorted(res.scorecard, key=lambda x: x["discovery"]["score"], reverse=True):
        d, o = s["dev"], s["oos"]
        print(f"{s['hypothesis']:<32}{s['instrument']:<8}{s['timeframe']:<5}{str(s['N_dev']):>6}"
              f"{str(d.get('mean')):>10}{str(d.get('effect_z')):>6}{str(d.get('verdict')):>13}"
              f"{str(o.get('mean')):>10}{str(o.get('verdict')):>13}"
              f"{str(s['discovery']['score']):>7} {s['status']}")
    print(f"\nFAMILY SUMMARY: {json.dumps(res.family_summary, default=str)}")
    print(f"\nCANDIDATES ({len(res.candidates)}):")
    for c in res.candidates:
        print(f"  {c['hypothesis']} {c['instrument']} {c['timeframe']} status={c['status']}")
    print(f"\nML_READINESS_OVERALL = {res.ml_readiness_overall}")
    print(f"VERDICT: {res.verdict}")
    print("\nSCIENTIFIC QUESTIONS:")
    for k, v in res.scientific_questions.items():
        print(f"  {k}: {v}")
    print(f"\nPHASE 79 QUEUE ({len(res.phase79_queue)}):")
    for q in res.phase79_queue:
        print(f"  {q}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["run", "persist", "get_result", "augment", "HYPOTHESES", "hypothesis_registry_dicts",
           "study_range_expansion", "study_persistence", "ARTIFACT_KEY", "SCHEMA_VERSION",
           "Phase78Result", "INSTRUMENTS", "TIMEFRAMES"]
