# -*- coding: utf-8 -*-
"""
Research Diagnostic Matrix (auxiliary research tooling — predates the ORB/VWAP Phase 75).

Diagnosis of *why* the Phase-74 NO_VALIDATED_EDGE result holds: deterministic
segmentation, sample-size discipline, multiple-comparison accounting, temporal
stability, a candidate promotion gate, and hard evidence-governance (the frozen
holdout is never read).

Uses synthetic trade lists — no full backtest — so the suite stays fast.
"""
import importlib
import inspect

import pandas as pd
import pytest

import research_diagnostics as rd


def _trade(ts, r, is_oos=False, direction="BUY", session=None, liq="SWING_HIGH"):
    # a trade whose R == `r` given entry=100, sl=99, size=1  ->  risk = 1
    return {"entry_time": pd.Timestamp(ts, tz="UTC"), "entry_price": 100.0,
            "stop_loss": 99.0, "position_size": 1.0, "pnl": float(r),
            "is_oos": is_oos, "direction": direction, "session": session,
            "liquidity_type": liq}


# --- sample-size classification (§3) -----------------------------------
def test_sample_class_thresholds():
    assert rd.sample_class(0) == "INSUFFICIENT_SAMPLE"
    assert rd.sample_class(29) == "INSUFFICIENT_SAMPLE"
    assert rd.sample_class(30) == "EXPLORATORY"
    assert rd.sample_class(99) == "EXPLORATORY"
    assert rd.sample_class(100) == "UNCERTAIN"
    assert rd.sample_class(299) == "UNCERTAIN"
    assert rd.sample_class(300) == "ROBUST"
    assert rd.sample_class(50_000) == "ROBUST"


# --- deterministic segmentation (§2) ---------------------------------
def test_segmentation_functions_are_deterministic_and_pre_declared():
    t = _trade("2024-06-13 12:00", 1.0, direction="SELL", session="ASIA", liq="PDH")
    assert rd.SEGMENTATIONS["direction"](t) == "SHORT"
    assert rd.SEGMENTATIONS["session"](t) == "ASIA"          # trade's own valid session kept
    assert rd.SEGMENTATIONS["day_of_week"](t) == "Thu"       # 2024-06-13 is a Thursday
    assert rd.SEGMENTATIONS["liquidity_type"](t) == "PDH"
    assert rd.SEGMENTATIONS["year"](t) == "2024"
    assert rd.SEGMENTATIONS["is_oos_split"](t) == "IS"
    # every declared dimension has a documented rule
    assert set(rd.SEGMENTATIONS) == set(rd.SEGMENTATION_RULES_DOC)


def test_session_falls_back_to_utc_window_when_trade_session_missing():
    # 08:00 UTC with no trade session -> LONDON by the canonical window
    assert rd.SEGMENTATIONS["session"](_trade("2024-01-03 08:00", 0.0, session=None)) == "LONDON"
    assert rd.SEGMENTATIONS["session"](_trade("2024-01-03 02:00", 0.0, session="N/A")) == "ASIA"
    assert rd.SEGMENTATIONS["session"](_trade("2024-01-03 13:00", 0.0, session=None)) \
        == "LONDON_NY_OVERLAP"


# --- bucket stats + bootstrap CI (§3) --------------------------------
def test_bucket_stats_reports_n_ci_and_lower_bound():
    rs = [0.5, -1.0, 2.0, -1.0, 1.5, -1.0, 0.8, -1.0, 3.0, -1.0] * 12  # N=120
    s = rd._bucket_stats(rs, n_comparisons=50)
    assert s["n"] == 120
    assert s["sample_class"] == "UNCERTAIN"
    assert "ci_lower" in s and "ci_upper" in s
    assert "ci_lower_bonferroni" in s
    # a Bonferroni-widened interval is never tighter than the nominal one
    assert s["ci_lower_bonferroni"] <= s["ci_lower"] + 1e-9


def test_bucket_stats_deterministic():
    rs = [0.3, -1.0, 1.7, -1.0, 0.9] * 30
    a = rd._bucket_stats(rs, n_comparisons=17)
    b = rd._bucket_stats(rs, n_comparisons=17)
    assert a == b


def test_negative_bucket_is_flagged_negative():
    rs = [-1.0] * 40 + [0.2] * 10
    s = rd._bucket_stats(rs, n_comparisons=10)
    assert s["status"] == "NEGATIVE"


def test_insufficient_sample_never_promoted_as_positive():
    rs = [5.0, 4.0, 6.0]  # tiny but hugely positive mean
    s = rd._bucket_stats(rs, n_comparisons=10)
    assert s["status"] == "INSUFFICIENT_SAMPLE"


# --- temporal stability (§7) ----------------------------------------
def test_temporal_stability_is_chronological():
    # positive early, negative late -> not both halves positive
    pts = [(pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(days=i),
            1.0 if i < 50 else -1.0) for i in range(100)]
    ts = rd._temporal_stability(pts)
    assert ts["both_halves_positive"] is False
    assert ts["degradation"] < 0


def test_temporal_stability_positive_when_consistent():
    pts = [(pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(days=i),
            0.4 if i % 3 else -0.5) for i in range(120)]
    ts = rd._temporal_stability(pts)
    assert ts["both_halves_positive"] is True
    assert ts["positive_thirds"] == 3


# --- multiple-comparison accounting (§4) ----------------------------
def test_matrix_counts_comparisons_and_applies_bonferroni(monkeypatch):
    # stub run_pair so no backtest runs
    def _fake_run(asset, sid, tf):
        base = pd.Timestamp("2023-01-01", tz="UTC")
        trades = []
        for i in range(400):
            trades.append({"entry_time": base + pd.Timedelta(hours=6 * i),
                           "entry_price": 100.0, "stop_loss": 99.0, "position_size": 1.0,
                           "pnl": (0.6 if i % 2 else -1.0), "is_oos": i >= 280,
                           "direction": "BUY" if i % 2 else "SELL",
                           "session": None, "liquidity_type": "PDH",
                           "_r": (0.6 if i % 2 else -1.0),
                           "_regime": "TRENDING" if i % 2 else "RANGING"})
        return {"asset": asset, "strategy_id": sid, "strategy_family": "x", "timeframe": tf,
                "state": "AVAILABLE", "params": {}, "dataset_id": "d", "dataset_hash": "h",
                "coverage": {}, "n_trades": len(trades), "trades": trades}

    monkeypatch.setattr(rd, "run_pair", _fake_run)
    monkeypatch.setattr(rd.dataset_manifest, "get_manifest", lambda a: None, raising=False)
    m = rd.build_matrix("15m", assets=["XAUUSD"], strategies=["ict_2022_sweep_mss_fvg"])
    assert m.n_comparisons >= 5
    assert m.multiple_testing["bonferroni_alpha"] == round(0.05 / m.n_comparisons, 6)
    assert m.multiple_testing["expected_false_positives_at_0.05"] == round(0.05 * m.n_comparisons, 1)
    assert m.multiple_testing["risk_level"] in ("LOW", "MODERATE", "HIGH (DATA-MINING RISK)")
    # conclusion is one of the conservative classifications
    assert m.conclusion.startswith(("NO_EDGE_CONFIRMED", "EXPLORATORY_CANDIDATE"))


def test_promotion_gate_requires_every_criterion(monkeypatch):
    # a bucket that is positive but only in the first half -> must NOT promote
    def _fake_run(asset, sid, tf):
        base = pd.Timestamp("2022-01-01", tz="UTC")
        trades = []
        for i in range(600):
            early = i < 300
            r = 1.2 if (early and i % 2 == 0) else (-1.0 if early else (0.1 if i % 2 else -0.2))
            trades.append({"entry_time": base + pd.Timedelta(hours=4 * i),
                           "entry_price": 100.0, "stop_loss": 99.0, "position_size": 1.0,
                           "pnl": r, "is_oos": i >= 420, "direction": "BUY",
                           "session": "LONDON", "liquidity_type": "PDH",
                           "_r": r, "_regime": "TRENDING"})
        return {"asset": asset, "strategy_id": sid, "strategy_family": "x", "timeframe": tf,
                "state": "AVAILABLE", "params": {}, "dataset_id": "d", "dataset_hash": "h",
                "coverage": {}, "n_trades": len(trades), "trades": trades}

    monkeypatch.setattr(rd, "run_pair", _fake_run)
    monkeypatch.setattr(rd.dataset_manifest, "get_manifest", lambda a: None, raising=False)
    m = rd.build_matrix("15m", assets=["XAUUSD"], strategies=["ict_2022_sweep_mss_fvg"])
    assert m.promoted_candidates == []
    assert m.conclusion.startswith("NO_EDGE_CONFIRMED")


# --- evidence governance (§10) -------------------------------------
def test_module_never_reads_the_frozen_holdout():
    src = inspect.getsource(rd)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
                "HistoricalVsForwardComparator", "load_holdout", "read_holdout"):
        assert bad not in src


def test_no_execution_or_broker_imports():
    src = inspect.getsource(rd)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
                "order_execution", "live_trading", "live_automation"):
        assert bad not in src


def test_frozen_hash_recorded_and_unchanged(monkeypatch):
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"

    def _fake_run(asset, sid, tf):
        return {"asset": asset, "strategy_id": sid, "strategy_family": "x", "timeframe": tf,
                "state": "INSUFFICIENT_EVIDENCE", "reason": "stub", "trades": []}
    monkeypatch.setattr(rd, "run_pair", _fake_run)
    monkeypatch.setattr(rd.dataset_manifest, "get_manifest", lambda a: None, raising=False)
    m = rd.build_matrix("15m", assets=["XAUUSD"], strategies=["ict_2022_sweep_mss_fvg"])
    assert m.frozen_contract_hash == FROZEN_CONTRACT_HASH
    assert m.holdout_untouched is True


# --- reproducibility (§14) ----------------------------------------
def test_matrix_is_reproducible(monkeypatch):
    def _fake_run(asset, sid, tf):
        base = pd.Timestamp("2023-01-01", tz="UTC")
        trades = [{"entry_time": base + pd.Timedelta(hours=3 * i), "entry_price": 100.0,
                   "stop_loss": 99.0, "position_size": 1.0, "pnl": (0.5 if i % 3 else -1.0),
                   "is_oos": i >= 210, "direction": "BUY", "session": "LONDON",
                   "liquidity_type": "PDH", "_r": (0.5 if i % 3 else -1.0),
                   "_regime": "RANGING"} for i in range(300)]
        return {"asset": asset, "strategy_id": sid, "strategy_family": "x", "timeframe": tf,
                "state": "AVAILABLE", "params": {}, "dataset_id": "d", "dataset_hash": "h",
                "coverage": {}, "n_trades": 300, "trades": trades}

    monkeypatch.setattr(rd, "run_pair", _fake_run)
    monkeypatch.setattr(rd.dataset_manifest, "get_manifest", lambda a: None, raising=False)
    m1 = rd.build_matrix("15m", assets=["XAUUSD"], strategies=["ict_2022_sweep_mss_fvg"])
    m2 = rd.build_matrix("15m", assets=["XAUUSD"], strategies=["ict_2022_sweep_mss_fvg"])
    assert m1.rows == m2.rows
    assert m1.conclusion == m2.conclusion
    assert m1.n_comparisons == m2.n_comparisons


def test_diagnostics_module_imports_clean():
    importlib.reload(rd)
    assert hasattr(rd, "build_matrix") and hasattr(rd, "get_matrix")
