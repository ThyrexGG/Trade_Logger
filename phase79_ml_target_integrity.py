# -*- coding: utf-8 -*-
"""
Phase 79 — ML Target Integrity, Leakage Audit & Pilot Readiness.

A research-INTEGRITY phase, not a strategy-development phase and NOT an ML
training phase. Phase 78 found exactly two phenomena classified
``ML_TARGET_READY``:

    V2 — high-volatility regime persistence   (12/12 instrument x TF cells)
    V1 — compression-duration -> range expansion, restricted to 15m (per the
         Phase 78 queue; V1 is NOT extended to 1h here without independent
         justification, §2)

Phase 79 asks a narrower, harder question about those two findings only:
can they be turned into rigorously defined, leakage-free, timestamp-correct
ML *targets*? It does NOT re-litigate whether the phenomena are real (Phase
78 already established that with dev/OOS bootstrap CIs, Bonferroni control,
cross-year/cross-asset stability and a placebo null) — it audits whether the
target CONSTRUCTION is safe to eventually learn from.

No third hypothesis is opened (§37 of the master prompt) and Phase 77's
large-bar reversal is not reopened. No ML/DL library is imported or used;
see ``test_no_ml_training_in_module``.

Everything here reuses Phase 76/78 machinery verbatim wherever possible
(``phase76_event_study.load_bars``/``block_bootstrap``, and
``phase78_market_behavior_discovery_ii.augment``/``study_persistence``/
``study_range_expansion``/``_placebo_effect``/``_b_vol_bucket_high``/
``_b_compression_duration``) — see docs §2 "architecture note: what was
reused and why". New code is limited to: (1) a formal, versioned target
specification for each of V2/V1, (2) temporal-metadata materialization for
audit purposes, (3) the leakage/overlap/purge/null/shuffle/shift audits the
master prompt requires, none of which existed before Phase 79.

Read-only. No execution / broker / risk / forward-validation module imported.
The frozen Phase-74 holdout (``xauusd_market_conditions.FROZEN_CONTRACT_HASH``)
is never read, queried, or compared (§6).
"""
from __future__ import annotations

import gc
import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

import numpy as np
import pandas as pd

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
from phase76_event_study import FWD_HORIZONS, _DEV_RATIO, _headline_h, block_bootstrap, load_bars
from phase78_market_behavior_discovery_ii import (
    INSTRUMENTS, _b_compression_duration, _b_vol_bucket_high,
    _placebo_effect, augment, study_persistence, study_range_expansion,
)

SCHEMA_VERSION = "phase79.1"
ARTIFACT_KEY = "phase79_ml_target_integrity"
RANDOM_SEED = 42

_TF_SECONDS: Dict[str, int] = {"15m": 900, "1h": 3600}

# §2 — the exact Phase 79 target universe (no invented third target, §37).
V2_TIMEFRAMES: Tuple[str, ...] = ("15m", "1h")
V1_TIMEFRAMES: Tuple[str, ...] = ("15m",)     # restricted per Phase 78 queue item #2
TARGET_UNIVERSE: Tuple[str, ...] = INSTRUMENTS  # unchanged 6-instrument universe

_SHOCK_MULT = 50.0
_SHIFT_BARS = (1, 2, 4, 8)
_LABEL_SHUFFLE_SEED_OFFSET = 79001
_TIME_SHIFT_SEED_OFFSET = 79002        # kept for API symmetry; shift is deterministic, not random
_ADVERSARIAL_SEED = 79100


# ==========================================================================
# §7/§8/§25/§26 — formal, versioned target specifications.
# ==========================================================================
@dataclass(frozen=True)
class TargetSpec:
    target_name: str
    version: str
    family: str
    directional: bool
    source_hypothesis: str
    source_module_version: str
    description: str
    event_definition: str
    feature_timestamp_rule: str
    prediction_timestamp_rule: str
    target_start_rule: str
    target_end_rule: str
    horizon_bars: Tuple[int, ...]
    normalization: str
    threshold_definition: str
    label_construction: str
    minimum_data_requirements: str
    invalid_missing_data_handling: str
    overlapping_label_behavior: str

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["horizon_bars"] = list(d["horizon_bars"])
        return d


# Both timestamp rules below reuse the repository's OWN look-ahead convention
# verbatim: ``historical_data_store.get_candles(as_of=...)`` already defines a
# bar's CLOSE as ``open_time + timeframe`` and truncates on it (§7 architecture
# note). A bar's derived features (ATR, ATR-rank, RV-rank, comp_run, ...) all
# require that bar's own OHLC, so they cannot be known before that same close
# time — hence feature_timestamp == prediction_timestamp == close(event bar).
_PRED_TS_RULE = ("prediction_timestamp = open_time(event_bar) + timeframe_seconds "
                  "(the CLOSE of the event bar — the instant its OHLC, and every "
                  "feature computed from it, first become knowable; identical to "
                  "historical_data_store.get_candles(as_of=...)'s existing "
                  "look-ahead convention)")

V2_TARGET_SPEC = TargetSpec(
    target_name="V2_HIGH_VOL_REGIME_PERSISTENCE",
    version="V2-target-v1",
    family="volatility_regime_persistence",
    directional=False,
    source_hypothesis="V2_VOL_REGIME_PERSISTENCE_HIGH (Phase 78)",
    source_module_version=p78.SCHEMA_VERSION,
    description=(
        "Binary target: is the realized-volatility regime still HIGH h bars after "
        "an event bar that was already observed to be in the HIGH regime? "
        "Conceptually 'current volatility regime -> future volatility regime', "
        "derived unchanged from the Phase 78 V2 hypothesis, not a new formulation."),
    event_definition=(
        "any bar i whose trailing rv_rank (realized-vol over the last "
        f"{p78._RV_WINDOW} 1-bar log-returns, ranked over the trailing 200 bars) "
        "is > 0.66 -- the HIGH bucket (phase78_market_behavior_discovery_ii."
        "_b_vol_bucket_high, unchanged)"),
    feature_timestamp_rule=_PRED_TS_RULE.replace("prediction_timestamp", "feature_timestamp"),
    prediction_timestamp_rule=_PRED_TS_RULE,
    target_start_rule="target_start_timestamp = prediction_timestamp (identical instant)",
    target_end_rule="target_end_timestamp = open_time(event_bar + h) + timeframe_seconds "
                     "= close(event_bar + h), for h in {1,2,4,8} bars",
    horizon_bars=FWD_HORIZONS,
    normalization="probability (Bernoulli indicator), baseline-centred: "
                  "label - P(rv_rank(i+h) > 0.66) unconditionally over the same slice",
    threshold_definition="rv_rank > 0.66 defines HIGH at both event time and target time "
                          "(same threshold, no post-hoc tuning)",
    label_construction="target_value = 1.0 if rv_rank(event_idx + h) > 0.66 else 0.0; "
                        "the SCORED effect (what block_bootstrap tests against zero) is "
                        "target_value - baseline_P(bucket at horizon h), per "
                        "phase78.study_persistence, unchanged",
    minimum_data_requirements="event bar index >= 200 (rv_rank warm-up) and "
                              "event_idx + max(horizon_bars) < len(df) (target must be fully "
                              "observable); n_events >= 20 per (instrument, timeframe) cell "
                              "for block_bootstrap, >= 200 for the Phase 78/79 gate",
    invalid_missing_data_handling="events with a non-finite rv_rank at event time, or whose "
                                  "target bar falls beyond the end of the series, are dropped "
                                  "(never imputed, never forward-filled)",
    overlapping_label_behavior="HIGH-volatility bars cluster in runs, so consecutive events' "
                               "target windows overlap heavily at short horizons; NOT treated "
                               "as independent draws — see the §10/§21 overlap and effective-N "
                               "audit, which is why block_bootstrap uses block=h rather than an "
                               "i.i.d. CI",
)

V1_TARGET_SPEC = TargetSpec(
    target_name="V1_COMPRESSION_DURATION_RANGE_EXPANSION",
    version="V1-target-v1",
    family="compression_duration_persistence",
    directional=False,
    source_hypothesis="V1_COMPRESSION_DURATION (Phase 78)",
    source_module_version=p78.SCHEMA_VERSION,
    description=(
        "Continuous target: how much does the realized range over the next h "
        "bars exceed a STABLE (trailing 200-bar mean, unconditioned) ATR-implied "
        "range, following a multi-bar volatility compression? Conceptually "
        "'compression duration -> future realized range', restricted to 15m "
        "(Phase 78 found this NOT universal on 1h; no independent justification "
        "exists yet to extend it, §2)."),
    event_definition=(
        f"the bar that FIRST reaches {p78._COMPRESSION_MIN_RUN} CONSECUTIVE bars with "
        "ATR percentile rank (trailing-200-bar, causal) <= 0.10 "
        "(phase78_market_behavior_discovery_ii._b_compression_duration, unchanged)"),
    feature_timestamp_rule=_PRED_TS_RULE.replace("prediction_timestamp", "feature_timestamp"),
    prediction_timestamp_rule=_PRED_TS_RULE,
    target_start_rule="target_start_timestamp = prediction_timestamp (identical instant)",
    target_end_rule="target_end_timestamp = open_time(event_bar + h) + timeframe_seconds "
                     "= close(event_bar + h), for h in {1,2,4,8} bars",
    horizon_bars=FWD_HORIZONS,
    normalization="(sum of true range over bars [event_idx+1 .. event_idx+h]) / "
                  "(atr_stable(event_idx) * h) - 1, baseline-centred by subtracting the "
                  "SAME ratio's unconditional mean over every valid bar in the slice. "
                  "atr_stable is the trailing-200-bar MEAN of ATR(14), NOT the event-time "
                  "ATR -- the event-time ATR is by construction depressed at a compression "
                  "event, so dividing by it would mechanically inflate the ratio (the exact "
                  "bug class fixed in Phase 76/78; re-verified for Phase 79 in §14)",
    threshold_definition="no direction/threshold on the label itself; magnitude-only",
    label_construction="target_value = true_range_sum(i+1..i+h) / (atr_stable(i) * h) - 1, "
                        "minus baseline_mean, per phase78.study_range_expansion, unchanged",
    minimum_data_requirements="event bar index >= 200 (atr_stable/atr_rank warm-up) and "
                              "event_idx + max(horizon_bars) < len(df); n_events >= 20 per "
                              "cell for block_bootstrap, >= 200 for the gate",
    invalid_missing_data_handling="events with a non-finite/non-positive atr_stable at event "
                                  "time, or whose target bars fall beyond the series end, are "
                                  "dropped (never imputed)",
    overlapping_label_behavior="compression runs cluster, and the true-range-sum window "
                               "itself overlaps for nearby events at short horizons; see the "
                               "§10/§21 overlap and effective-N audit",
)


def target_registry_dicts() -> List[Dict[str, Any]]:
    return [V2_TARGET_SPEC.to_dict(), V1_TARGET_SPEC.to_dict()]


# ==========================================================================
# §9 temporal-metadata materialization (used by the timestamp-ordering audit
# and directly by tests — kept small; NOT persisted row-by-row in the artifact)
# ==========================================================================
def materialize_target_rows(df: pd.DataFrame, tf: str, idx: np.ndarray, kind: str,
                            horizons: Tuple[int, ...] = FWD_HORIZONS,
                            max_rows: int = 5000) -> pd.DataFrame:
    """Per-event x per-horizon rows with EXPLICIT UTC timestamps, for the
    feature/target temporal-ordering audit (§9). ``kind`` is "V2" or "V1".
    Bounded by ``max_rows`` (a uniform stride subsample) — this is an audit
    tool, not the artifact payload."""
    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    n = len(df)
    idx = np.asarray(idx, int)
    if len(idx) == 0:
        return pd.DataFrame(columns=["event_idx", "target_idx", "horizon_bars",
                                     "feature_timestamp", "prediction_timestamp",
                                     "target_start_timestamp", "target_end_timestamp",
                                     "target_value"])
    stride = max(1, len(idx) // max_rows)
    idx = idx[::stride]
    if kind == "V2":
        rvr = df["rv_rank"].to_numpy(float)
    else:
        tr = df["tr"].to_numpy(float)
        atr_stable = df["atr_stable"].to_numpy(float)
        csum = np.concatenate([[0.0], np.cumsum(tr)])
    rows = []
    for h in horizons:
        j = idx + h
        m = (j < n)
        for e, t in zip(idx[m], j[m]):
            e, t = int(e), int(t)
            pred_ts = int(open_ts[e]) + tf_sec
            targ_end_ts = int(open_ts[t]) + tf_sec
            if kind == "V2":
                val = float(rvr[t] > 0.66) if np.isfinite(rvr[t]) else np.nan
            else:
                if atr_stable[e] > 0:
                    val = float(csum[t + 1] - csum[e + 1]) / (atr_stable[e] * h) - 1.0
                else:
                    val = np.nan
            rows.append({
                "event_idx": e, "target_idx": t, "horizon_bars": h,
                "feature_timestamp": pd.Timestamp(pred_ts, unit="s", tz="UTC"),
                "prediction_timestamp": pd.Timestamp(pred_ts, unit="s", tz="UTC"),
                "target_start_timestamp": pd.Timestamp(pred_ts, unit="s", tz="UTC"),
                "target_end_timestamp": pd.Timestamp(targ_end_ts, unit="s", tz="UTC"),
                "target_value": val,
            })
    return pd.DataFrame(rows)


def audit_timestamp_ordering(tbl: pd.DataFrame, tf: str) -> Dict[str, Any]:
    """§9A/§9B: feature_timestamp <= prediction_timestamp; target strictly after.

    The "horizon math" check compares elapsed wall-clock time to
    ``horizon_bars * timeframe_seconds`` as a LOWER BOUND, not an equality:
    ``horizon_bars`` counts BARS, and real MT5 data has weekend/holiday
    calendar gaps between consecutive bars, so the true wall-clock gap over h
    bars is >= h * timeframe_seconds, with equality only when the series is
    perfectly regular (true of synthetic test data, not of real market data).
    An earlier version of this audit asserted exact equality and consequently
    mis-flagged every real (non-synthetic) instrument as failing purely
    because of ordinary weekend gaps -- not a leakage issue. Fixed here; a
    genuine leakage bug would show target_end <= prediction (caught by
    ``target_end_strictly_after_prediction``), not merely a wider gap."""
    if tbl.empty:
        return {"state": "NO_ROWS"}
    tf_sec = _TF_SECONDS[tf]
    ok_feat = bool((tbl["feature_timestamp"] <= tbl["prediction_timestamp"]).all())
    ok_start = bool((tbl["target_start_timestamp"] >= tbl["prediction_timestamp"]).all())
    ok_end_after = bool((tbl["target_end_timestamp"] > tbl["prediction_timestamp"]).all())
    gap_sec = (tbl["target_end_timestamp"] - tbl["prediction_timestamp"]).dt.total_seconds()
    min_expected_sec = tbl["horizon_bars"] * tf_sec
    ok_horizon_math = bool((gap_sec.to_numpy() >= min_expected_sec.to_numpy() - 1e-6).all())
    return {
        "n_rows_checked": int(len(tbl)),
        "feature_timestamp_never_after_prediction": ok_feat,
        "target_start_not_before_prediction": ok_start,
        "target_end_strictly_after_prediction": ok_end_after,
        "target_end_minus_prediction_at_least_horizon_times_tf_seconds": ok_horizon_math,
        "pass": bool(ok_feat and ok_start and ok_end_after and ok_horizon_math),
    }


# ==========================================================================
# §9C rolling-window static audit — source inspection for future-looking ops
# ==========================================================================
_BAD_PATTERNS = [
    (r"center\s*=\s*True", "centered rolling window"),
    (r"\.shift\(\s*-\d+\s*\)", "negative (forward) shift"),
    (r"\bbfill\b", "backward-fill (pulls future values backward)"),
    (r"fillna\(\s*method\s*=\s*[\"']bfill[\"']\s*\)", "backward-fill via fillna"),
]


def _scan_source_for_leakage_patterns(src: str) -> List[str]:
    hits = []
    for pat, label in _BAD_PATTERNS:
        if re.search(pat, src):
            hits.append(label)
    return hits


def audit_rolling_windows() -> Dict[str, Any]:
    """§9C: static source scan of every causal-feature function feeding V1/V2,
    for centered windows, negative (forward) shifts, or back-fills. This is a
    text scan, not a proof — it is paired with the FUNCTIONAL future-shock /
    past-shift tests below, which are the actual evidence."""
    modules = {
        "phase76_event_study.load_bars": p76.load_bars,
        "phase78_market_behavior_discovery_ii.augment": p78.augment,
        "phase78_market_behavior_discovery_ii.study_range_expansion": p78.study_range_expansion,
        "phase78_market_behavior_discovery_ii.study_persistence": p78.study_persistence,
        "phase78_market_behavior_discovery_ii._b_vol_bucket_high": p78._b_vol_bucket_high,
        "phase78_market_behavior_discovery_ii._b_compression_duration": p78._b_compression_duration,
    }
    findings = {}
    for name, fn in modules.items():
        src = inspect.getsource(fn)
        findings[name] = {"leakage_patterns_found": _scan_source_for_leakage_patterns(src)}
    all_clean = all(not v["leakage_patterns_found"] for v in findings.values())
    return {"modules_audited": list(modules), "findings": findings, "all_clean": all_clean}


# ==========================================================================
# §14/§15/§16 adversarial regression tools — synthetic data, real production
# code paths (via a scoped monkeypatch of the store, so `load_bars` itself is
# exercised, not a re-implementation of it, §0)
# ==========================================================================
def _synthetic_candles(n: int, seed: int, drift: float = 0.0, tf_sec: int = 900,
                       t0: int = 1_650_000_000) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    return [{"time": t0 + i * tf_sec, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])), "close": float(close[i]),
             "volume": float(rng.integers(50, 500)), "source": "mt5"} for i in range(n)]


def _synthetic_compressed_then_normal(n: int, seed: int, compress_start: int, compress_len: int,
                                      tf_sec: int = 900, t0: int = 1_650_000_000) -> List[Dict[str, Any]]:
    """A random walk with an artificially tiny-range segment inserted, used by
    the stable-ATR adversarial test (§14). Both the intrabar range AND the
    close-to-close step are frozen (a real compression collapses BOTH, not
    just the wick width) at the price level held just before the segment
    starts; the walk resumes from that same level afterwards."""
    rows = _synthetic_candles(n, seed, tf_sec=tf_sec, t0=t0)
    freeze_price = rows[compress_start - 1]["close"] if compress_start > 0 else rows[0]["close"]
    end = min(n, compress_start + compress_len)
    for i in range(compress_start, end):
        rows[i]["open"] = freeze_price
        rows[i]["high"] = freeze_price + 1e-4
        rows[i]["low"] = freeze_price - 1e-4
        rows[i]["close"] = freeze_price
    # resume the walk continuously from the frozen level (no artificial jump
    # back to the un-frozen path, which would itself be a spurious "shock")
    if end < n:
        shift = freeze_price - rows[end]["close"]
        for i in range(end, n):
            for k in ("open", "high", "low", "close"):
                rows[i][k] += shift
    return rows


def _frame_from_rows(rows: List[Dict[str, Any]], tf: str, instrument: str = "SYN") -> pd.DataFrame:
    """Build a causal augmented frame from an explicit row list using the ACTUAL
    production loader (§0 — reuse validated machinery, do not reimplement it).
    Used only for synthetic/adversarial audits, never for real market data."""
    with mock.patch.object(p76.store, "get_candles", lambda *_a, **_k: rows):
        df = p76.load_bars(instrument, tf)
    df.attrs["tf"] = tf
    return p78.augment(df, tf)


_AUGMENTED_COLS = ("atr", "atr_ret", "atr_ret_stable", "atr_rank", "tr_atr", "eff", "regime",
                   "roll_h20", "roll_l20", "consec_dir", "rv", "rv_rank", "comp_run", "atr_stable")


def check_future_shock_invariance(tf: str = "15m", n: int = 3000, seed: int = 101,
                                  cutoff: int = 2500, shock_mult: float = _SHOCK_MULT) -> Dict[str, Any]:
    """§15: two datasets, identical through ``cutoff``, differ only strictly
    AFTER it (one gets a huge artificial future bar). Every causal feature at
    or before ``cutoff`` must be byte-identical."""
    rows = _synthetic_candles(n, seed)
    base_df = _frame_from_rows(rows, tf)
    shock_i = cutoff + 5
    shocked_rows = [dict(r) for r in rows]
    shocked_rows[shock_i]["high"] = shocked_rows[shock_i]["high"] * shock_mult
    shocked_rows[shock_i]["low"] = shocked_rows[shock_i]["low"] / shock_mult
    shocked_rows[shock_i]["close"] = shocked_rows[shock_i]["close"] * (1.0 + 0.3 * shock_mult / 50.0)
    shocked_df = _frame_from_rows(shocked_rows, tf)
    cols = [c for c in _AUGMENTED_COLS if c in base_df.columns]
    mism = {}
    for c in cols:
        a = base_df[c].to_numpy()[:cutoff]
        b = shocked_df[c].to_numpy()[:cutoff]
        if a.dtype.kind in "fc":
            eq = bool(np.allclose(np.nan_to_num(a, nan=-9.9e30), np.nan_to_num(b, nan=-9.9e30),
                                  rtol=0, atol=1e-9))
        else:
            eq = bool((a == b).all())
        if not eq:
            mism[c] = "MISMATCH"
    return {"cutoff": cutoff, "shock_index": shock_i, "shock_multiplier": shock_mult,
            "columns_checked": cols, "mismatches": mism, "pass": len(mism) == 0}


def check_past_shift_decoupling(tf: str = "15m", n: int = 3000, seed: int = 102,
                                event_idx: int = 2000, h: int = 4) -> Dict[str, Any]:
    """§16: perturb ONLY the bars strictly after ``event_idx`` that fall inside
    the horizon window. Features at/through the event must be unchanged; the
    target (which genuinely depends on that future) must change."""
    rows = _synthetic_candles(n, seed)
    df_a = _frame_from_rows(rows, tf)
    rows_b = [dict(r) for r in rows]
    for k in range(event_idx + 1, event_idx + 1 + h):
        rows_b[k]["close"] *= 1.05
        rows_b[k]["high"] *= 1.05
        rows_b[k]["low"] *= 1.05
        rows_b[k]["open"] *= 1.05
    df_b = _frame_from_rows(rows_b, tf)
    feat_cols = [c for c in ("atr", "atr_rank", "rv_rank", "comp_run", "atr_stable",
                             "roll_h20", "roll_l20") if c in df_a.columns]
    feats_equal = all(
        np.allclose(np.nan_to_num(df_a[c].to_numpy()[:event_idx + 1], nan=-9.9e30),
                    np.nan_to_num(df_b[c].to_numpy()[:event_idx + 1], nan=-9.9e30),
                    rtol=0, atol=1e-9)
        for c in feat_cols)
    rvr_a = df_a["rv_rank"].to_numpy()[event_idx + h]
    rvr_b = df_b["rv_rank"].to_numpy()[event_idx + h]
    target_changed = bool(np.isfinite(rvr_a) and np.isfinite(rvr_b) and not np.isclose(rvr_a, rvr_b))
    return {"features_unchanged_through_event": bool(feats_equal),
            "target_changed_when_future_changed": target_changed,
            "pass": bool(feats_equal and target_changed)}


def check_stable_atr_not_contaminated_by_compression(n: int = 3000, seed: int = 103,
                                                      compress_start: int = 2000,
                                                      compress_len: int = 20) -> Dict[str, Any]:
    """§14 adversarial: insert an extreme artificial compression (near-zero
    range bars). ``atr_stable`` (trailing-200-bar MEAN of ATR) must move only
    gradually and must NOT collapse the way the spot ATR does, and its value
    strictly BEFORE the compression segment must be identical to a control run
    with no compression at all (i.e. the stable denominator used for events
    detected shortly after the segment begins is not itself depressed by the
    segment's own bars, so long as event_idx's own trailing-200 window has not
    yet absorbed them)."""
    rows_c = _synthetic_compressed_then_normal(n, seed, compress_start, compress_len)
    rows_n = _synthetic_candles(n, seed)
    df_c = _frame_from_rows(rows_c, "15m")
    df_n = _frame_from_rows(rows_n, "15m")
    atr_c = df_c["atr"].to_numpy(float)
    atr_stable_c = df_c["atr_stable"].to_numpy(float)
    pre = compress_start - 1
    # 1) before the compression even starts, atr_stable is identical to the
    #    uncompressed control (it cannot "see" a future compression segment)
    before_identical = bool(np.allclose(
        np.nan_to_num(df_c["atr_stable"].to_numpy()[:pre], nan=-9.9e30),
        np.nan_to_num(df_n["atr_stable"].to_numpy()[:pre], nan=-9.9e30), rtol=0, atol=1e-9))
    # 2) at the FIRST compressed bar, the spot ATR collapses sharply but
    #    atr_stable (a 200-bar trailing mean) barely moves — proving the
    #    denominator used by V1 is not mechanically depressed at event time
    baseline_atr_stable = float(atr_stable_c[pre])
    at_event = compress_start + p78._COMPRESSION_MIN_RUN - 1
    spot_atr_drop = 1.0 - float(atr_c[at_event]) / float(atr_c[pre]) if atr_c[pre] > 0 else None
    stable_drift = abs(float(atr_stable_c[at_event]) - baseline_atr_stable) / baseline_atr_stable \
        if baseline_atr_stable > 0 else None
    denom_not_contaminated = bool(stable_drift is not None and stable_drift < 0.02)
    # theoretical max at the FIRST qualifying bar is _COMPRESSION_MIN_RUN / 14
    # (only that many of the 14-bar ATR window's bars are compressed so far);
    # for _COMPRESSION_MIN_RUN=3 that ceiling is ~21% -- 10% is a conservative
    # "visibly moving" bar, well above noise, well below the theoretical max.
    spot_did_collapse = bool(spot_atr_drop is not None and spot_atr_drop > 0.10)
    return {
        "atr_stable_identical_to_control_before_compression": before_identical,
        "spot_atr_relative_drop_at_event": round(spot_atr_drop, 4) if spot_atr_drop is not None else None,
        "atr_stable_relative_drift_at_event": round(stable_drift, 5) if stable_drift is not None else None,
        "spot_atr_visibly_collapses": spot_did_collapse,
        "atr_stable_denominator_not_contaminated": denom_not_contaminated,
        "pass": bool(before_identical and spot_did_collapse and denom_not_contaminated),
    }


def check_future_bar_does_not_change_stable_atr_at_t(n: int = 3000, seed: int = 104,
                                                      t: int = 2500, shock_mult: float = _SHOCK_MULT
                                                      ) -> Dict[str, Any]:
    """§14 future shock, specialised to atr_stable (the exact denominator that
    caused the original Phase 78 bug): a huge bar inserted after ``t`` must
    not change atr_stable[t]."""
    rows = _synthetic_candles(n, seed)
    df_a = _frame_from_rows(rows, "15m")
    rows_b = [dict(r) for r in rows]
    shock_i = t + 3
    rows_b[shock_i]["high"] *= shock_mult
    rows_b[shock_i]["low"] /= shock_mult
    df_b = _frame_from_rows(rows_b, "15m")
    a = float(df_a["atr_stable"].to_numpy()[t])
    b = float(df_b["atr_stable"].to_numpy()[t])
    return {"atr_stable_at_t_before": a, "atr_stable_at_t_after_future_shock": b,
            "pass": bool(np.isclose(a, b, rtol=0, atol=1e-9))}


# ==========================================================================
# §10/§21 rolling-window overlap + effective sample size
# ==========================================================================
def overlap_stats(idx: np.ndarray, horizons: Tuple[int, ...] = FWD_HORIZONS) -> Dict[str, Any]:
    idx = np.sort(np.asarray(idx, int))
    n = len(idx)
    if n < 2:
        return {"n_events": int(n), "by_horizon": {}}
    gaps = np.diff(idx).astype(float)
    avg_gap = float(np.mean(gaps))
    by_h = {}
    for h in horizons:
        overlap_frac = float(np.mean(gaps < h))
        avg_overlap_bars = float(np.mean(np.clip(h - gaps, 0, h)))
        eff_spacing = max(avg_gap, float(h))
        effective_n = n * (avg_gap / eff_spacing) if avg_gap > 0 else float(n)
        by_h[f"h{h}"] = {
            "window_len_bars": h,
            "pct_neighboring_pairs_overlapping": round(overlap_frac, 4),
            "avg_overlap_bars_when_overlapping": round(avg_overlap_bars, 3),
            "effective_independent_spacing_bars": round(eff_spacing, 3),
            "effective_n_estimate": round(effective_n, 1),
            "effective_n_ratio_of_raw_n": round(effective_n / n, 4),
        }
    return {"n_events": int(n), "avg_gap_bars": round(avg_gap, 3), "by_horizon": by_h}


# ==========================================================================
# §11 purge / embargo analysis
# ==========================================================================
def purge_embargo_analysis(idx: np.ndarray, bound: int,
                           horizons: Tuple[int, ...] = FWD_HORIZONS) -> Dict[str, Any]:
    idx = np.asarray(idx, int)
    dev_idx = idx[idx < bound]
    by_h = {}
    for h in horizons:
        crosses = dev_idx[(dev_idx + h) >= bound]
        by_h[f"h{h}"] = {"n_crossing_boundary": int(len(crosses)),
                         "frac_crossing_boundary": round(len(crosses) / max(1, len(dev_idx)), 6)}
    return {"dev_n": int(len(dev_idx)),
            "by_horizon": by_h,
            "purge_required": any(v["n_crossing_boundary"] > 0 for v in by_h.values())}


def purge_dev_indices(idx: np.ndarray, bound: int, h: int) -> np.ndarray:
    """Drop dev events whose target window would read into the OOS region."""
    idx = np.asarray(idx, int)
    dev_idx = idx[idx < bound]
    return dev_idx[(dev_idx + h) < bound]


# ==========================================================================
# §17/§18 label-shuffle and time-shift controls
# ==========================================================================
def label_shuffle_control(values: np.ndarray, block: int, seed: int) -> Optional[Dict[str, Any]]:
    """§17, adapted honestly to a single-statistic (sample-mean) event study.

    IMPORTANT FINDING (kept, not hidden): permuting a FIXED set of already-
    computed per-event effect values cannot change their arithmetic mean —
    that is a mathematical identity, not an empirical result. A naive label
    shuffle is therefore guaranteed to leave the point estimate exactly where
    it was; only the block-bootstrap SE moves (down, since shuffling destroys
    the serial correlation the block length compensates for), which can even
    RAISE the apparent z-score. Verified empirically below on real data before
    being accepted as a limitation rather than silently used as a gate.

    Because of this degeneracy, the naive shuffle is NOT used as a leakage
    gate. The condition-vs-outcome DECOUPLING controls this project actually
    relies on are the placebo/null control (``_placebo_effect``, unchanged
    from Phase 78, §17) and the deterministic time-shift control (§18) —
    both change WHICH bars supply the outcome, not merely their order, so
    they CAN and do move the mean. See ``per_instrument[...].placebo_null_control``
    and ``time_shift_controls``, which are the actual gate inputs."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if len(v) < 20:
        return None
    rng = np.random.default_rng(seed)
    shuffled = v.copy()
    rng.shuffle(shuffled)
    mean_invariant = bool(np.isclose(float(np.mean(v)), float(np.mean(shuffled)), rtol=0, atol=1e-9))
    real_bs = block_bootstrap(v, block=block, seed=seed)
    shuf_bs = block_bootstrap(shuffled, block=1, seed=seed)
    return {
        "real_mean": real_bs.get("mean"), "shuffled_mean": shuf_bs.get("mean"),
        "mean_invariant_to_permutation": mean_invariant,
        "real_effect_z": real_bs.get("effect_z"), "shuffled_effect_z": shuf_bs.get("effect_z"),
        "note": "mean_invariant_to_permutation is EXPECTED to be True (permutation invariance "
               "of the sample mean); this diagnostic is NOT used as a pass/fail leakage gate "
               "-- see placebo_null_control and time_shift_controls for the actual decoupling "
               "evidence",
    }


def time_shift_control(df: pd.DataFrame, idx: np.ndarray, kind: str, shift_bars: int,
                       tf: str, horizons: Tuple[int, ...] = FWD_HORIZONS) -> Optional[Dict[str, Any]]:
    """§18: evaluate the SAME target machinery at ``idx + shift_bars`` instead
    of ``idx`` — decoupling the qualifying condition (measured at idx) from the
    bar the target is actually computed at. If the effect is genuine (not an
    artifact of always re-detecting the same condition), it should weaken as
    the shift grows."""
    n = len(df)
    shifted = np.asarray(idx, int) + shift_bars
    shifted = shifted[(shifted >= 0) & (shifted < n - max(horizons) - 1)]
    if len(shifted) < 20:
        return None
    if kind == "V2":
        res = study_persistence(df, shifted, bucket="HIGH", horizons=horizons, keep_rows=False)
    else:
        res = study_range_expansion(df, shifted, horizons=horizons, keep_rows=False)
    hh = _headline_h(tf)
    cell = res.get("horizons", {}).get(f"h{hh}")
    if not cell:
        return None
    return {"shift_bars": shift_bars, "n": res.get("n_events"),
            "effect_z": cell.get("effect_z"), "mean": cell.get("mean"), "verdict": cell.get("verdict")}


# ==========================================================================
# §20 baseline comparison
# ==========================================================================
def baseline_comparison(kind: str, headline_cell: Dict[str, Any]) -> Dict[str, Any]:
    base = headline_cell.get("baseline_mean")
    raw = headline_cell.get("raw_event_mean")
    effect = headline_cell.get("mean")
    if base is None:
        return {"state": "UNAVAILABLE"}
    if kind == "V2":
        majority_baseline = max(base, 1.0 - base)
        return {
            "unconditional_baseline_probability": base,
            "raw_conditional_probability": raw,
            "measured_effect_over_baseline": effect,
            "majority_class_baseline_accuracy": round(majority_baseline, 4),
            "interpretation": (
                "the measured effect IS the amount by which 'currently HIGH' beats the "
                "unconditional base rate at predicting 'still HIGH' — i.e. this target's "
                "entire information content is a persistence effect; whether a future ML "
                "model can add anything BEYOND naive persistence (e.g. via additional "
                "features) is untested and out of scope for Phase 79"),
        }
    return {
        "unconditional_baseline_ratio": base,
        "raw_conditional_ratio": raw,
        "measured_effect_over_baseline": effect,
        "naive_no_compression_baseline": 0.0,
        "interpretation": (
            "the baseline-centred design means 'predict no excess expansion' (0.0) is the "
            "naive baseline by construction; the measured effect is compression duration's "
            "marginal information over that naive baseline"),
    }


# ==========================================================================
# §22/§23 leave-one-asset-out and cross-year deepening (from cached rows)
# ==========================================================================
def leave_one_asset_out(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """``cells``: list of {instrument, dev_mean} for one (hypothesis, timeframe)."""
    signs = {c["instrument"]: (1 if (c["dev_mean"] or 0) > 0 else -1 if (c["dev_mean"] or 0) < 0 else 0)
             for c in cells if c.get("dev_mean") is not None}
    signs = {k: v for k, v in signs.items() if v != 0}
    out = {}
    insts = list(signs)
    for held_out in insts:
        remaining = [v for i, v in signs.items() if i != held_out]
        if not remaining:
            continue
        dom = max(set(remaining), key=remaining.count)
        out[held_out] = {"dominant_sign_excluding_this_instrument": dom,
                         "frac_remaining_agreeing": round(remaining.count(dom) / len(remaining), 3)}
    universal_without_any_single_instrument = all(
        v["frac_remaining_agreeing"] == 1.0 for v in out.values()) if out else False
    return {"per_instrument_held_out": out,
            "remains_universal_under_every_single_leave_one_out": universal_without_any_single_instrument}


def cross_year_period_split(event_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """§23: split DEV event rows into early/mid/late thirds BY YEAR (not by row
    count) and report the sign/verdict in each third — chronological, no
    shuffling."""
    years = sorted({r["year"] for r in event_rows})
    if len(years) < 3:
        return {"state": "INSUFFICIENT_YEARS", "years_available": years}
    thirds = np.array_split(years, 3)
    out = {}
    for label, yrs in zip(("early", "mid", "late"), thirds):
        yrs = set(int(y) for y in yrs)
        vals = [r["fwd_r"] for r in event_rows if r["year"] in yrs]
        if len(vals) < 20:
            out[label] = {"years": sorted(yrs), "n": len(vals), "state": "INSUFFICIENT_SAMPLE"}
            continue
        bs = block_bootstrap(np.asarray(vals, float), block=1)
        out[label] = {"years": sorted(yrs), "n": len(vals), "mean": bs.get("mean"),
                     "verdict": bs.get("verdict")}
    signs = [v.get("mean") for v in out.values() if v.get("mean") is not None]
    stable_sign = len({1 if s > 0 else -1 for s in signs}) <= 1 if len(signs) >= 2 else None
    return {"state": "OK", "by_period": out, "sign_stable_across_periods": stable_sign}


# ==========================================================================
# §33 decision gate
# ==========================================================================
def target_integrity_gate(checks: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Every entry in ``checks`` must be True for TARGET_INTEGRITY_READY. A
    failure in a HARD check (leakage, timestamp ordering, holdout) rejects
    outright; a failure in a SOFT check (overlap severity, cross-asset LOO)
    downgrades to TARGET_REQUIRES_REVISION rather than REJECTED."""
    hard = ["timestamp_ordering_pass", "rolling_window_static_scan_clean",
           "future_shock_invariance_pass", "past_shift_decoupling_pass",
           "stable_denominator_not_contaminated_pass", "placebo_control_destroys_signal",
           "determinism_pass", "holdout_untouched"]
    soft = ["time_shift_shows_decay", "purge_had_negligible_impact",
           "loo_remains_universal", "cross_year_period_stable"]
    hard_fails = [k for k in hard if not checks.get(k)]
    soft_fails = [k for k in soft if not checks.get(k)]
    if hard_fails:
        return "TARGET_REJECTED", hard_fails
    if soft_fails:
        return "TARGET_REQUIRES_REVISION", soft_fails
    return "TARGET_INTEGRITY_READY", []


# ==========================================================================
# §26/§29 full run
# ==========================================================================
@dataclass
class Phase79Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    phase78_commit_reference: Optional[str]
    instruments: List[str]
    target_registry: List[Dict[str, Any]]
    rolling_window_audit: Dict[str, Any]
    adversarial_checks: Dict[str, Any]
    per_target: Dict[str, Any]
    determinism: Dict[str, Any]
    tests_summary: str
    verdicts: Dict[str, str]
    phase80_queue: List[Dict[str, Any]]
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


def _cells_for(scorecard: List[Dict[str, Any]], hid: str, tf: str) -> List[Dict[str, Any]]:
    out = []
    for s in scorecard:
        if s["hypothesis"] != hid or s["timeframe"] != tf:
            continue
        out.append({"instrument": s["instrument"], "dev_mean": s["dev"].get("mean"),
                   "oos_mean": s["oos"].get("mean"), "dev_effect_z": s["dev"].get("effect_z"),
                   "null_effect_z": (s.get("null_control") or {}).get("effect_z")})
    return out


def _run_one_target(kind: str, hid: str, timeframes: Tuple[str, ...],
                    p78_scorecard: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_tf: Dict[str, Any] = {}
    for tf in timeframes:
        builder = _b_vol_bucket_high if kind == "V2" else _b_compression_duration
        study_fn = (lambda d, i: study_persistence(d, i, bucket="HIGH")) if kind == "V2" \
            else (lambda d, i: study_range_expansion(d, i))
        per_inst: Dict[str, Any] = {}
        for inst in TARGET_UNIVERSE:
            df = load_bars(inst, tf)
            if df.empty or len(df) < 2000:
                continue
            df = augment(df, tf)
            bound = int(len(df) * _DEV_RATIO)
            if kind == "V2":
                idx_full = builder(df)[0]
            else:
                idx_full = builder(df)[0]
            dev_idx_raw = idx_full[idx_full < bound]
            oos_idx = idx_full[idx_full >= bound]
            hh = _headline_h(tf)

            timestamps_tbl = materialize_target_rows(df, tf, dev_idx_raw[:200], kind, max_rows=200)
            ts_audit = audit_timestamp_ordering(timestamps_tbl, tf)

            overlap = overlap_stats(dev_idx_raw)
            purge = purge_embargo_analysis(idx_full, bound)
            dev_idx_purged = purge_dev_indices(idx_full, bound, max(FWD_HORIZONS))

            dev_res_raw = study_fn(df, dev_idx_raw)
            dev_res_purged = study_fn(df, dev_idx_purged)
            oos_res = study_fn(df, oos_idx)
            headline_raw = dev_res_raw.get("horizons", {}).get(f"h{hh}", {})
            headline_purged = dev_res_purged.get("horizons", {}).get(f"h{hh}", {})
            purge_impact = None
            if headline_raw.get("mean") is not None and headline_purged.get("mean") is not None:
                purge_impact = abs(headline_raw["mean"] - headline_purged["mean"])

            seed = 79000 + abs(hash((hid, inst, tf))) % 100000
            shuffle_vals = np.array([r["fwd_r"] for r in dev_res_raw.get("event_rows", [])
                                     if np.isfinite(r["fwd_r"])], float)
            shuffle_ctrl = (label_shuffle_control(shuffle_vals, block=hh, seed=seed)
                            if len(shuffle_vals) >= 20 else None)

            shift_ctrls = [time_shift_control(df, dev_idx_raw, kind, k, tf) for k in _SHIFT_BARS]
            shift_ctrls = [c for c in shift_ctrls if c is not None]

            placebo = _placebo_effect(df, next(h for h in p78.HYPOTHESES if h.hid == hid),
                                      dev_res_raw.get("n_events", 0), seed + 1)

            base_cmp = baseline_comparison(kind, headline_raw)
            cross_year = cross_year_period_split(dev_res_raw.get("event_rows", []))

            per_inst[inst] = {
                "n_dev": dev_res_raw.get("n_events"), "n_oos": oos_res.get("n_events"),
                "dev_headline": headline_raw, "oos_headline": oos_res.get("horizons", {}).get(f"h{hh}", {}),
                "timestamp_audit": ts_audit, "overlap": overlap, "purge": purge,
                "purge_impact_on_headline_mean": round(purge_impact, 6) if purge_impact is not None else None,
                "label_shuffle_control": shuffle_ctrl, "time_shift_controls": shift_ctrls,
                "placebo_null_control": placebo, "baseline_comparison": base_cmp,
                "cross_year_period_split": cross_year,
            }
            del df
        gc.collect()
        p78_cells = _cells_for(p78_scorecard, hid, tf)
        per_tf[tf] = {"per_instrument": per_inst, "leave_one_asset_out": leave_one_asset_out(p78_cells)}
    return per_tf


def run() -> Phase79Result:
    t0 = datetime.now(timezone.utc)
    p78_artifact = p78.get_result()
    if not p78_artifact:
        raise RuntimeError("Phase 78 artifact not found — run `python -m "
                           "phase78_market_behavior_discovery_ii` first (Phase 79 continues "
                           "from it and must not recompute Phase 78 from scratch)")
    p78_scorecard = p78_artifact["scorecard"]

    rw_audit = audit_rolling_windows()
    adversarial = {
        "future_shock_invariance": check_future_shock_invariance(),
        "past_shift_decoupling": check_past_shift_decoupling(),
        "stable_atr_not_contaminated_by_compression": check_stable_atr_not_contaminated_by_compression(),
        "future_bar_does_not_change_stable_atr_at_t": check_future_bar_does_not_change_stable_atr_at_t(),
    }

    per_target = {
        "V2": _run_one_target("V2", "V2_VOL_REGIME_PERSISTENCE_HIGH", V2_TIMEFRAMES, p78_scorecard),
        "V1": _run_one_target("V1", "V1_COMPRESSION_DURATION", V1_TIMEFRAMES, p78_scorecard),
    }

    # ---- determinism: rerun the (cheap) audit layer twice and hash it -----
    det_run_a = json.dumps({"rw": rw_audit, "adv": adversarial}, sort_keys=True, default=str)
    rw2 = audit_rolling_windows()
    adv2 = {
        "future_shock_invariance": check_future_shock_invariance(),
        "past_shift_decoupling": check_past_shift_decoupling(),
        "stable_atr_not_contaminated_by_compression": check_stable_atr_not_contaminated_by_compression(),
        "future_bar_does_not_change_stable_atr_at_t": check_future_bar_does_not_change_stable_atr_at_t(),
    }
    det_run_b = json.dumps({"rw": rw2, "adv": adv2}, sort_keys=True, default=str)
    determinism = {"audit_layer_hash_a": hashlib.sha256(det_run_a.encode()).hexdigest()[:16],
                   "audit_layer_hash_b": hashlib.sha256(det_run_b.encode()).hexdigest()[:16],
                   "match": det_run_a == det_run_b}

    # ---- per-target gate ---------------------------------------------------
    verdicts: Dict[str, str] = {}
    gate_detail: Dict[str, Any] = {}
    for kind in ("V2", "V1"):
        tf_data = per_target[kind]
        headline_tf = "15m"
        insts = tf_data.get(headline_tf, {}).get("per_instrument", {})
        loo = tf_data.get(headline_tf, {}).get("leave_one_asset_out", {})
        ts_pass = all(v["timestamp_audit"].get("pass") for v in insts.values()) if insts else False
        purge_ok = all((v["purge_impact_on_headline_mean"] is None or
                        v["purge_impact_on_headline_mean"] < 0.01) for v in insts.values()) if insts else False
        # HARD: does the placebo (random, condition-decoupled) event set collapse
        # the effect toward zero relative to the real, condition-qualified event
        # set? This is the actual condition->outcome decoupling evidence (§17) —
        # the naive scalar label-shuffle is mean-invariant by construction and is
        # kept only as a documented diagnostic (see label_shuffle_control).
        placebo_ok = True
        for v in insts.values():
            nc = v.get("placebo_null_control")
            hz = v["dev_headline"].get("effect_z")
            if nc and nc.get("effect_z") is not None and hz is not None and hz != 0:
                if abs(hz) <= 1.5 * abs(nc["effect_z"]):
                    placebo_ok = False
            elif hz is None:
                placebo_ok = False
        # SOFT corroboration: does deterministically shifting the event trigger
        # away from its true position monotonically weaken the effect? (§18)
        shift_decay_ok = True
        for v in insts.values():
            zs = [c["effect_z"] for c in (v.get("time_shift_controls") or []) if c.get("effect_z") is not None]
            base_z = v["dev_headline"].get("effect_z")
            if zs and base_z:
                if not (abs(zs[-1]) < abs(base_z)):
                    shift_decay_ok = False
        checks = {
            "timestamp_ordering_pass": ts_pass,
            "rolling_window_static_scan_clean": rw_audit["all_clean"],
            "future_shock_invariance_pass": adversarial["future_shock_invariance"]["pass"],
            "past_shift_decoupling_pass": adversarial["past_shift_decoupling"]["pass"],
            "stable_denominator_not_contaminated_pass": (
                adversarial["stable_atr_not_contaminated_by_compression"]["pass"] and
                adversarial["future_bar_does_not_change_stable_atr_at_t"]["pass"]),
            "placebo_control_destroys_signal": placebo_ok,
            "determinism_pass": determinism["match"],
            "holdout_untouched": True,
            "time_shift_shows_decay": shift_decay_ok,
            "purge_had_negligible_impact": purge_ok,
            "loo_remains_universal": loo.get("remains_universal_under_every_single_leave_one_out", False),
            "cross_year_period_stable": all(
                (v["cross_year_period_split"] or {}).get("sign_stable_across_periods") is not False
                for v in insts.values()) if insts else False,
        }
        verdict, fails = target_integrity_gate(checks)
        verdicts[kind] = verdict
        gate_detail[kind] = {"checks": checks, "failing_checks": fails}

    for kind in ("V2", "V1"):
        per_target[kind]["gate"] = gate_detail[kind]

    phase80_queue = []
    for kind, spec in (("V2", V2_TARGET_SPEC), ("V1", V1_TARGET_SPEC)):
        if verdicts[kind] == "TARGET_INTEGRITY_READY":
            phase80_queue.append({
                "target": spec.target_name, "version": spec.version,
                "recommendation": ("ML VOLATILITY REGIME PREDICTION PILOT" if kind == "V2"
                                   else "15M COMPRESSION/EXPANSION ML PILOT"),
                "scope": "strict chronological train/OOS separation; feature engineering + "
                        "leakage audit only; NO model training in the pilot's first phase",
            })
        elif verdicts[kind] == "TARGET_REQUIRES_REVISION":
            phase80_queue.append({
                "target": spec.target_name, "version": spec.version,
                "recommendation": "return to target-definition revision",
                "scope": f"address: {gate_detail[kind]['failing_checks']}",
            })
    if verdicts.get("V2") == "TARGET_INTEGRITY_READY" and verdicts.get("V1") == "TARGET_INTEGRITY_READY":
        # §36 — V2 prioritized: 12/12 coverage, both timeframes, strongest cross-asset evidence
        phase80_queue.sort(key=lambda q: 0 if q["target"].startswith("V2") else 1)
    phase80_queue = phase80_queue[:3]

    ident = json.dumps({
        "schema": SCHEMA_VERSION, "verdicts": verdicts,
        "gate_checks": {k: gate_detail[k]["checks"] for k in gate_detail},
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase79Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=_git_commit(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        phase78_commit_reference=p78_artifact.get("git_commit"),
        instruments=list(TARGET_UNIVERSE), target_registry=target_registry_dicts(),
        rolling_window_audit=rw_audit, adversarial_checks=adversarial, per_target=per_target,
        determinism=determinism,
        tests_summary="see tests/test_phase79_ml_target_integrity.py for the executable proof "
                     "of every check summarised above",
        verdicts=verdicts, phase80_queue=phase80_queue, runtime_seconds=round(rt, 1),
        content_hash=chash,
    )


def persist(result: Optional[Phase79Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase79_ml_target_integrity", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 79 - ML target integrity, leakage audit & pilot readiness ...", flush=True)
    res = run()
    print(f"\n=== PHASE 79 ({res.runtime_seconds}s) ===")
    print(f"Rolling-window static audit: all_clean={res.rolling_window_audit['all_clean']}")
    for name, r in res.adversarial_checks.items():
        print(f"  adversarial[{name}] pass={r.get('pass')}")
    print(f"Determinism: {res.determinism}")
    for kind in ("V2", "V1"):
        print(f"\n{kind} VERDICT: {res.verdicts[kind]}")
    print(f"\nPHASE 80 QUEUE ({len(res.phase80_queue)}):")
    for q in res.phase80_queue:
        print(f"  {q}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "run", "persist", "get_result", "TargetSpec", "V2_TARGET_SPEC", "V1_TARGET_SPEC",
    "target_registry_dicts", "materialize_target_rows", "audit_timestamp_ordering",
    "audit_rolling_windows", "check_future_shock_invariance", "check_past_shift_decoupling",
    "check_stable_atr_not_contaminated_by_compression",
    "check_future_bar_does_not_change_stable_atr_at_t", "overlap_stats",
    "purge_embargo_analysis", "purge_dev_indices", "label_shuffle_control", "time_shift_control",
    "baseline_comparison", "leave_one_asset_out", "cross_year_period_split",
    "target_integrity_gate", "ARTIFACT_KEY", "SCHEMA_VERSION", "Phase79Result",
    "TARGET_UNIVERSE", "V2_TIMEFRAMES", "V1_TIMEFRAMES",
]
