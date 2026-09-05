# -*- coding: utf-8 -*-
"""
Phase 97 -- portfolio construction & risk-of-ruin sizing.

Covers: frozen parameters, the weekly-cash conversion, annualised metrics,
the risk-of-ruin Monte-Carlo (collapse shocks scale with carry fraction,
severity, and inverse venue count; no-collapse cell has zero ruin), the
f* selection rule (ruin + early-loss constraints), the diversification
test (a negative-Sharpe uncorrelated sleeve does not "help"), the
usability verdict tree, determinism, persistence, the read-only API
surface, and safety invariants. Sleeve series are monkeypatched with
synthetic weekly returns; the real run is
``python -m phase97_portfolio_construction``.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import phase97_portfolio_construction as p97


# --------------------------------------------------------------------------
def _synthetic_frame(n=420, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-04", periods=n, freq="W-FRI")
    carry = rng.normal(0.0022, 0.006, n)          # ~ Sharpe 2.6, low vol
    cmom = rng.normal(0.0006, 0.02, n)            # ~ Sharpe 0.2
    fxmom = rng.normal(-0.0009, 0.02, n)          # ~ Sharpe -0.3
    dep = np.full(n, 0.71)
    return pd.DataFrame({"carry": carry, "carry_deployed": dep, "cmom": cmom, "fxmom": fxmom}, index=idx)


@pytest.fixture
def synthetic_series(monkeypatch):
    frame = _synthetic_frame()
    monkeypatch.setattr(p97, "_sleeve_series",
                        lambda: {"frame": frame, "start": frame.index[0].date().isoformat(),
                                 "end": frame.index[-1].date().isoformat(), "n_weeks": len(frame)})
    return frame


# --- A. frozen params ---------------------------------------------------
def test_frozen_parameters():
    assert p97._CASH_ANNUAL == 0.02
    assert p97._RUIN_LEVEL == 0.70 and p97._SEVERE_RUIN_LEVEL == 0.50
    assert p97._RUIN_THRESHOLD == 0.05
    assert p97._PLANNING_PROB == 0.04 and p97._PLANNING_N_VENUES == 2
    assert p97._MAX_SINGLE_VENUE_LOSS_OF_BOOK == 0.12
    assert abs(sum(w for _, w in p97._PLANNING_SEV_MIX) - 1.0) < 1e-9


def test_weekly_cash_compounds_to_annual():
    assert abs((1.0 + p97._weekly_cash()) ** 52 - 1.02) < 1e-6


# --- B. Monte-Carlo mechanics ----------------------------------------
def test_no_collapse_cell_has_zero_ruin(synthetic_series):
    df = synthetic_series
    r = p97._simulate_paths(df["carry"].to_numpy(float), df["carry_deployed"].to_numpy(float),
                            np.zeros(len(df)), 0.30, 0.0, 0.0, 1.0, 1, 500,
                            np.random.default_rng(0))
    assert (r["final_equity"] > 1.0).all()          # carry + cash, no shock -> always up
    assert p97._summarize(r)["prob_ruin"] == 0.0


def test_collapse_damage_scales_with_fraction_and_severity(synthetic_series):
    df = synthetic_series
    cw, dep, z = df["carry"].to_numpy(float), df["carry_deployed"].to_numpy(float), np.zeros(len(df))
    lo = p97._simulate_paths(cw, dep, z, 0.15, 0.0, 0.10, 1.0, 1, 3000, np.random.default_rng(1))
    hi = p97._simulate_paths(cw, dep, z, 0.45, 0.0, 0.10, 1.0, 1, 3000, np.random.default_rng(1))
    assert p97._summarize(hi)["prob_ruin"] >= p97._summarize(lo)["prob_ruin"]
    # more venues -> each collapse smaller -> less ruin
    few = p97._simulate_paths(cw, dep, z, 0.45, 0.0, 0.10, 1.0, 1, 3000, np.random.default_rng(2))
    many = p97._simulate_paths(cw, dep, z, 0.45, 0.0, 0.10, 1.0, 3, 3000, np.random.default_rng(2))
    assert p97._summarize(many)["prob_ruin"] <= p97._summarize(few)["prob_ruin"]


def test_optimal_carry_fraction_respects_single_venue_cap(synthetic_series):
    oc = p97.optimal_carry_fraction(p97._sleeve_series())
    fs = oc["f_star"]
    assert fs in p97._CARRY_FRACTION_GRID or fs == 0.0
    if fs > 0:
        s = oc["by_fraction"][f"f{fs:.2f}"]
        assert s["single_venue_loss_of_book"] <= p97._MAX_SINGLE_VENUE_LOSS_OF_BOOK
    # every larger grid fraction must exceed the single-venue cap
    for f in [f for f in p97._CARRY_FRACTION_GRID if f > fs]:
        assert oc["by_fraction"][f"f{f:.2f}"]["single_venue_loss_of_book"] > p97._MAX_SINGLE_VENUE_LOSS_OF_BOOK


# --- C. diversification --------------------------------------------
def test_negative_sharpe_sleeve_does_not_help(synthetic_series):
    div = p97.diversification_analysis(p97._sleeve_series(), 0.25)
    # fxmom is negative-Sharpe by construction -> must not be marked as helping
    assert div["carry_plus_fxmom"]["helps_vs_cash"] is False
    assert div["standalone_sleeve_sharpe"]["fxmom"] < 0


# --- D. verdict tree ---------------------------------------------
def _book(cagr, sharpe, dd, harsh_ruin=0.05):
    return {"historical_metrics_no_tail": {"state": "OK", "cagr": cagr, "sharpe": sharpe,
                                           "max_drawdown": dd},
            "ruin_profile": {"p0.10_v1": {"prob_ruin": harsh_ruin}}}


def _oc(fstar, ruin=0.01, p05_cagr=0.02, single_venue=0.11, worst_early=-0.18):
    return {"by_fraction": {f"f{fstar:.2f}": {"prob_ruin": ruin, "p05_cagr": p05_cagr,
                                              "single_venue_loss_of_book": single_venue,
                                              "worst_early_loss": worst_early}}}


def test_verdict_no_usable_edge_when_fstar_zero():
    v, _ = p97.classify_usability(0.0, _book(0.0, 0.0, -0.5), _oc(0.0))
    assert v == "NO_USABLE_EDGE"


def test_verdict_found_when_all_gates_pass():
    v, _ = p97.classify_usability(0.30, _book(0.05, 1.3, -0.08, harsh_ruin=0.10),
                                  _oc(0.30, ruin=0.02, p05_cagr=0.02, single_venue=0.11))
    assert v == "USABLE_EDGE_FOUND"


def test_verdict_marginal_when_single_venue_loss_too_big_for_found():
    v, _ = p97.classify_usability(0.40, _book(0.05, 1.3, -0.08, harsh_ruin=0.10),
                                  _oc(0.40, ruin=0.03, p05_cagr=0.01, single_venue=0.145))
    assert v == "USABLE_EDGE_MARGINAL"


# --- E. determinism + persistence ------------------------------
def test_optimal_fraction_is_deterministic(synthetic_series):
    a = p97.optimal_carry_fraction(p97._sleeve_series())["f_star"]
    b = p97.optimal_carry_fraction(p97._sleeve_series())["f_star"]
    assert a == b


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p97.store, "save_artifact",
                        lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h97"))
    monkeypatch.setattr(p97.store, "load_artifact",
                        lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    res = p97.Phase97Result(
        schema_version=p97.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
        frozen_contract_hash="x", design_note={}, sample={}, sleeve_standalone={}, risk_of_ruin_grid={},
        optimal_carry_fraction={}, diversification={}, recommended_book={}, usability_verdict="V",
        usability_reason="", fx_carry_status="DEFERRED", determinism={"match": True})
    assert p97.persist(res) == "h97"
    assert p97.get_result()["usability_verdict"] == "V"


def test_result_reports_safety_flags():
    res = p97.Phase97Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="x", design_note={},
        sample={}, sleeve_standalone={}, risk_of_ruin_grid={}, optimal_carry_fraction={},
        diversification={}, recommended_book={}, usability_verdict="x", usability_reason="",
        fx_carry_status="x", determinism={})
    d = res.to_dict()
    assert d["live_automation_enabled"] is False
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["holdout_untouched"] is True


# --- F. safety -----------------------------------------------
def test_module_never_imports_execution_or_reads_holdout():
    src = inspect.getsource(p97)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "live_trading", "risk_engine",
              "account_management", "mt5_execution", "trade_execution"):
        assert not any(f in l for l in import_lines), f"forbidden import: {f}"
    for token in ("place_order", "submit_order", "execute_trade", "delete_account", "remove_account",
                  "load_holdout", "locked_holdout"):
        assert token not in src


def test_frozen_contract_hash_is_the_canonical_constant():
    import gold_strategy_baseline as gsb
    assert gsb.get_gold_baseline().frozen_contract_hash == gsb.CANONICAL_CONTRACT_HASH


# --- G. API ------------------------------------------------
def test_api_endpoint_get_only_and_safe():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    r = client.get("/api/research/portfolio-construction")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert body["safety_barrier"] == {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}
    assert client.post("/api/research/portfolio-construction").status_code == 405
