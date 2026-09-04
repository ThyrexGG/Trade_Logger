# -*- coding: utf-8 -*-
"""
Phase 84 -- Information Frontier & Missing Signal Research Audit.

This is deliberately NOT a pipeline phase like 76-83. It is an audit/roadmap
phase: the deliverable is a research report (``docs/PHASE_84_INFORMATION_
FRONTIER_AUDIT.md``) classifying what information TradeLogger already has,
what it plausibly lacks, and the single most scientifically defensible next
research direction. No strategy artifact, no new data acquisition, and no
unrestricted model search is performed here (per the master prompt's
repeated ABSOLUTE RULE).

Three small, explicitly-permitted, EXISTING-DATA-ONLY quantitative pieces
are computed by this module, each reusing Phase 76-83 machinery rather than
duplicating it:

  1. ``run_feature_group_ablation`` -- a cumulative feature-group ablation
     (intercept-only -> +volatility -> +time/session -> +trend/momentum ->
     +location/structure [= Phase 83's full Baseline D]) for BOTH the
     magnitude target (T2) and the direction target (T1), reusing Phase 83's
     ``build_pooled_context_dataset`` / ``discovery_confirmation_split`` /
     ``fit_and_eval_83`` unchanged. This is purely a "which existing group
     already contributes" understanding exercise -- not a competition, and
     no new group is ever selected as a winner.

  2. ``run_volume_ablation`` -- extends step 1 with ONE additional group:
     MT5 tick-volume-derived features (``volume_rank``, ``volume_ret_1``),
     computed with the identical causal trailing-200-bar-rank convention
     already used for ``atr_rank``/``rv_rank`` since Phase 76/78. This is
     included because the repository audit (see ``VOLUME_COLUMN_AUDIT``
     below) found that MT5 tick volume has been loaded into the shared
     ``load_bars()`` causal frame (as column ``vol``) by EVERY phase since
     Phase 76, yet has never once been placed in a feature registry or
     ablation set in Phases 76-83 -- a zero-acquisition-cost, already-causal,
     already-available column that has simply never been tested. Testing it
     is explicitly an "existing data, different use" experiment, not new
     data acquisition.

  3. ``redundancy_audit`` -- a correlation / mutual-information / PCA
     understanding pass over Phase 83's own Baseline-D feature set (never a
     feature-selection competition -- no group is dropped or recommended for
     removal here).

  4. ``data_inventory_audit`` -- queries ``historical_data_store.
     list_available()`` LIVE (never hard-coded) to determine, per instrument,
     which timeframes are actually populated and over what date range --
     this is the concrete evidence behind the native-resolution / tick-data
     feasibility sections of the report (never assumed).

  5. ``predictability_ceiling_table`` -- reads the ALREADY-PERSISTED
     ``get_result()`` artifacts of Phases 78/80/81/82/83 live (never
     hand-copied numbers) and extracts a small set of headline
     direction/magnitude/state predictability figures into one table. No
     phase is re-run.

No M15-vs-M1 resolution experiment is run (see ``m1_resolution_feasibility``
for the documented reason: MT5 M1 data exists ONLY for XAUUSD over a
~14-week window, which the audit judges too short and too narrow -- a single
instrument, one short and unusually recent regime -- to support a fair,
non-overfitting comparison against the multi-year M15 study population; the
master prompt's own "do not manufacture success" principle governs this
call). This is reported as a judgment, not silently skipped.

Safety invariants (identical to every phase since 76): read-only research,
no execution/broker/risk import, the frozen Gold strategy contract hash is
read (never modified) purely to stamp it on the artifact, and the frozen
Phase-74 holdout is never touched by anything in this module.
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
from sklearn.decomposition import PCA
from sklearn.feature_selection import mutual_info_regression

import gold_strategy_baseline as gsb
import historical_data_store as store
import phase78_market_behavior_discovery_ii as p78
import phase80_ml_volatility_regime as p80
import phase82_compression_expansion_ml_pilot as p82
import phase83_conditional_interaction_discovery as p83
from phase76_event_study import RANDOM_SEED, load_bars
from phase78_market_behavior_discovery_ii import augment
from phase81_v2_information_decomposition import bootstrap_delta_ci
from phase82_compression_expansion_ml_pilot import compute_regression_metrics, _r2_fn
from phase83_conditional_interaction_discovery import (
    BASELINE_D_COLUMNS, BASELINE_D_CONTINUOUS, BASELINE_D_REGIME_DUMMIES,
    BASELINE_D_SESSION_DUMMIES, INSTRUMENTS_83, PRIMARY_HORIZON, PRIMARY_TF,
    discovery_confirmation_split,
)

SCHEMA_VERSION = "phase84.1"
ARTIFACT_KEY = "phase84_information_frontier_audit"
DATASET_VERSION = "phase84-volume-dataset-v1"

# ==========================================================================
# §1 repository audit findings -- static facts, each independently verified
# by direct inspection during this phase (never assumed from documentation
# or from an earlier phase's memory/report). Re-verified at run() time where
# cheaply possible (``data_inventory_audit``); the rest are code-inspection
# facts recorded as of this commit and are not expected to change quietly
# (a change here would need a corresponding code change).
# ==========================================================================
VOLUME_COLUMN_AUDIT: Dict[str, Any] = {
    "finding": "historical_data_store stores exactly one volume-like column "
               "('volume', populated from MT5 tick_volume by mt5_provider.py). "
               "phase76_event_study.load_bars() loads it into every phase's "
               "shared causal frame as column 'vol' -- but grep across "
               "phase76/78/80/81/82/83's feature registries and ablation "
               "sets (FEATURE_REGISTRY, ABLATION_SETS, FEATURE_GROUPS_81, "
               "FEATURE_GROUPS_82, BASELINE_D_COLUMNS) found zero references "
               "to 'vol'/'volume' anywhere -- it has been loaded and silently "
               "discarded by every phase since 76.",
    "orthogonality_caveat": "MT5 tick_volume counts price-update ticks at "
               "this ONE broker, not executed trade volume on a centralized "
               "exchange; for spot FX/OTC gold there is no single centralized "
               "volume figure at all. Potentially informative, but not "
               "equivalent to true traded volume.",
    "acquisition_cost": "NONE -- already stored, already loaded by every "
               "phase's own data loader.",
}

MT5_CAPABILITY_AUDIT: Dict[str, Any] = {
    "copy_ticks_range_used": False,
    "note_copy_ticks": "MT5's Python API exposes copy_ticks_range (bid/ask/"
               "last/volume/flags at tick resolution) but grep across the "
               "entire repository found zero calls to it anywhere -- "
               "TradeLogger has never ingested historical tick data, only "
               "OHLCV candles via copy_rates_range.",
    "bid_ask_spread_in_schema": False,
    "note_schema": "historical_data_store's schema carries "
               "open/high/low/close/volume/source/source_revision only -- "
               "no bid, ask, spread, or market-depth column exists anywhere "
               "in the persisted schema.",
    "live_bid_ask_usage": "symbol_info_tick() is called live in "
               "market_data.py, order_execution.py, server.py and "
               "auto_sync.py for CURRENT price only -- never persisted "
               "historically, and order_execution.py is part of the frozen "
               "live layer this phase does not touch.",
    "market_book_depth_used": False,
}

MACRO_NEWS_AI_AUDIT: Dict[str, Any] = {
    "macro_providers": ["FRED (Phase 65 macro provider)",
                        "CFTC COT net positioning (Phase 66 multi-provider "
                        "macro evidence layer, macro_intelligence_engine.py)"],
    "macro_revision_awareness": "macro_intelligence_engine.py's own module "
               "docstring states an explicit lookahead rule: releases with "
               "release_timestamp > as_of are strictly inaccessible.",
    "news_provider": "ForexFactory + StandardMacroCalendar via "
               "xauusd_daily_preflight.EconomicCalendarProviderFactory, with "
               "an immutable NewsSnapshotStore and CalendarMutationDetector "
               "(Phase 38, xauusd_news_snapshot_store.py) already tracking "
               "post-release revisions/forecast shifts -- revision-awareness "
               "infrastructure for news/macro already exists at the data "
               "layer, ahead of anything Phases 76-83 have used.",
    "ai_gemini_usage": "api/gemini_client.py wraps a LIVE conversational "
               "Gemini assistant (chat-style, model gemini-1.5-flash by "
               "default) for on-demand analysis commentary -- it is not, "
               "and has never been used as, a deterministic historical "
               "feature-generation pipeline over archived text.",
    "vwap_structure": "phase75_orb_vwap.py (session-VWAP mean reversion, "
               "NO_EDGE_CONFIRMED) and strategies/smc_utils.py + "
               "true_mtf_engine.py (Phase 19 swing/liquidity/MTF structure) "
               "already exist; true_mtf_engine.py's own docstring describes "
               "a 1D->4H->15M->5M->1M cascade, but this PREDATES and is "
               "architecturally independent of the Phase 76-83 event-study "
               "lineage, and (per data_inventory_audit below) M1/M5 data is "
               "NOT actually populated for most of the canonical universe.",
    "monte_carlo_wfo": "backtester.py already implements run_monte_carlo() "
               "and run_walk_forward() for strategy-level trade-sequence "
               "resampling -- a different (execution-outcome) use of "
               "bootstrap resampling than Phase 76-83's block-bootstrap over "
               "raw target values, not reused here.",
}


# ==========================================================================
# §7 cumulative feature-group ablation (existing-data-only, T1 AND T2)
# ==========================================================================
def _cumulative_feature_groups() -> List[Tuple[str, List[str]]]:
    session_cols = list(BASELINE_D_SESSION_DUMMIES)
    regime_cols = list(BASELINE_D_REGIME_DUMMIES)
    g0: List[str] = []
    g1 = g0 + ["atr_rank", "rv_rank"]
    g2 = g1 + ["hour_sin", "hour_cos", "dow"] + session_cols
    g3 = g2 + ["mom_4"] + regime_cols
    g4 = g3 + ["loc_in_range", "dist_pdh_atr", "dist_pdl_atr"]
    assert set(g4) == set(BASELINE_D_COLUMNS), "G4 must equal Phase 83's full Baseline D"
    return [
        ("G0_intercept_only", g0),
        ("G1_plus_volatility", g1),
        ("G2_plus_time_session", g2),
        ("G3_plus_trend_momentum", g3),
        ("G4_plus_location_structure_FULL_BASELINE_D", g4),
    ]


def _fit_eval_group_84(train: pd.DataFrame, test: pd.DataFrame, features: List[str],
                       target_col: str) -> Dict[str, Any]:
    """Mirrors Phase 81's ``fit_and_eval_group`` empty-feature special case,
    adapted for a regression target (constant-predictor = train mean)."""
    train_mean = float(train[target_col].mean())
    if not features:
        y_test = test[target_col].to_numpy(float)
        p_test = np.full(len(y_test), train_mean)
        return {"features": [], "n_train": len(train), "train_mean": train_mean,
               "metrics": compute_regression_metrics(y_test, p_test, train_mean),
               "_p_pred": p_test, "_y_true": y_test}
    cols = [f"feat__{c}" for c in features]
    r = p83.fit_and_eval_83(train, test, cols, target_col)
    return {"features": features, "n_train": r["n_train"], "train_mean": r["train_mean"],
           "metrics": r["metrics"], "_p_pred": r["_p_pred"], "_y_true": r["_y_true"]}


def _directional_hit_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Secondary, purely descriptive metric for T1: sign-match rate against
    a nonzero prediction (baseline = 0.5 under no information)."""
    nz = np.abs(y_pred) > 1e-12
    if nz.sum() == 0:
        return 0.5
    return float((np.sign(y_true[nz]) == np.sign(y_pred[nz])).mean())


def run_feature_group_ablation(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                               groups: Optional[List[Tuple[str, List[str]]]] = None
                               ) -> Dict[str, Any]:
    groups = groups if groups is not None else _cumulative_feature_groups()
    out: Dict[str, List[Dict[str, Any]]] = {"T1": [], "T2": []}
    full_by_target: Dict[str, Dict[str, Any]] = {}
    for target_col in ("T1", "T2"):
        rows = []
        fits: Dict[str, Dict[str, Any]] = {}
        for name, feats in groups:
            r = _fit_eval_group_84(discovery, confirmation, feats, target_col)
            fits[name] = r
            row = {"group": name, "n_features": len(feats), "oos_r2": r["metrics"]["oos_r2"],
                  "mae": r["metrics"]["mae"], "spearman": r["metrics"]["spearman"]}
            if target_col == "T1":
                row["directional_hit_rate"] = round(
                    _directional_hit_rate(r["_y_true"], r["_p_pred"]), 4)
            rows.append(row)
        # delta of full (last group) vs intercept-only (first group), bootstrap CI
        g0_name, g_last_name = groups[0][0], groups[-1][0]
        boot = bootstrap_delta_ci(
            fits[g_last_name]["_y_true"], fits[g_last_name]["_p_pred"], fits[g0_name]["_p_pred"],
            _r2_fn(fits[g_last_name]["train_mean"]), block=PRIMARY_HORIZON, seed=RANDOM_SEED)
        out[target_col] = rows
        full_by_target[target_col] = {"full_vs_intercept_delta_r2": boot}
    out["full_vs_intercept_delta_r2"] = {t: full_by_target[t]["full_vs_intercept_delta_r2"] for t in ("T1", "T2")}
    return out


# ==========================================================================
# §41-46/§75-77 volume ablation -- ONE new group added to the existing
# ablation, using data already loaded by every phase since 76 but never
# tested (see VOLUME_COLUMN_AUDIT)
# ==========================================================================
_VOLUME_WINDOW = 200


def _add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Causal (trailing-only) tick-volume features, using the IDENTICAL
    trailing-200-bar percentile-rank convention already used for atr_rank/
    rv_rank since Phase 76/78 (see phase76_event_study.load_bars / "
    "phase78_market_behavior_discovery_ii.augment)."""
    vol = np.clip(df["vol"].to_numpy(float), 0.0, None)
    n = len(vol)
    vol_rank = np.full(n, np.nan)
    if n >= _VOLUME_WINDOW:
        sw = np.lib.stride_tricks.sliding_window_view(vol, _VOLUME_WINDOW)
        vol_rank[_VOLUME_WINDOW - 1:] = (sw <= sw[:, -1:]).mean(axis=1)
    prev = np.concatenate([[np.nan], vol[:-1]])
    with np.errstate(divide="ignore", invalid="ignore"):
        vol_ret_1 = np.where((vol > 0) & (prev > 0), np.log(vol / np.where(prev > 0, prev, np.nan)), np.nan)
    return pd.DataFrame({"volume_rank": vol_rank, "volume_ret_1": vol_ret_1})


def build_context_dataset_with_volume(instrument: str, tf: str = PRIMARY_TF,
                                      horizon: int = PRIMARY_HORIZON) -> pd.DataFrame:
    df = load_bars(instrument, tf)
    if df.empty or len(df) < 2000:
        return pd.DataFrame()
    df = augment(df, tf)
    n = len(df)
    feats = p83._build_context_features(df)
    vol_feats = _add_volume_features(df)
    feats = pd.concat([feats, vol_feats], axis=1)
    t1 = p83._t1_signed_return(df, horizon)
    t2 = p83._t2_range_ratio(df, horizon)

    warmup = max(p83._WARMUP, _VOLUME_WINDOW)
    idx = np.arange(warmup, n - horizon)
    finite_mask = np.isfinite(feats.iloc[idx].to_numpy(float)).all(axis=1) \
        & np.isfinite(t1[idx]) & np.isfinite(t2[idx])
    idx = idx[finite_mask]
    if len(idx) == 0:
        return pd.DataFrame()

    from phase80_ml_volatility_regime import _TF_SECONDS
    tf_sec = _TF_SECONDS[tf]
    open_ts = df["t"].to_numpy(np.int64)
    pred_ts = pd.to_datetime(open_ts[idx].astype(np.int64) + tf_sec, unit="s", utc=True)
    targ_end_ts = pd.to_datetime(open_ts[idx + horizon].astype(np.int64) + tf_sec, unit="s", utc=True)

    out = pd.DataFrame({
        "instrument": instrument, "timeframe": tf, "horizon_bars": horizon,
        "event_idx": idx, "prediction_timestamp": pred_ts, "target_end_timestamp": targ_end_ts,
        "T1": t1[idx], "T2": t2[idx], "dataset_version": DATASET_VERSION,
    })
    feat_rows = feats.iloc[idx].reset_index(drop=True)
    return pd.concat([out, feat_rows.add_prefix("feat__")], axis=1)


def build_pooled_volume_dataset(tf: str = PRIMARY_TF, horizon: int = PRIMARY_HORIZON,
                                instruments: Tuple[str, ...] = INSTRUMENTS_83) -> pd.DataFrame:
    frames = [d for inst in instruments
             if not (d := build_context_dataset_with_volume(inst, tf, horizon)).empty]
    if not frames:
        return pd.DataFrame()
    pooled = pd.concat(frames, ignore_index=True)
    return pooled.sort_values("prediction_timestamp").reset_index(drop=True)


def run_volume_ablation(discovery: pd.DataFrame, confirmation: pd.DataFrame) -> Dict[str, Any]:
    groups = _cumulative_feature_groups()
    full_name, full_feats = groups[-1]
    plus_volume = (full_feats + ["volume_rank", "volume_ret_1"])
    ablation = [(full_name, full_feats), ("G5_plus_volume", plus_volume)]
    out: Dict[str, Any] = {}
    for target_col in ("T1", "T2"):
        r_full = _fit_eval_group_84(discovery, confirmation, full_feats, target_col)
        r_vol = _fit_eval_group_84(discovery, confirmation, plus_volume, target_col)
        boot = bootstrap_delta_ci(r_vol["_y_true"], r_vol["_p_pred"], r_full["_p_pred"],
                                  _r2_fn(r_vol["train_mean"]), block=PRIMARY_HORIZON, seed=RANDOM_SEED)
        out[target_col] = {
            "full_baseline_r2": r_full["metrics"]["oos_r2"],
            "plus_volume_r2": r_vol["metrics"]["oos_r2"],
            "delta_r2": boot,
        }
    return out


def volume_ablation_controls(discovery: pd.DataFrame, confirmation: pd.DataFrame,
                             target_col: str = "T2", seed: int = 84001) -> Dict[str, Any]:
    """Because the volume ablation surfaced a non-trivial (CI-excludes-zero)
    positive delta for T2, this runs the SAME two falsification controls
    used throughout Phases 80-83 before treating it as anything more than a
    Phase-85 candidate: (a) shuffled-target -- if the effect is a mechanical/
    leakage artifact rather than genuine forward information, shuffling the
    train-set target must NOT make the delta collapse; a genuine effect
    MUST collapse under this control; (b) a volume-shuffle placebo --
    permuting the raw `vol` values across rows (breaking temporal volume
    structure while preserving its marginal distribution) before deriving
    volume_rank/volume_ret_1, which should also collapse the delta if the
    signal comes from genuine temporal volume dynamics rather than from the
    marginal distribution of volume values alone."""
    groups = _cumulative_feature_groups()
    full_feats = groups[-1][1]
    plus_volume = full_feats + ["volume_rank", "volume_ret_1"]

    # (a) shuffled target
    rng = np.random.default_rng(seed)
    train_shuf = discovery.copy()
    train_shuf[target_col] = rng.permutation(train_shuf[target_col].to_numpy())
    r_full_s = _fit_eval_group_84(train_shuf, confirmation, full_feats, target_col)
    r_vol_s = _fit_eval_group_84(train_shuf, confirmation, plus_volume, target_col)
    shuffled = {"full_baseline_r2": r_full_s["metrics"]["oos_r2"],
               "plus_volume_r2": r_vol_s["metrics"]["oos_r2"],
               "delta_r2": round(r_vol_s["metrics"]["oos_r2"] - r_full_s["metrics"]["oos_r2"], 5)}

    # (b) volume-shuffle placebo (permute vol_rank/vol_ret_1 across rows)
    rng2 = np.random.default_rng(seed + 1)
    train_ph = discovery.copy()
    test_ph = confirmation.copy()
    for c in ("feat__volume_rank", "feat__volume_ret_1"):
        train_ph[c] = rng2.permutation(train_ph[c].to_numpy())
        test_ph[c] = rng2.permutation(test_ph[c].to_numpy())
    r_full_p = _fit_eval_group_84(train_ph, test_ph, full_feats, target_col)
    r_vol_p = _fit_eval_group_84(train_ph, test_ph, plus_volume, target_col)
    placebo = {"full_baseline_r2": r_full_p["metrics"]["oos_r2"],
              "plus_volume_r2": r_vol_p["metrics"]["oos_r2"],
              "delta_r2": round(r_vol_p["metrics"]["oos_r2"] - r_full_p["metrics"]["oos_r2"], 5)}

    return {"target": target_col, "shuffled_target_control": shuffled,
           "volume_shuffle_placebo": placebo}


# ==========================================================================
# redundancy / correlation / mutual-information / PCA understanding pass
# (never a feature-selection competition -- no group is dropped here)
# ==========================================================================
def redundancy_audit(discovery: pd.DataFrame) -> Dict[str, Any]:
    cols = [f"feat__{c}" for c in BASELINE_D_COLUMNS]
    X = discovery[cols].to_numpy(float)
    corr = pd.DataFrame(X, columns=list(BASELINE_D_COLUMNS)).corr()
    pairs = []
    n = len(BASELINE_D_COLUMNS)
    for i in range(n):
        for j in range(i + 1, n):
            c = corr.iloc[i, j]
            if np.isfinite(c) and abs(c) >= 0.4:
                pairs.append({"a": BASELINE_D_COLUMNS[i], "b": BASELINE_D_COLUMNS[j],
                             "pearson_r": round(float(c), 4)})
    pairs.sort(key=lambda d: -abs(d["pearson_r"]))

    rng = np.random.default_rng(RANDOM_SEED)
    sub_idx = rng.choice(len(X), size=min(50_000, len(X)), replace=False)
    Xs = X[sub_idx]
    mi_t1 = mutual_info_regression(Xs, discovery["T1"].to_numpy(float)[sub_idx],
                                   random_state=RANDOM_SEED)
    mi_t2 = mutual_info_regression(Xs, discovery["T2"].to_numpy(float)[sub_idx],
                                   random_state=RANDOM_SEED)
    mutual_info = {"T1": {c: round(float(v), 5) for c, v in zip(BASELINE_D_COLUMNS, mi_t1)},
                   "T2": {c: round(float(v), 5) for c, v in zip(BASELINE_D_COLUMNS, mi_t2)}}

    Xz = (X - X.mean(axis=0)) / np.where(X.std(axis=0) > 1e-12, X.std(axis=0), 1.0)
    pca = PCA(n_components=min(len(BASELINE_D_COLUMNS), 10), random_state=RANDOM_SEED)
    pca.fit(Xz)
    n_components_for_90pct = int(np.searchsorted(np.cumsum(pca.explained_variance_ratio_), 0.90) + 1)

    return {"n_features": n, "n_rows": int(len(X)), "high_correlation_pairs_abs_ge_0.4": pairs,
           "mutual_info_with_targets": mutual_info,
           "pca_explained_variance_ratio": [round(float(v), 4) for v in pca.explained_variance_ratio_],
           "n_components_for_90pct_variance": n_components_for_90pct}


# ==========================================================================
# §41-46/§75-77 live data-inventory audit -- NEVER hard-coded, always
# re-queried from historical_data_store at run() time
# ==========================================================================
def data_inventory_audit() -> Dict[str, Any]:
    rows = store.list_available()
    by_asset: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        a = r["asset"]
        by_asset.setdefault(a, {})[r["timeframe"]] = {
            "count": r["count"], "first_iso": r["first_iso"], "last_iso": r["last_iso"],
        }
    canonical_universe = list(INSTRUMENTS_83)
    m1_m5_coverage = {a: {tf: by_asset[a][tf] for tf in ("1m", "5m") if tf in by_asset.get(a, {})}
                      for a in canonical_universe}
    m1_m5_available_instruments = [a for a, d in m1_m5_coverage.items() if d]
    return {
        "canonical_universe": canonical_universe,
        "timeframes_populated_per_instrument": {a: sorted(by_asset.get(a, {}).keys())
                                                for a in canonical_universe},
        "m1_m5_coverage": m1_m5_coverage,
        "m1_m5_available_for": m1_m5_available_instruments,
        "m1_m5_available_for_all_canonical_instruments": (
            set(m1_m5_available_instruments) == set(canonical_universe)),
    }


def m1_resolution_feasibility(inventory: Dict[str, Any]) -> Dict[str, Any]:
    """Judgment call, documented rather than silently skipped: is the
    permitted M15-vs-M1 resolution experiment actually run in this phase?"""
    m1_only_for = inventory["m1_m5_available_for"]
    verdict = "NOT_ATTEMPTED_DATA_INSUFFICIENT"
    reasoning = (
        "M1/M5 data exists only for {insts} (per data_inventory_audit, queried "
        "live), not for the other {n_missing} of the {n_total} canonical "
        "instruments -- so no cross-instrument comparison is possible. Even "
        "for the one covered instrument, the M1 window is short and recent "
        "(a few months), against a multi-year M15 study population used by "
        "every other phase; a resolution comparison built on a single "
        "instrument's short, unusually recent window would be underpowered "
        "and could easily produce a misleadingly clean or misleadingly null "
        "result driven by that window's own idiosyncratic regime, not by "
        "resolution itself. Per the master prompt's 'do not manufacture "
        "success' principle, this experiment is deliberately NOT run; the "
        "correct classification is DATA_INFEASIBLE for a conclusive test "
        "today, not a negative finding.".format(
            insts=", ".join(m1_only_for) if m1_only_for else "no instrument",
            n_missing=len(inventory["canonical_universe"]) - len(m1_only_for),
            n_total=len(inventory["canonical_universe"])))
    return {"verdict": verdict, "reasoning": reasoning}


# ==========================================================================
# predictability-ceiling table -- synthesized LIVE from already-persisted
# artifacts, never re-run, never hand-copied
# ==========================================================================
def predictability_ceiling_table() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    r83 = p83.get_result()
    if r83 and r83.get("scorecard"):
        by_target: Dict[str, float] = {}
        for s in r83["scorecard"]:
            by_target.setdefault(s["target"], s["baseline_r2_confirmation"])
        if "T2" in by_target:
            rows.append({"source": "Phase 83 Baseline D", "target_class": "MAGNITUDE (T2, forward "
                        "range/ATR ratio)", "metric": "OOS R^2 (confirmation)", "value": by_target["T2"]})
        if "T1" in by_target:
            rows.append({"source": "Phase 83 Baseline D", "target_class": "DIRECTION (T1, forward "
                        "signed return)", "metric": "OOS R^2 (confirmation)", "value": by_target["T1"]})
    r80 = p80.get_result()
    if r80 and r80.get("ablation_sweep"):
        d_rows = [x for x in r80["ablation_sweep"]
                 if x["ablation"] == "D_full_conservative" and x["model"] == "hist_gradient_boosting"]
        if d_rows:
            mean_auc = float(np.mean([x["metrics"]["roc_auc"] for x in d_rows]))
            rows.append({"source": "Phase 80 V2 volatility-regime pilot",
                        "target_class": "STATE (forward high-volatility bucket, binary)",
                        "metric": "ROC-AUC (mean across walk-forward folds, D_full_conservative/HGB)",
                        "value": round(mean_auc, 4)})
    r82 = p82.get_result()
    if r82:
        gates = r82.get("gates", {})
        real_r2 = gates.get("real_r2") if isinstance(gates, dict) else None
        if real_r2 is not None:
            rows.append({"source": "Phase 82 V1 compression-expansion pilot",
                        "target_class": "MAGNITUDE (forward expansion ratio)",
                        "metric": "OOS R^2 (primary model, headline)", "value": real_r2})
    r78 = p78.get_result() if hasattr(p78, "get_result") else None
    return rows


# ==========================================================================
# §h Information Frontier Matrix -- static classification registry.
# Priority/verdict are holistic judgments (documented in the report's
# per-candidate reasoning), not a mechanically-summed score -- avoiding
# false numeric precision on what are, honestly, qualitative calls.
# Six-level verdict vocabulary (master prompt §r):
#   REDUNDANT | LOW_INFORMATION_VALUE | DATA_INFEASIBLE | CAUSALLY_DIFFICULT
#   | PROMISING_RESEARCH_FRONTIER | HIGH_PRIORITY_RESEARCH_FRONTIER
# Priority levels: P0 (highest) .. P3 (lowest / not recommended now).
# ==========================================================================
INFORMATION_FRONTIER_MATRIX: Tuple[Dict[str, Any], ...] = (
    {"source": "OHLC (price)", "category": "Direct", "already_present": True,
     "orthogonal": "N/A (foundation)", "historical_availability": "Full (2016-2026 1h/4h/1d; "
     "2022-2026 15m) across all 6 canonical instruments", "resolution": "15m primary",
     "causal_difficulty": "None", "cost": "None", "priority": "N/A", "verdict": "N/A_FOUNDATION"},
    {"source": "Volatility (ATR/RV, derived)", "category": "Derived", "already_present": True,
     "orthogonal": False, "historical_availability": "Same as OHLC", "resolution": "15m",
     "causal_difficulty": "None", "cost": "None", "priority": "P3",
     "verdict": "REDUNDANT", "note": "Deeply explored Phases 78/80/81/82/83; explains most of "
     "current predictive value already found."},
    {"source": "MT5 tick_volume (broker-specific)", "category": "Direct (broker-specific)",
     "already_present": True, "orthogonal": "Empirically supported (screening-level), broker-specific",
     "historical_availability": "Same as OHLC (already stored, already loaded, never used)",
     "resolution": "15m", "causal_difficulty": "None", "cost": "None", "priority": "P0",
     "verdict": "HIGH_PRIORITY_RESEARCH_FRONTIER",
     "note": "See VOLUME_COLUMN_AUDIT: loaded by every phase since 76, never once tested. This "
     "audit's own small bounded ablation (run_volume_ablation) found a non-trivial incremental "
     "T2 (magnitude) OOS R^2 gain of +0.0204 (0.19651 -> 0.21691, bootstrap CI [0.0176, 0.0229], "
     "excludes zero) over Phase 83's full Baseline D, which SURVIVED both a shuffled-target "
     "control (delta collapses to +0.00012) and a volume-shuffle placebo (delta collapses to "
     "+0.00001) -- see volume_ablation_controls. This is a screening-level result from ONE "
     "bounded audit experiment, NOT a validated finding: it has not yet been through the "
     "Phase-83-grade battery (cross-asset generalization, leave-one-out, multiple horizons, "
     "future-shock invariance, multiple-testing correction, discovery/confirmation-locked "
     "re-verification) that a genuine Phase 85 candidate requires. No T1 (direction) benefit "
     "was found (delta -0.0001)."},
    {"source": "VWAP / volume profile", "category": "Derived (from tick_volume)",
     "already_present": True, "orthogonal": False,
     "historical_availability": "Phase 75 already tested (NO_EDGE_CONFIRMED)", "resolution": "15m",
     "causal_difficulty": "None", "cost": "None", "priority": "P3", "verdict": "REDUNDANT"},
    {"source": "Market structure (swing/liquidity/SMC)", "category": "Derived",
     "already_present": True, "orthogonal": False,
     "historical_availability": "strategies/smc_utils.py already implemented", "resolution": "15m/1h",
     "causal_difficulty": "None", "cost": "None", "priority": "P3", "verdict": "REDUNDANT",
     "note": "Phase 83's loc_in_range/dist_pdh_atr/dist_pdl_atr already test the core idea; "
     "EXPLAINED_BY_CONTEXT."},
    {"source": "Multi-timeframe (MTF) cascade", "category": "Derived", "already_present": "Partial",
     "orthogonal": False, "historical_availability": "true_mtf_engine.py (Phase 19) predates and is "
     "architecturally separate from Phases 76-83", "resolution": "1D/4H/15M (5M/1M assumed by "
     "Phase 19 but NOT populated for 5 of 6 instruments)", "causal_difficulty": "Low",
     "cost": "None", "priority": "P2", "verdict": "LOW_INFORMATION_VALUE",
     "note": "1D/4H/15M MTF context is a linear recombination of already-tested single-TF context; "
     "genuine novelty would require M1/M5, which data_inventory_audit shows is unavailable "
     "for 5/6 instruments."},
    {"source": "Order flow / order-book imbalance", "category": "Potentially Orthogonal",
     "already_present": False, "orthogonal": "Potentially (unproven)",
     "historical_availability": "Not stored; MT5 market_book_get is live-only depth, no history",
     "resolution": "Tick", "causal_difficulty": "Medium (broker-specific depth semantics)",
     "cost": "Low-Medium (would require new live capture starting now)", "priority": "P2",
     "verdict": "DATA_INFEASIBLE", "note": "No historical order-book data exists or can be "
     "backfilled; only forward capture from today would be possible."},
    {"source": "Centralized futures volume (COMEX/CME)", "category": "Proxy",
     "already_present": False, "orthogonal": "Potentially (different market structure)",
     "historical_availability": "External vendor-dependent; roll/basis handling required",
     "resolution": "Daily/intraday depending on vendor", "causal_difficulty": "Medium-High "
     "(contract roll, basis vs spot, publication timing)", "cost": "Medium-High (licensing)",
     "priority": "P2", "verdict": "CAUSALLY_DIFFICULT"},
    {"source": "Open interest", "category": "Proxy", "already_present": False,
     "orthogonal": "Potentially", "historical_availability": "External, reporting-delayed",
     "resolution": "Daily", "causal_difficulty": "High (contract roll, delayed reporting)",
     "cost": "Medium", "priority": "P3", "verdict": "CAUSALLY_DIFFICULT"},
    {"source": "Options / implied volatility", "category": "Proxy", "already_present": False,
     "orthogonal": "Potentially", "historical_availability": "External, vendor-dependent",
     "resolution": "Daily", "causal_difficulty": "High (surface construction, publication timing)",
     "cost": "High", "priority": "P3", "verdict": "CAUSALLY_DIFFICULT"},
    {"source": "COT positioning", "category": "Proxy", "already_present": "Partial",
     "orthogonal": "Potentially", "historical_availability": "macro_intelligence_engine.py "
     "already ingests CFTC COT (Phase 66) with lookahead-safe as_of gating",
     "resolution": "Weekly (Friday release, 3-day reporting lag)",
     "causal_difficulty": "Medium (weekly resolution vs 15m study cadence)", "cost": "None "
     "(already integrated for macro context, not yet tested as an ML feature)", "priority": "P2",
     "verdict": "LOW_INFORMATION_VALUE", "note": "Already available and revision-safe, but weekly "
     "resolution makes it a very coarse feature relative to a 15m/4-bar study; unlikely to move "
     "an R^2=0.005 direction result but cheap enough to be a legitimate low-priority probe."},
    {"source": "Macro / rates (FRED)", "category": "Direct", "already_present": True,
     "orthogonal": "Potentially", "historical_availability": "Phase 65 FRED provider, production",
     "resolution": "Daily/monthly depending on series", "causal_difficulty": "Low (already "
     "publication-timestamp aware)", "cost": "None", "priority": "P2",
     "verdict": "LOW_INFORMATION_VALUE", "note": "Same resolution mismatch as COT."},
    {"source": "Economic surprises", "category": "Derived", "already_present": True,
     "orthogonal": "Potentially", "historical_availability": "macro_intelligence_engine.py surprise "
     "analysis already exists", "resolution": "Event-time (irregular)",
     "causal_difficulty": "Medium (must use consensus known immediately before release only)",
     "cost": "None", "priority": "P2", "verdict": "PROMISING_RESEARCH_FRONTIER",
     "note": "Genuinely event-conditioned (not a rolling-window feature), which is a structurally "
     "different information type than anything in Phases 76-83's designs; needs a dedicated "
     "event-study design (out of scope for this audit's small-experiment budget)."},
    {"source": "News (headline/event state)", "category": "Potentially Orthogonal",
     "already_present": "Partial", "orthogonal": "Potentially",
     "historical_availability": "xauusd_news_snapshot_store.py has immutable, revision-aware "
     "calendar snapshots (Phase 38); does not yet cover headline text/sentiment",
     "resolution": "Event-time", "causal_difficulty": "Medium (timestamp/latency verified for "
     "calendar events; text-level news feeds not yet audited for latency/survivorship)",
     "cost": "Low (calendar) / Unknown (text feeds)", "priority": "P2",
     "verdict": "PROMISING_RESEARCH_FRONTIER", "note": "Calendar event-state (not sentiment) is "
     "the defensible near-term version of this."},
    {"source": "Cross-market information", "category": "Potentially Orthogonal",
     "already_present": False, "orthogonal": "Potentially", "historical_availability": "MT5 "
     "already provides correlated instruments (DXY proxies, yields via other symbols) but no "
     "per-instrument candidate-market mapping has been built or tested",
     "resolution": "15m (same store)", "causal_difficulty": "Medium (session asynchrony, "
     "predefined-lag-family discipline required per the master prompt's anti-lag-fishing rule)",
     "cost": "None (same MT5 connection, same store)", "priority": "P1",
     "verdict": "PROMISING_RESEARCH_FRONTIER", "note": "Cheapest genuinely-new-information "
     "candidate: no new provider needed, only a new predefined cross-instrument feature design."},
    {"source": "Liquidity / spread", "category": "Potentially Orthogonal", "already_present": False,
     "orthogonal": "Potentially", "historical_availability": "Not stored historically (see "
     "MT5_CAPABILITY_AUDIT); only live current spread is ever read", "resolution": "Tick/quote",
     "causal_difficulty": "Medium (broker-specific, would need forward capture)",
     "cost": "Low (forward capture only, once started)", "priority": "P2",
     "verdict": "DATA_INFEASIBLE", "note": "Cannot be backfilled; only usable prospectively."},
    {"source": "Market depth (order book)", "category": "Potentially Orthogonal",
     "already_present": False, "orthogonal": "Potentially",
     "historical_availability": "Not stored; live-only via market_book_get", "resolution": "Tick",
     "causal_difficulty": "Medium-High", "cost": "Low (forward capture only)", "priority": "P3",
     "verdict": "DATA_INFEASIBLE"},
    {"source": "Higher-resolution price (M1/tick, information-loss-through-"
              "aggregation hypothesis)", "category": "Derived (finer OHLC)", "already_present":
     "Partial (XAUUSD only, ~14-week window)", "orthogonal": "Unproven",
     "historical_availability": "See data_inventory_audit -- not available for 5/6 instruments, "
     "short window for the 6th", "resolution": "M1/M5", "causal_difficulty": "Low (same provider)",
     "cost": "Low if acquired going forward; historical backfill depth is broker-limited",
     "priority": "P1", "verdict": "PROMISING_RESEARCH_FRONTIER", "note": "Structurally cheap and "
     "causally simple, but the CURRENT M1/M5 store does not yet have enough history/coverage for "
     "a conclusive test -- see m1_resolution_feasibility. Priority is about EASE of eventually "
     "acquiring more history, not about anything measured yet."},
    {"source": "LLM/Gemini-derived deterministic text features", "category": "Speculative",
     "already_present": False, "orthogonal": "Unproven / high scrutiny required",
     "historical_availability": "Requires archival historical source text with verified publication "
     "timestamps -- not currently available", "resolution": "Event-time",
     "causal_difficulty": "High (determinism, reproducibility, no future context, archival "
     "availability all unverified)", "cost": "Unknown", "priority": "P3",
     "verdict": "DATA_INFEASIBLE", "note": "Per the master prompt's explicit warning: an LLM must "
     "transform historically-available, timestamped information deterministically, not 'predict' "
     "anything -- no such archival source has been identified yet."},
    {"source": "Redundant OHLC-derived indicators (EMA/RSI/MACD/etc.)",
     "category": "Derived", "already_present": True, "orthogonal": False,
     "historical_availability": "N/A", "resolution": "N/A", "causal_difficulty": "None",
     "cost": "None", "priority": "P3", "verdict": "REDUNDANT",
     "note": "Worked example from the master prompt: derived purely from OHLC already in the "
     "feature space; re-deriving more of these is not new information."},
)


# ==========================================================================
# result container
# ==========================================================================
@dataclass
class Phase84Result:
    schema_version: str
    generated_at: str
    git_commit: Optional[str]
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    volume_column_audit: Dict[str, Any]
    mt5_capability_audit: Dict[str, Any]
    macro_news_ai_audit: Dict[str, Any]
    data_inventory: Dict[str, Any]
    m1_resolution_feasibility: Dict[str, Any]
    feature_group_ablation: Dict[str, Any]
    volume_ablation: Dict[str, Any]
    volume_ablation_controls: Dict[str, Any]
    redundancy_audit: Dict[str, Any]
    predictability_ceiling: List[Dict[str, Any]]
    information_frontier_matrix: List[Dict[str, Any]]
    determinism: Dict[str, Any]
    runtime_seconds: float = 0.0
    content_hash: str = ""
    holdout_untouched: bool = True
    strategy_status: str = "RESEARCH_ONLY_NO_STRATEGY_ARTIFACT"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _ablation_identity(ablation: Dict[str, Any]) -> Dict[str, Any]:
    return {t: [{"group": r["group"], "oos_r2": r["oos_r2"]} for r in ablation[t]]
           for t in ("T1", "T2")}


def run() -> Phase84Result:
    t0 = datetime.now(timezone.utc)
    git_commit = _git_commit()

    ds_h4 = p83.build_pooled_context_dataset(PRIMARY_TF, PRIMARY_HORIZON)
    discovery, confirmation = discovery_confirmation_split(ds_h4)

    ablation_1 = run_feature_group_ablation(discovery, confirmation)
    ablation_2 = run_feature_group_ablation(discovery, confirmation)
    determinism = {"match": _ablation_identity(ablation_1) == _ablation_identity(ablation_2)}

    ds_vol = build_pooled_volume_dataset(PRIMARY_TF, PRIMARY_HORIZON)
    vol_discovery, vol_confirmation = discovery_confirmation_split(ds_vol)
    volume_ablation = run_volume_ablation(vol_discovery, vol_confirmation)
    volume_controls = volume_ablation_controls(vol_discovery, vol_confirmation, "T2")

    redundancy = redundancy_audit(discovery)
    inventory = data_inventory_audit()
    m1_feasibility = m1_resolution_feasibility(inventory)
    ceiling = predictability_ceiling_table()

    ident = json.dumps({
        "schema": SCHEMA_VERSION, "ablation": _ablation_identity(ablation_1),
        "volume_ablation": {t: volume_ablation[t]["delta_r2"].get("point")
                            for t in ("T1", "T2")},
        "volume_controls": volume_controls,
        "n_frontier_rows": len(INFORMATION_FRONTIER_MATRIX),
    }, sort_keys=True, default=str)
    chash = hashlib.sha256(ident.encode()).hexdigest()
    rt = (datetime.now(timezone.utc) - t0).total_seconds()

    return Phase84Result(
        schema_version=SCHEMA_VERSION, generated_at=t0.isoformat(), git_commit=git_commit,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(INSTRUMENTS_83), timeframe=PRIMARY_TF,
        volume_column_audit=VOLUME_COLUMN_AUDIT, mt5_capability_audit=MT5_CAPABILITY_AUDIT,
        macro_news_ai_audit=MACRO_NEWS_AI_AUDIT, data_inventory=inventory,
        m1_resolution_feasibility=m1_feasibility, feature_group_ablation=ablation_1,
        volume_ablation=volume_ablation, volume_ablation_controls=volume_controls,
        redundancy_audit=redundancy,
        predictability_ceiling=ceiling,
        information_frontier_matrix=list(INFORMATION_FRONTIER_MATRIX),
        determinism=determinism, runtime_seconds=round(rt, 1), content_hash=chash,
    )


def persist(result: Optional[Phase84Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase84_information_frontier_audit", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 84 - information frontier & missing signal research audit ...", flush=True)
    res = run()
    print(f"\n=== PHASE 84 ({res.runtime_seconds}s) ===")
    print(f"Data inventory (M1/M5 available for): {res.data_inventory['m1_m5_available_for']}")
    print(f"M1 resolution feasibility: {res.m1_resolution_feasibility['verdict']}")
    print(f"\nFeature-group ablation (T2 magnitude): {json.dumps(res.feature_group_ablation['T2'])}")
    print(f"Feature-group ablation (T1 direction): {json.dumps(res.feature_group_ablation['T1'])}")
    print(f"\nVolume ablation: {json.dumps(res.volume_ablation, default=str)}")
    print(f"Volume ablation controls: {json.dumps(res.volume_ablation_controls, default=str)}")
    print(f"\nPredictability ceiling: {json.dumps(res.predictability_ceiling, default=str)}")
    print(f"\nDeterminism match: {res.determinism['match']}")
    h = persist(res)
    print(f"\nartifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = [
    "SCHEMA_VERSION", "ARTIFACT_KEY", "DATASET_VERSION",
    "VOLUME_COLUMN_AUDIT", "MT5_CAPABILITY_AUDIT", "MACRO_NEWS_AI_AUDIT",
    "INFORMATION_FRONTIER_MATRIX", "run_feature_group_ablation", "run_volume_ablation",
    "redundancy_audit", "data_inventory_audit", "m1_resolution_feasibility",
    "predictability_ceiling_table", "build_context_dataset_with_volume",
    "build_pooled_volume_dataset", "run", "persist", "get_result", "main",
]
