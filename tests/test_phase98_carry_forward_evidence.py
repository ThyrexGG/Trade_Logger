# -*- coding: utf-8 -*-
"""
Phase 98 -- funding-carry forward-evidence harness.

Covers: the frozen go-live anchor and thresholds, the backtest/forward
split at the anchor, segment metrics, the TRACKING / DIVERGING /
CONFIRMING / INSUFFICIENT verdict tree, the immutable append-only
snapshot + running index, determinism, persistence, the read-only API
surface, and safety invariants (no execution/order/position import, no
holdout read, live flags unchanged). Phase 96's carry run is monkeypatched
with a synthetic weekly series; the real run is
``python -m phase98_carry_forward_evidence``.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import phase98_carry_forward_evidence as p98


def _carry_run(n_pre=200, n_fwd=0, fwd_funding_wk=0.002, seed=0):
    """Synthetic p96.run_carry output: n_pre weeks before the anchor, n_fwd
    after, with a controllable forward weekly funding level."""
    rng = np.random.default_rng(seed)
    anchor = pd.Timestamp(p98._GO_LIVE_DATE, tz="UTC")
    pre_idx = pd.date_range(end=anchor, periods=n_pre, freq="W-FRI")
    fwd_idx = pd.date_range(start=anchor + pd.Timedelta(weeks=1), periods=n_fwd, freq="W-FRI") if n_fwd else pd.DatetimeIndex([])
    idx = pre_idx.append(fwd_idx)
    n = len(idx)
    funding = np.concatenate([np.full(n_pre, 0.002), np.full(n_fwd, fwd_funding_wk)])
    basis = rng.normal(0, 0.0002, n)
    cost = np.full(n, -0.0002)
    net = funding + basis + cost
    return {"index": idx, "net": net, "funding": funding, "basis": basis, "cost": cost}


@pytest.fixture
def patch_carry(monkeypatch):
    state = {"run": _carry_run()}
    monkeypatch.setattr(p98.p96, "run_carry", lambda **kw: state["run"])
    monkeypatch.setattr(p98, "get_result", lambda: None)          # fresh history each test
    monkeypatch.setattr(p98.store, "save_artifact", lambda k, kind, payload: "h")
    return state


# --- A. frozen anchors -------------------------------------------------
def test_frozen_anchor_and_thresholds():
    assert p98._GO_LIVE_DATE == "2026-09-04"
    assert p98._RECOMMENDED_CARRY_FRACTION == 0.25
    assert p98._MIN_FORWARD_WEEKS_TO_ASSESS == 12
    assert p98._MIN_FORWARD_WEEKS_TO_CONFIRM == 26


# --- B. split at anchor --------------------------------------------
def test_ledger_splits_at_go_live_anchor(patch_carry):
    patch_carry["run"] = _carry_run(n_pre=180, n_fwd=20)
    led = p98.compute_ledger()
    assert led["backtest_reference"]["n_weeks"] == 180
    assert led["forward_evidence"]["n_weeks"] == 20
    # forward start is strictly after the anchor
    assert led["forward_evidence"]["start"] > p98._GO_LIVE_DATE
    assert led["recommended_book_forward"]["carry_fraction"] == 0.25


def test_recommended_book_forward_blends_carry_and_cash(patch_carry):
    patch_carry["run"] = _carry_run(n_pre=100, n_fwd=52, fwd_funding_wk=0.003)
    led = p98.compute_ledger()
    rb = led["recommended_book_forward"]
    assert rb["n_weeks"] == 52
    # 25% of a positive carry + 75% cash over a year -> a small positive cumulative
    assert 0.0 < rb["cumulative_return"] < 0.10


# --- C. verdict tree ---------------------------------------------
def test_verdict_insufficient_below_min_weeks(patch_carry):
    patch_carry["run"] = _carry_run(n_pre=200, n_fwd=5)
    v, _, comp = p98.classify_forward(p98.compute_ledger())
    assert v == "FORWARD_EVIDENCE_INSUFFICIENT"
    assert comp["forward_weeks"] == 5


def test_verdict_tracking_when_forward_matches_backtest(patch_carry):
    patch_carry["run"] = _carry_run(n_pre=200, n_fwd=16, fwd_funding_wk=0.002)
    v, _, _ = p98.classify_forward(p98.compute_ledger())
    assert v == "FORWARD_EVIDENCE_TRACKING"


def test_verdict_confirming_after_enough_tracking_weeks(patch_carry):
    patch_carry["run"] = _carry_run(n_pre=200, n_fwd=30, fwd_funding_wk=0.002)
    v, _, _ = p98.classify_forward(p98.compute_ledger())
    assert v == "FORWARD_EVIDENCE_CONFIRMING"


def test_verdict_diverging_when_forward_funding_collapses(patch_carry):
    patch_carry["run"] = _carry_run(n_pre=200, n_fwd=20, fwd_funding_wk=0.0002)  # ~10% of backtest
    v, reason, _ = p98.classify_forward(p98.compute_ledger())
    assert v == "FORWARD_EVIDENCE_DIVERGING"
    assert "do not deploy" in reason.lower()


def test_verdict_diverging_when_forward_sharpe_negative(patch_carry):
    run = _carry_run(n_pre=200, n_fwd=20, fwd_funding_wk=0.002)
    # make the forward net returns negative on average
    run["net"][-20:] = -0.003
    patch_carry["run"] = run
    v, _, _ = p98.classify_forward(p98.compute_ledger())
    assert v == "FORWARD_EVIDENCE_DIVERGING"


# --- D. snapshot ledger --------------------------------------
def test_append_snapshot_is_immutable_keyed_by_time(monkeypatch):
    saved = {}
    monkeypatch.setattr(p98.store, "save_artifact",
                        lambda k, kind, payload: saved.__setitem__(k, payload) or "h")
    led = p98.compute_ledger.__wrapped__ if hasattr(p98.compute_ledger, "__wrapped__") else None
    ledger = {"forward_evidence": {"n_weeks": 3}, "recommended_book_forward": {}, "data_through": "2026-09-11"}
    k1 = p98.append_snapshot(ledger, "FORWARD_EVIDENCE_INSUFFICIENT", {"forward_weeks": 3})
    assert k1.startswith(p98._SNAPSHOT_PREFIX)
    assert saved[k1]["verdict"] == "FORWARD_EVIDENCE_INSUFFICIENT"


def test_run_appends_to_prior_history(monkeypatch):
    monkeypatch.setattr(p98.p96, "run_carry", lambda **kw: _carry_run(n_pre=200, n_fwd=4))
    monkeypatch.setattr(p98.store, "save_artifact", lambda k, kind, payload: "h")
    monkeypatch.setattr(p98, "get_result",
                        lambda: {"snapshot_history": [{"snapshot_key": "old", "verdict": "X"}]})
    res = p98.run(do_refresh=False)
    assert len(res.snapshot_history) == 2
    assert res.snapshot_history[0]["snapshot_key"] == "old"


# --- E. determinism + persistence ---------------------------
def test_determinism(monkeypatch):
    monkeypatch.setattr(p98.p96, "run_carry", lambda **kw: _carry_run(n_pre=200, n_fwd=8))
    monkeypatch.setattr(p98.store, "save_artifact", lambda k, kind, payload: "h")
    monkeypatch.setattr(p98, "get_result", lambda: None)
    assert p98.run(do_refresh=False).determinism["match"] is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p98.store, "save_artifact",
                        lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h98")
                        if k == p98.ARTIFACT_KEY else "s")
    monkeypatch.setattr(p98.store, "load_artifact",
                        lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    res = p98.Phase98Result(
        schema_version=p98.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
        frozen_contract_hash="x", design_note={}, refresh={}, ledger={}, verdict="V", verdict_reason="",
        comparison={}, snapshot_key="s", snapshot_history=[], determinism={"match": True})
    assert p98.persist(res) == "h98"
    assert p98.get_result()["verdict"] == "V"


def test_result_reports_safety_flags():
    res = p98.Phase98Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="x", design_note={},
        refresh={}, ledger={}, verdict="x", verdict_reason="", comparison={}, snapshot_key="",
        snapshot_history=[], determinism={})
    d = res.to_dict()
    assert d["live_automation_enabled"] is False
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["holdout_untouched"] is True


# --- F. safety ---------------------------------------------
def test_module_never_imports_execution_or_reads_holdout():
    src = inspect.getsource(p98)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "execution_pipeline", "paper_simulator",
              "account_state", "account_management", "risk_engine", "positions"):
        assert not any(f in l for l in import_lines), f"forbidden import: {f}"
    for token in ("place_order", "submit_order", "execute_trade", "load_holdout", "locked_holdout"):
        assert token not in src


def test_frozen_contract_hash_is_the_canonical_constant():
    import gold_strategy_baseline as gsb
    assert gsb.get_gold_baseline().frozen_contract_hash == gsb.CANONICAL_CONTRACT_HASH


# --- G. API ----------------------------------------------
def test_api_endpoint_get_only_and_safe():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    r = client.get("/api/research/funding-carry-forward")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert body["safety_barrier"] == {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}
    assert client.post("/api/research/funding-carry-forward").status_code == 405
