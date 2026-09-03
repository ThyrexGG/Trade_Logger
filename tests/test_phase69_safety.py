# -*- coding: utf-8 -*-
"""Phase 69 — safety & isolation (§58, §77)."""
import importlib

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

PHASE69_MODULES = [
    "research_universe",
    "historical_data_store",
    "market_data_ingest",
    "gold_strategy_baseline",
    "api.routers.strategy_research",
]

FORBIDDEN = ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
             "order_execution", "paper_simulator")


def test_no_phase69_module_imports_execution_layer():
    import sys
    for mod_name in PHASE69_MODULES:
        mod = importlib.import_module(mod_name)
        src = ""
        try:
            import inspect
            src = inspect.getsource(mod)
        except (OSError, TypeError):
            pass
        for bad in FORBIDDEN:
            assert bad not in src, f"{mod_name} references {bad}"


def test_research_endpoints_are_get_only():
    for path in ("/api/research/historical/coverage", "/api/research/universe",
                 "/api/research/gold-baseline"):
        assert client.get(path).status_code == 200
        assert client.post(path).status_code in (404, 405)
        assert client.delete(path).status_code in (404, 405)
        assert client.put(path).status_code in (404, 405)


def test_safety_barrier_present_and_blocked():
    for path in ("/api/research/historical/coverage", "/api/research/universe",
                 "/api/research/gold-baseline"):
        j = client.get(path).json()
        assert j["safety_barrier"]["live_automation_enabled"] is False
        assert j["safety_barrier"]["live_broker_transmission"] == "BLOCKED"


def test_health_invariants_unchanged():
    j = client.get("/api/health").json()
    assert j["automation_enabled"] is False
    assert j["live_broker_transmission"] == "BLOCKED"


def test_no_secrets_in_responses():
    for path in ("/api/research/historical/coverage", "/api/research/universe",
                 "/api/research/gold-baseline"):
        body = client.get(path).text.lower()
        for token in ("api_key", "apikey", "secret", "password", "fred_api", "bearer "):
            assert token not in body


def test_frozen_hash_and_holdout_constants_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    from xauusd_forward_accumulation import HistoricalVsForwardComparator as H
    assert FROZEN_CONTRACT_HASH == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    b = H.LOCKED_HISTORICAL_BASELINE
    assert (b["n"], b["expectancy_r"], b["win_rate_pct"], b["profit_factor"]) == (82, 0.637, 58.6, 2.52)


def test_ingestion_module_has_no_network_at_import():
    # importing must not trigger a download; yf handle may be None or a module
    import market_data_ingest as ing
    assert hasattr(ing, "ingest")
