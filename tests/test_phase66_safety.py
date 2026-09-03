# -*- coding: utf-8 -*-
"""
Phase 66 — safety invariants for the multi-provider evidence layer.

No provider (FRED / CFTC / forecast / sentiment) or the orchestrator may reach
execution infrastructure. Strategy Contract SHA-256 unchanged. No secret in
source or API responses.
"""
import hashlib
import os
import types

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _offline_and_clean(monkeypatch):
    """Keep every provider offline (no real network) and leave the shared
    EconomicDataRegistry as we found it."""
    from api.providers import cftc_provider as cp
    from macro_intelligence_engine import EconomicDataRegistry

    monkeypatch.setattr(cp, "_http_get", lambda p, t: (_ for _ in ()).throw(OSError("offline in tests")))
    cp.reset_state_for_tests()
    saved = list(EconomicDataRegistry._RELEASES)
    saved_init = EconomicDataRegistry._INITIALIZED
    saved_mgd = EconomicDataRegistry._PROVIDER_MANAGED
    yield
    cp.reset_state_for_tests()
    EconomicDataRegistry._RELEASES = saved
    EconomicDataRegistry._INITIALIZED = saved_init
    EconomicDataRegistry._PROVIDER_MANAGED = saved_mgd

_FORBIDDEN_MODULES = {
    "execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
    "execution_config",
}
_PROVIDER_MODULES = [
    "api.providers.registry",
    "api.providers.fred_provider",
    "api.providers.cftc_provider",
    "api.providers.forecast_provider",
    "api.providers.sentiment_provider",
    "api.macro_evidence",
]


def test_strategy_contract_hash_unchanged():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()
    assert digest == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_safety_state_unchanged_by_evidence_layer(monkeypatch):
    def _safety():
        h = client.get("/api/health").json()
        return h["automation_enabled"], h["live_broker_transmission"]

    assert _safety() == (False, "BLOCKED")
    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    monkeypatch.setenv("MACRO_FORECAST_PROVIDER", "none")
    client.get("/api/macro/providers")
    client.get("/api/macro/overview")
    client.get("/api/macro/currencies/USD")
    assert _safety() == (False, "BLOCKED")


def test_provider_modules_import_no_execution_module():
    for modname in _PROVIDER_MODULES:
        mod = __import__(modname, fromlist=["_"])
        bound = {v.__name__ for v in vars(mod).values() if isinstance(v, types.ModuleType)}
        leaked = bound & _FORBIDDEN_MODULES
        assert not leaked, f"{modname} imports {leaked}"


def test_no_secret_in_provider_source():
    import api.providers.cftc_provider as cp
    import api.providers.forecast_provider as fcp
    import api.providers.registry as rg

    for mod in (cp, fcp, rg):
        with open(mod.__file__, encoding="utf-8") as fh:
            text = fh.read().lower()
        # no hardcoded credential assignment
        assert "api_key = \"" not in text
        assert "secret = \"" not in text
        assert "token = \"" not in text


def test_providers_endpoint_never_returns_a_secret(monkeypatch):
    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    monkeypatch.setenv("FRED_API_KEY", "SUPERSECRETKEY" + "x" * 20)
    monkeypatch.setenv("MACRO_DATA_PROVIDER", "fred")
    blob = str(client.get("/api/macro/providers").json())
    assert "SUPERSECRETKEY" not in blob
    assert "api_key" not in blob.lower()


def test_evidence_layer_does_not_enable_automation(monkeypatch):
    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    from api.macro_evidence import ensure_evidence

    ensure_evidence()
    h = client.get("/api/health").json()
    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
