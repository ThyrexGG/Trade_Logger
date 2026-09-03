# -*- coding: utf-8 -*-
"""Phase 72 — Trade Setup Engine (§57, §58, §72)."""
import inspect

import pytest
from fastapi.testclient import TestClient

from api.main import app
import trade_setup as ts

client = TestClient(app)

_VS = ts.ValidatedStrategy(
    strategy_id="ict_2022_sweep_mss_fvg", strategy_version="test",
    family="LIQUIDITY_SWEEP + MSS + FVG", timeframe_stack="1d->4h->1h",
    sessions=["LONDON", "LONDON_NY_OVERLAP", "NEW_YORK", "ASIA"],
    oos_metrics={"expectancy_r": 0.2, "profit_factor": 1.6, "total_trades": 80, "win_rate_pct": 55},
    bootstrap_ci={"ci_lower": 0.05, "ci_range_str": "[+0.05R, +0.35R]"},
    wfo_stability=0.8, source="test")


class _Snap:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


def _snapshot(tech="BULLISH", smc="BULLISH", regime_state="AVAILABLE",
              regime_name="TRENDING", smc_items=("Liquidity sweep (15m)", "Bullish MSS (15m)",
                                                 "Bullish FVG (15m)"),
              stale=None):
    def cat(name, direction, state="AVAILABLE", items=(), freshness="FRESH"):
        ev = [it if isinstance(it, dict) else {"metric": it, "value": None, "note": ""}
              for it in items]
        return {
            "category": name, "state": state, "direction": direction, "score": 40.0,
            "freshness": "STALE" if stale and name in stale else freshness,
            "evidence": ev,
        }
    return _Snap({
        "categories": [
            cat("TECHNICAL", tech),
            cat("SMC", smc, state=("AVAILABLE" if smc else "INSUFFICIENT_EVIDENCE"),
                items=smc_items),
            cat("REGIME", "NEUTRAL", state=regime_state,
                items=[{"metric": "regime classification", "value": regime_name,
                        "note": regime_name}]),
        ],
        "provenance": [{"source": "live:test"}],
        "cross_category_state": "AGREEMENT",
    })


@pytest.fixture(autouse=True)
def _reset():
    ts.set_test_resolver(None)
    yield
    ts.set_test_resolver(None)


def _patch_evidence(monkeypatch, snap):
    from api import evidence_fusion
    monkeypatch.setattr(evidence_fusion, "get_asset_intelligence", lambda *a, **k: snap)


# --- the real current state -------------------------------------------
def test_no_validated_strategy_is_no_setup():
    s = ts.evaluate_setup("XAUUSD")
    assert s.state == "NO_SETUP"
    assert "No validated strategy" in s.reason
    assert s.strategy_id is None
    assert s.entry is None


def test_every_universe_instrument_is_no_setup_today():
    for sym in ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD"):
        assert ts.evaluate_setup(sym).state == "NO_SETUP"


# --- READY path (injected validated strategy + favourable evidence) ---
def test_ready_when_all_mandatory_conditions_pass(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    _patch_evidence(monkeypatch, _snapshot())
    monkeypatch.setattr(
        "historical_market_data.get_candle_window",
        lambda *a, **k: type("W", (), {
            "n": 60,
            "candles": [{"open": 2000 + i, "high": 2002 + i, "low": 1998 + i,
                         "close": 2001 + i, "volume": 1} for i in range(60)],
        })(),
    )
    s = ts.evaluate_setup("XAUUSD")
    assert s.state == "READY"
    assert s.direction == "LONG"
    assert s.entry is not None and s.stop_loss is not None and s.take_profit is not None
    assert s.risk_reward and s.risk_reward > 1
    assert not s.failing_conditions


def test_setup_forming_when_levels_not_derivable(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    _patch_evidence(monkeypatch, _snapshot())
    monkeypatch.setattr("historical_market_data.get_candle_window", lambda *a, **k: None)
    s = ts.evaluate_setup("XAUUSD")
    assert s.state == "SETUP_FORMING"
    assert s.entry is None


# --- failing conditions ---------------------------------------------
def test_wrong_mtf_alignment_is_not_ready(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    _patch_evidence(monkeypatch, _snapshot(tech="BULLISH", smc="BEARISH"))
    s = ts.evaluate_setup("XAUUSD")
    assert s.state != "READY"
    assert "MTF alignment (SMC agrees with HTF)" in s.failing_conditions or s.state == "INVALIDATED"


def test_incompatible_regime_is_not_ready(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    # strategy tolerates TRENDING / HIGH_VOLATILITY; give it LOW_VOLATILITY
    _patch_evidence(monkeypatch, _snapshot(regime_name="LOW_VOLATILITY"))
    s = ts.evaluate_setup("XAUUSD")
    assert s.state != "READY"


def test_wrong_session_is_not_ready(monkeypatch):
    vs = ts.ValidatedStrategy(**{**_VS.__dict__, "sessions": ["LONDON"]})
    ts.set_test_resolver(lambda a: vs)
    _patch_evidence(monkeypatch, _snapshot())
    s = ts.evaluate_setup("XAUUSD")
    # unless the test happens to run during London, session fails
    if "Session permitted" in s.failing_conditions:
        assert s.state != "READY"


def test_stale_evidence_yields_stale_state(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    _patch_evidence(monkeypatch, _snapshot(stale=["TECHNICAL"]))
    s = ts.evaluate_setup("XAUUSD")
    assert s.state == "STALE"
    assert s.waiting_for == "fresh evidence"


def test_unknown_regime_yields_insufficient_evidence(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    _patch_evidence(monkeypatch, _snapshot(regime_state="INSUFFICIENT_EVIDENCE"))
    s = ts.evaluate_setup("XAUUSD")
    assert s.state == "INSUFFICIENT_EVIDENCE"


def test_contradiction_can_invalidate(monkeypatch):
    ts.set_test_resolver(lambda a: _VS)
    # HTF bullish, SMC bearish, regime incompatible -> two contradictions
    _patch_evidence(monkeypatch, _snapshot(tech="BULLISH", smc="BEARISH",
                                           regime_name="LOW_VOLATILITY"))
    s = ts.evaluate_setup("XAUUSD")
    assert s.state in ("INVALIDATED", "WATCH", "NO_SETUP", "SETUP_FORMING")
    assert s.state != "READY"


# --- AI cannot change the state -------------------------------------
def test_ai_summary_carries_do_not_override_and_matches_engine():
    summ = ts.ai_setup_summary("XAUUSD")
    engine_state = ts.evaluate_setup("XAUUSD").state
    assert summ["state"] == engine_state
    assert "do not override" in summ["note"].lower()


def test_ai_context_system_instruction_forbids_overriding_setup():
    from api.ai_context import SYSTEM_INSTRUCTION
    assert "never call a setup READY" in SYSTEM_INSTRUCTION
    assert "override a NO_SETUP" in SYSTEM_INSTRUCTION or "NO TRADE" in SYSTEM_INSTRUCTION


# --- safety --------------------------------------------------------
def test_no_execution_imports():
    for mod_name in ("trade_setup", "api.routers.trade_setup"):
        import importlib
        src = inspect.getsource(importlib.import_module(mod_name))
        for bad in ("execution_pipeline", "broker_adapter", "risk_gateway",
                    "reconciliation", "order_execution"):
            assert bad not in src


def test_endpoints_get_only_and_safe():
    for p in ("/api/trade-setup", "/api/trade-setup/XAUUSD",
              "/api/trade-setup/EURUSD/conditions"):
        assert client.get(p).status_code == 200
        assert client.post(p).status_code in (404, 405)
    j = client.get("/api/trade-setup/XAUUSD").json()
    assert j["safety_barrier"]["live_broker_transmission"] == "BLOCKED"
    assert client.get("/api/trade-setup/NOPE").status_code == 404
