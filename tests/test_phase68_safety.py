# -*- coding: utf-8 -*-
"""
Phase 68 — safety invariants for the historical market evidence layer.

Read-only. No execution path. Frozen contract unchanged. No secrets.
"""
import hashlib
import os
import types

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_FROZEN_CONTRACT_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
_FORBIDDEN = {
    "execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
    "order_execution", "execution_config", "paper_simulator",
}
_PHASE68_MODULES = ["historical_market_data", "market_evidence_engine"]


def test_frozen_contract_hash_unchanged():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()
    assert digest == _FROZEN_CONTRACT_HASH


def test_live_automation_flags_unchanged():
    h = client.get("/api/health").json()
    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
    client.get("/api/intelligence/asset/XAUUSD")
    client.get("/api/intelligence/asset/EURUSD?as_of=2026-04-01T00:00:00Z")
    h2 = client.get("/api/health").json()
    assert h2["automation_enabled"] is False
    assert h2["live_broker_transmission"] == "BLOCKED"


def test_phase68_modules_import_no_execution_module():
    for name in _PHASE68_MODULES:
        mod = __import__(name, fromlist=["_"])
        bound = {v.__name__ for v in vars(mod).values() if isinstance(v, types.ModuleType)}
        leaked = bound & _FORBIDDEN
        assert not leaked, f"{name} imports {leaked}"


def test_phase68_source_has_no_execution_reference():
    import historical_market_data as h
    import market_evidence_engine as m
    for src in (h, m):
        with open(src.__file__, encoding="utf-8") as fh:
            text = fh.read()
        for bad in _FORBIDDEN:
            assert f"import {bad}" not in text
            assert f"from {bad} import" not in text
        assert "submit_order" not in text
        assert "place_order" not in text


def test_market_data_source_helper_is_readonly():
    """get_candles_with_source only reads — it must not have side effects beyond
    the existing candle cache."""
    import market_data
    c1, s1 = market_data.get_candles_with_source("XAUUSD", "15m", 40)
    c2, s2 = market_data.get_candles_with_source("XAUUSD", "15m", 40)
    assert len(c1) == len(c2)
    assert s1 == s2
    assert s1 in ("mt5", "binance", "yahoo", "synthetic_fallback", "unknown")


def test_no_secret_in_phase68_source():
    import historical_market_data as h
    import market_evidence_engine as m
    for mod in (h, m):
        with open(mod.__file__, encoding="utf-8") as fh:
            text = fh.read().lower()
        assert 'api_key = "' not in text
        assert 'secret = "' not in text
        assert 'token = "' not in text


def test_snapshot_still_declares_read_only_barrier():
    j = client.get("/api/intelligence/asset/XAUUSD").json()
    assert j["safety_barrier"] == {
        "live_automation_enabled": False,
        "live_broker_transmission": "BLOCKED",
    }
