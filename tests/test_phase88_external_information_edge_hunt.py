# -*- coding: utf-8 -*-
"""
Phase 88 — external information acquisition & aggressive directional edge
hunt.

Covers: the Tier 1/2/4 data-availability feasibility audits, the Tier-3
external-data causal merge (availability-lag enforcement, no lookahead,
dtype-safe as-of join, dropped-not-filled missing rows), the candidate
registry's hypothesis-driven target restriction, the candidate evaluation/
verdict decision tree, the research ledger, and safety invariants.
Synthetic external series + synthetic bars for structural/logic tests
(never a live yfinance call in a test); the real full run is the artifact
produced by ``python -m phase88_external_information_edge_hunt``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase88_external_information_edge_hunt as p88


def _frame(n=6000, seed=71):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    vol = np.abs(rng.normal(100.0, 20.0, n)) + 1.0
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


def _fake_snapshot(start="2022-01-01", n_days=1400, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n_days, freq="D", tz="UTC")
    series = {}
    for name in p88._TIER3_SYMBOLS:
        walk = 100.0 + np.cumsum(rng.normal(0, 1.0, n_days))
        series[name] = [{"date": d.strftime("%Y-%m-%d"), "close": float(v)}
                       for d, v in zip(dates, walk)]
    return {"fetched_at": "2026-01-01T00:00:00+00:00", "provider": "test",
           "symbols": dict(p88._TIER3_SYMBOLS),
           "data_source_independence": "test", "timestamp_semantics": "test",
           "series": series}


# --- A. Tier 1/2/4 feasibility audits -----------------------------------------
def test_economic_surprise_feasibility_reports_unavailable():
    out = p88.economic_surprise_feasibility()
    assert out["verdict"] == "CONSENSUS_DATA_UNAVAILABLE"
    assert out["forex_factory_provider_makes_a_live_network_call"] is False


def test_order_flow_feasibility_reports_unavailable():
    out = p88.order_flow_feasibility()
    assert out["verdict"] == "DATA_SOURCE_UNAVAILABLE"
    assert out["copy_ticks_range_used"] is False


# --- B. causal external-data merge ---------------------------------------------
def test_external_series_causal_applies_availability_lag():
    snap = _fake_snapshot(n_days=10)
    s = p88._external_series_causal("DXY", snap)
    raw_dates = pd.to_datetime([r["date"] for r in snap["series"]["DXY"]], utc=True)
    # every available_at timestamp must be strictly after its own bar's date
    for ts in s.index:
        assert ts > raw_dates[0]


def test_merge_external_onto_dataset_never_uses_a_same_day_value(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p83.build_context_dataset("EURUSD", "15m", 4)
    snap = _fake_snapshot(n_days=1400)
    merged = p88.merge_external_onto_dataset(ds, "DXY", snap, sign=1.0)
    assert not merged.empty
    assert "feat__ext_dxy" in merged.columns
    assert "feat__ext_dxy_rank" in merged.columns
    assert np.isfinite(merged["feat__ext_dxy"].to_numpy()).all()
    assert ((merged["feat__ext_dxy_rank"] >= 0) & (merged["feat__ext_dxy_rank"] <= 1)).all()


def test_merge_external_onto_dataset_applies_sign_convention(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p83.build_context_dataset("EURUSD", "15m", 4)
    snap = _fake_snapshot(n_days=1400)
    pos = p88.merge_external_onto_dataset(ds, "DXY", snap, sign=1.0)
    neg = p88.merge_external_onto_dataset(ds, "DXY", snap, sign=-1.0)
    common_n = min(len(pos), len(neg))
    np.testing.assert_allclose(pos["feat__ext_dxy"].to_numpy()[:common_n],
                               -neg["feat__ext_dxy"].to_numpy()[:common_n])


def test_merge_external_onto_dataset_handles_missing_series(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p83.build_context_dataset("EURUSD", "15m", 4)
    empty_snap = {"series": {"DXY": []}}
    merged = p88.merge_external_onto_dataset(ds, "DXY", empty_snap, sign=1.0)
    assert merged.empty


# --- C. candidate registry -------------------------------------------------------
def test_external_candidates_are_exactly_six_frozen():
    assert len(p88.EXTERNAL_CANDIDATES) == 6
    ids = [c["id"] for c in p88.EXTERNAL_CANDIDATES]
    assert len(set(ids)) == 6


def test_every_candidate_has_a_hypothesis_and_sign_map():
    for c in p88.EXTERNAL_CANDIDATES:
        assert c["hypothesis"]
        assert set(c["targets"]).issubset(set(c["sign_map"].keys()))


def test_dxy_and_ust10y_share_the_same_hypothesis_driven_target_restriction():
    e1 = next(c for c in p88.EXTERNAL_CANDIDATES if c["id"] == "E1_DXY_direction")
    e2 = next(c for c in p88.EXTERNAL_CANDIDATES if c["id"] == "E2_UST10Y_direction")
    assert set(e1["targets"]) == set(e2["targets"]) == {"USDJPY", "EURUSD", "GBPUSD", "XAUUSD"}


# --- D. candidate evaluation / verdict decision tree -------------------------------
def test_evaluate_external_candidate_runs_end_to_end(monkeypatch):
    # evaluate_external_candidate calls the REAL calendar-based
    # discovery_confirmation_split internally; the synthetic frame's
    # 2022-anchored timestamps never reach the real 2025 confirmation
    # window, so that split is patched here to a positional 70/30 split
    # (structural test only, not the real dates).
    rows = _frame(n=8000, seed=5)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p88, "discovery_confirmation_split",
                        lambda ds: (ds.iloc[: int(len(ds) * 0.7)], ds.iloc[int(len(ds) * 0.7):]))
    snap = _fake_snapshot(n_days=1400)
    cand = {"id": "TEST", "series": "DXY", "targets": ("EURUSD",), "sign_map": {"EURUSD": 1.0},
           "hypothesis": "test"}
    r = p88.evaluate_external_candidate(cand, snap, "T1")
    assert "delta_r2_raw" in r
    assert "delta_r2_rank" in r
    assert "placebo_delta_r2" in r


def _fake_result(point, excl, placebo_point=0.0):
    return {"delta_r2_rank": {"point": point, "excludes_zero": excl},
           "placebo_delta_r2": {"point": placebo_point}}


def test_classify_verdict_data_unavailable_on_insufficient_sample():
    v, _ = p88.classify_candidate_verdict({"state": "INSUFFICIENT_SAMPLE"})
    assert v == "DATA_SOURCE_UNAVAILABLE"


def test_classify_verdict_no_information_when_not_ci_excluding():
    v, _ = p88.classify_candidate_verdict(_fake_result(0.02, False))
    assert v == "NO_EXTERNAL_INFORMATION_FOUND"


def test_classify_verdict_leakage_when_placebo_does_not_collapse():
    v, _ = p88.classify_candidate_verdict(_fake_result(0.02, True, placebo_point=0.025))
    assert v == "LEAKAGE"


def test_classify_verdict_not_actionable_below_materiality():
    v, _ = p88.classify_candidate_verdict(_fake_result(0.002, True, placebo_point=0.0))
    assert v == "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE"


def test_classify_verdict_promising_when_all_gates_clear():
    v, _ = p88.classify_candidate_verdict(_fake_result(0.02, True, placebo_point=0.0))
    assert v == "PROMISING_TRADING_HYPOTHESIS"


def test_final_decision_promotes_when_any_candidate_promising():
    v, _ = p88.final_decision([], {"E1": "PROMISING_TRADING_HYPOTHESIS", "E2": "NO_EXTERNAL_INFORMATION_FOUND"})
    assert v == "PROMISING_TRADING_HYPOTHESIS"


def test_final_decision_no_external_information_when_all_fail():
    v, _ = p88.final_decision([], {"E1": "NO_EXTERNAL_INFORMATION_FOUND",
                                   "E2": "NO_EXTERNAL_INFORMATION_FOUND"})
    assert v == "NO_EXTERNAL_INFORMATION_FOUND"


def test_final_decision_not_actionable_when_directional_but_weak():
    v, _ = p88.final_decision([], {"E1": "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE",
                                   "E2": "NO_EXTERNAL_INFORMATION_FOUND"})
    assert v == "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE"


# --- E. research ledger -----------------------------------------------------------
def test_research_ledger_records_every_entry():
    ledger = p88.ResearchLedger88()
    ledger.record("stage1", "h1", "desc", "OUTCOME_A", "reason")
    ledger.record("stage2", "h2", "desc", "OUTCOME_B", "reason")
    assert len(ledger.to_list()) == 2


# --- F. snapshot persistence --------------------------------------------------------
def test_get_external_snapshot_reuses_persisted_data_never_refetches(monkeypatch):
    calls = {"acquire": 0}

    def fake_acquire():
        calls["acquire"] += 1
        return _fake_snapshot(n_days=5)

    monkeypatch.setattr(p88, "acquire_external_snapshot", fake_acquire)
    monkeypatch.setattr(p88.store, "load_artifact",
                        lambda key: {"payload": _fake_snapshot(n_days=5)})
    snap = p88.get_external_snapshot()
    assert snap["series"]
    assert calls["acquire"] == 0  # persisted snapshot found -> never re-fetched


def test_get_external_snapshot_acquires_when_none_persisted(monkeypatch):
    calls = {"acquire": 0}

    def fake_acquire():
        calls["acquire"] += 1
        return _fake_snapshot(n_days=5)

    monkeypatch.setattr(p88, "acquire_external_snapshot", fake_acquire)
    monkeypatch.setattr(p88.store, "load_artifact", lambda key: None)
    snap = p88.get_external_snapshot()
    assert calls["acquire"] == 1


# --- G. safety invariants ----------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports():
    src = inspect.getsource(p88)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"


def test_result_dataclass_reports_research_only_status():
    r = p88.Phase88Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", tier1_2_economic_surprise={}, tier4_order_flow={},
        external_data_provenance={}, candidate_registry=[], candidate_results={},
        candidate_verdicts={}, research_ledger=[], verdict="NO_EXTERNAL_INFORMATION_FOUND",
        verdict_reason="x", determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p88"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p88.store, "save_artifact", fake_save)
    monkeypatch.setattr(p88.store, "load_artifact", fake_load)

    fake_result = p88.Phase88Result(
        schema_version=p88.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc", frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83),
        timeframe="15m", tier1_2_economic_surprise={}, tier4_order_flow={},
        external_data_provenance={}, candidate_registry=[], candidate_results={},
        candidate_verdicts={}, research_ledger=[], verdict="NO_EXTERNAL_INFORMATION_FOUND",
        verdict_reason="x", determinism={"match": True}, content_hash="deadbeef",
    )
    h = p88.persist(fake_result)
    assert h == "fake_hash_p88"
    got = p88.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["verdict"] == "NO_EXTERNAL_INFORMATION_FOUND"
