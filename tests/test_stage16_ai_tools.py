# -*- coding: utf-8 -*-
"""
Tests for Phase W1 — the AI Assistant's read-only tool registry (`api/ai_tools.py`).

The model may *request* one of these tools; `dispatch()` runs it. Every tool must
be read-only, bounded, allowlisted, and reachable by no execution path.
"""
import json

import pytest
from fastapi.testclient import TestClient

from api import ai_tools
from api.main import app

client = TestClient(app)

EXPECTED_TOOLS = {"query_trades", "analytics_period", "tag_record", "macro_scorecard", "journal_search"}


def test_registry_is_the_expected_allowlist():
    assert set(ai_tools.tool_names()) == EXPECTED_TOOLS


def test_unknown_tool_is_rejected():
    with pytest.raises(KeyError):
        ai_tools.dispatch("submit_order", {"symbol": "EURUSD"})
    with pytest.raises(KeyError):
        ai_tools.dispatch("", {})


def test_every_tool_returns_json_serialisable_dict():
    calls = [
        ("query_trades", {}),
        ("query_trades", {"symbol": "EURUSD", "direction": "buy", "session": "london"}),
        ("analytics_period", {"window": "all"}),
        ("tag_record", {}),
        ("journal_search", {"query": "setup"}),
    ]
    for name, args in calls:
        out = ai_tools.dispatch(name, args)
        assert isinstance(out, dict)
        json.dumps(out)  # must serialise


def test_bad_arguments_return_error_not_raise():
    assert "error" in ai_tools.dispatch("analytics_period", {"window": "decade"})
    assert "error" in ai_tools.dispatch("query_trades", {"session": "tokyo"})
    assert "error" in ai_tools.dispatch("query_trades", {"date_from": "not-a-date"})
    assert "error" in ai_tools.dispatch("journal_search", {"query": "x"})
    assert "error" in ai_tools.dispatch("macro_scorecard", {"instrument": "DOGECOIN"})
    # unexpected kwarg is swallowed, not raised
    assert isinstance(ai_tools.dispatch("tag_record", {"bogus": 1}), dict)


def test_query_trades_unknown_symbol_is_graceful():
    out = ai_tools.dispatch("query_trades", {"symbol": "ZZZZZZ"})
    assert out.get("n") == 0


def test_macro_scorecard_unsupported_lists_supported():
    out = ai_tools.dispatch("macro_scorecard", {"instrument": "GBPCHF_XYZ"})
    assert "error" in out and isinstance(out.get("supported"), list) and out["supported"]


def test_dispatching_tools_has_no_side_effects():
    sys_before = client.get("/api/operations/system").json()
    audit_before = client.get("/api/operations/audit?limit=1").json()
    positions_before = client.get("/api/positions").json()

    for name, args in [
        ("query_trades", {"symbol": "XAUUSD"}),
        ("analytics_period", {"window": "week"}),
        ("tag_record", {}),
        ("journal_search", {"query": "trade"}),
    ]:
        ai_tools.dispatch(name, args)

    assert client.get("/api/operations/system").json()["open_positions"] == sys_before["open_positions"]
    assert client.get("/api/operations/audit?limit=1").json()["total_records"] == audit_before["total_records"]
    assert client.get("/api/positions").json()["total_open"] == positions_before["total_open"]
    h = client.get("/api/health").json()
    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"


def test_gemini_declarations_build_and_match_registry():
    decls = ai_tools.gemini_tool_declarations()
    assert decls and hasattr(decls[0], "function_declarations")
    names = {fd.name for fd in decls[0].function_declarations}
    assert names == EXPECTED_TOOLS


def test_module_binds_no_execution_symbol():
    import types as _t

    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway", "submit_order"}
    for nm, val in vars(ai_tools).items():
        assert nm not in forbidden
        if isinstance(val, _t.ModuleType):
            assert val.__name__.split(".")[0] not in forbidden
