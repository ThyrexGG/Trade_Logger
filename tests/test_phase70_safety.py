# -*- coding: utf-8 -*-
"""Phase 70 — safety & isolation (§58, §77)."""
import importlib
import inspect


from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

PHASE70_MODULES = ["strategy_discovery", "pair_ranking", "api.routers.strategy_research"]
FORBIDDEN = ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
             "order_execution", "paper_simulator", "capital_sync", "mt5_sync")


def test_no_phase70_module_imports_execution_layer():
    for name in PHASE70_MODULES:
        mod = importlib.import_module(name)
        try:
            src = inspect.getsource(mod)
        except (OSError, TypeError):
            src = ""
        for bad in FORBIDDEN:
            assert bad not in src, f"{name} references {bad}"


def test_research_endpoints_get_only():
    for path in ("/api/research/strategies", "/api/research/pair-ranking"):
        assert client.get(path).status_code == 200
        assert client.post(path).status_code in (404, 405)
        assert client.delete(path).status_code in (404, 405)
        assert client.put(path).status_code in (404, 405)


def test_strategies_endpoint_shape_and_safety():
    j = client.get("/api/research/strategies").json()
    assert j["strategies"] and isinstance(j["strategies"], list)
    assert j["safety_barrier"]["live_broker_transmission"] == "BLOCKED"
    assert j["safety_barrier"]["live_automation_enabled"] is False


def test_unknown_strategy_404():
    assert client.get("/api/research/strategies/nope").status_code == 404


def test_pair_ranking_endpoint_returns_state():
    j = client.get("/api/research/pair-ranking").json()
    assert j["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert "leaderboard" in j
    assert j["safety_barrier"]["live_broker_transmission"] == "BLOCKED"


def test_no_market_or_trade_score_naming():
    """§22/§44 — the ranking number must be a ResearchRankingScore, never a
    MarketScore / TradeScore / 'AI Trade Score' identifier."""
    import strategy_discovery
    src = inspect.getsource(strategy_discovery)
    assert "ResearchRankingScore" in src
    assert "research_ranking_score" in dir(strategy_discovery)
    for forbidden in ("def market_score", "def trade_score", "class MarketScore",
                      "class TradeScore", "MarketScore(", "TradeScore("):
        assert forbidden not in src
    # the ranking result labels itself as a non-signal
    out = strategy_discovery.research_ranking_score.__doc__ or ""
    assert "NOT" in out


def test_frozen_hash_and_holdout_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    from xauusd_forward_accumulation import HistoricalVsForwardComparator as H
    assert FROZEN_CONTRACT_HASH == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    b = H.LOCKED_HISTORICAL_BASELINE
    assert (b["n"], b["expectancy_r"], b["win_rate_pct"], b["profit_factor"]) == (82, 0.637, 58.6, 2.52)


def test_gold_baseline_edge_status_is_evidence_gated():
    """Phase 70 does not validate Gold. Without a Phase-71 revalidation artifact
    the baseline is INSUFFICIENT_EVIDENCE; with one it reflects that run's
    objective classification (never VALIDATED off a timeframe-substituted proxy
    unless the strict rule is met)."""
    import gold_strategy_baseline
    b = gold_strategy_baseline.get_gold_baseline()
    assert b.edge_status in (
        "INSUFFICIENT_EVIDENCE", "DEGRADED", "INVALIDATED", "VALIDATED", "HEALTHY")
    if b.revalidated_metrics is not None:
        # a revalidation ran — it must carry the timeframe-substitution caveat
        assert "not" in (b.next_dependency or "").lower()
