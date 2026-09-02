# -*- coding: utf-8 -*-
"""
Tests for Stage 18 — Market & Macro Intelligence foundation.

Read-only. The macro layer (provider -> surprise engine -> service -> API ->
Gemini context) has no import of / path to execution_pipeline, broker_adapter
or risk_gateway, and never fabricates economic data: missing stays missing,
unsupported currencies return INSUFFICIENT_EVIDENCE, demo data is tagged
`provenance="seed_demo"`.
"""
import types

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import surprise_engine as se
from api.macro_provider import normalize_event

client = TestClient(app)


# --- 18A: provider normalization ------------------------------------
def test_normalize_missing_fields_stay_none():
    ev = normalize_event(
        {"event_name": "US CPI", "scheduled_time": "2026-09-03T13:30:00Z", "currency": "USD"},
        provider="seed_demo", is_live=False,
    )
    assert ev is not None
    assert ev["actual"] is None and ev["forecast"] is None and ev["previous"] is None
    assert ev["currency"] == "USD"
    assert ev["provenance"] == "seed_demo"


def test_normalize_parses_formatted_numbers():
    ev = normalize_event(
        {"name": "Jobless Claims", "timestamp": "2026-09-03T13:30:00Z",
         "country": "United States", "forecast": "225K", "previous": "228K", "actual": None},
        provider="seed_demo", is_live=False,
    )
    assert ev["forecast"] == 225_000.0 and ev["previous"] == 228_000.0
    assert ev["currency"] == "USD"  # derived from country


@pytest.mark.parametrize("bad", [None, {}, {"event_name": "x"}, {"scheduled_time": "t"}, "not a dict", 42])
def test_normalize_rejects_malformed(bad):
    assert normalize_event(bad, provider="seed_demo", is_live=False) is None


# --- 18B: surprise engine determinism ------------------------------
def test_surprise_inflation_vs_growth_are_not_the_same_rule():
    # CPI beat -> bad for the economy, hawkish for policy
    cpi = se.evaluate_surprise(indicator="CPI", actual=3.4, forecast=3.1, previous=3.2)
    assert cpi["direction_bias"] == "NEGATIVE"
    assert cpi["policy_bias"] == "HAWKISH"
    # GDP beat -> good for the economy
    gdp = se.evaluate_surprise(indicator="GDP", actual=2.8, forecast=2.1, previous=2.0)
    assert gdp["direction_bias"] == "POSITIVE"
    # Unemployment beat (higher) -> bad for the economy, dovish
    un = se.evaluate_surprise(indicator="UNEMPLOYMENT", actual=4.5, forecast=4.1)
    assert un["direction_bias"] == "NEGATIVE" and un["policy_bias"] == "DOVISH"
    # Jobless claims lower than forecast -> good for the economy
    jc = se.evaluate_surprise(indicator="JOBLESS_CLAIMS", actual=205_000, forecast=225_000)
    assert jc["direction_bias"] == "POSITIVE"


def test_surprise_missing_data_is_unavailable():
    r = se.evaluate_surprise(indicator="CPI", actual=None, forecast=3.1)
    assert r["state"] == "UNAVAILABLE" and r["surprise"] is None
    assert r["normalized_surprise"] is None


def test_surprise_unknown_indicator_is_insufficient_not_guessed():
    r = se.evaluate_surprise(indicator="RANDOM_MADE_UP_INDICATOR", actual=5.0, forecast=3.0)
    assert r["state"] == "INSUFFICIENT"
    assert r["direction_bias"] == "NEUTRAL"  # not interpreted
    assert r["surprise"] == 2.0  # raw delta is still reported


def test_surprise_normalized_only_when_std_configured_and_deterministic():
    a = se.evaluate_surprise(indicator="CORE_CPI", actual=3.4, forecast=3.2)
    b = se.evaluate_surprise(indicator="CORE_CPI", actual=3.4, forecast=3.2)
    assert a == b
    assert a["normalized_surprise"] is not None and a["confidence"] == "HIGH"
    # CORE_CPI std is 0.2 -> z = 0.2/0.2 = 1.0 -> normalized 30.0
    assert a["normalized_surprise"] == 30.0


def test_surprise_inline_when_tiny():
    r = se.evaluate_surprise(indicator="CPI", actual=3.11, forecast=3.10)
    assert r["state"] == "INLINE" and r["direction_bias"] == "NEUTRAL"


# --- 18F: API -----------------------------------------------------
def test_all_macro_endpoints_get_only():
    for ep in ("/api/macro/overview", "/api/macro/events", "/api/macro/surprises",
               "/api/macro/currencies", "/api/macro/assets"):
        assert client.post(ep, json={}).status_code == 405
        assert client.delete(ep).status_code == 405


def test_macro_responses_carry_provenance():
    for ep in ("/api/macro/overview", "/api/macro/currencies", "/api/macro/assets",
               "/api/macro/events/upcoming", "/api/macro/surprises"):
        d = client.get(ep).json()
        assert d["data_provider"] and "provider_is_live" in d and d["provenance"] in ("live", "seed_demo", "unavailable")
        assert d["provider_is_live"] is False  # default provider is the seed_demo one
        assert "disclaimer" in d


@pytest.mark.parametrize("qs,code", [
    ("window=nonsense", 422),
    ("start=2026/01/01", 422),
    ("end=notadate", 422),
    ("start=2026-06-01&end=2026-01-01", 422),
    ("currency=ZZZ", 422),
    ("impact=SUPERHIGH", 422),
    ("limit=0", 422),
    ("limit=9999", 422),
])
def test_macro_events_validation(qs, code):
    assert client.get(f"/api/macro/events?{qs}").status_code == code


def test_unsupported_currency_and_asset_are_404():
    assert client.get("/api/macro/currencies/ZZZ").status_code == 404
    assert client.get("/api/macro/assets/NOTATHING").status_code == 404


def test_insufficient_evidence_is_explicit_not_fabricated():
    d = client.get("/api/macro/currencies/CHF").json()
    assert d["available"] is False
    assert d["state"] == "INSUFFICIENT_EVIDENCE"
    assert d["score"] is None  # never a fabricated number
    # and the aggregate lists it honestly
    agg = client.get("/api/macro/currencies").json()
    assert "CHF" in agg["insufficient_evidence"]


def test_supported_currency_has_traceable_score():
    d = client.get("/api/macro/currencies/USD").json()
    assert d["available"] is True and isinstance(d["score"], (int, float))
    import macro_intelligence_engine as m
    canon = m.EconomicStrengthEngine.evaluate_economic_strength("USD")
    assert d["score"] == round(float(canon["economic_strength_score"]), 1)


def test_macro_deterministic():
    a = client.get("/api/macro/currencies").json()
    b = client.get("/api/macro/currencies").json()
    assert [c.get("score") for c in a["currencies"]] == [c.get("score") for c in b["currencies"]]


def test_no_provider_secret_in_responses():
    import json
    for ep in ("/api/macro/overview", "/api/macro/currencies", "/api/macro/assets", "/api/macro/events"):
        blob = json.dumps(client.get(ep).json()).lower()
        for leak in ("api_key", "apikey", "secret", "password", "token", "bearer"):
            assert leak not in blob


# --- safety -----------------------------------------------------
def test_macro_modules_bind_no_execution_symbol():
    import api.routers.macro as r
    import api.macro_service as s
    import api.macro_provider as p
    import api.surprise_engine as sg
    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway",
                 "submit_order", "get_broker_adapter", "CanonicalExecutionRequest"}
    for mod in (r, s, p, sg):
        for name, value in vars(mod).items():
            assert name not in forbidden, f"{mod.__name__} binds {name}"
            if isinstance(value, types.ModuleType):
                assert value.__name__.split(".")[0] not in forbidden, f"{mod.__name__} imports {value.__name__}"


def test_macro_usage_does_not_touch_execution_state():
    sys_before = client.get("/api/operations/system").json()
    audit_before = client.get("/api/operations/audit?limit=1").json()

    for ep in ("/api/macro/overview", "/api/macro/events", "/api/macro/currencies",
               "/api/macro/assets", "/api/macro/surprises", "/api/macro/pairs"):
        client.get(ep)

    sys_after = client.get("/api/operations/system").json()
    audit_after = client.get("/api/operations/audit?limit=1").json()
    h = client.get("/api/health").json()

    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
    assert sys_before["open_positions"] == sys_after["open_positions"]
    assert audit_before["total_records"] == audit_after["total_records"]
    assert audit_before["mode_counts"] == audit_after["mode_counts"]


# --- 18H: Gemini macro context ---------------------------------
def test_ai_context_includes_bounded_macro_section():
    from api.ai_context import build_context, context_as_prompt_block, SYSTEM_INSTRUCTION
    ctx = build_context()
    macro = ctx["snapshot"].get("macro_intelligence")
    assert macro is not None
    assert macro["is_live_data"] is False and macro["provenance"] == "seed_demo"
    # bounded — no raw calendar dump
    assert len(macro["upcoming_high_impact_events"]) <= 5
    assert len(macro["recent_important_surprises"]) <= 5
    block = context_as_prompt_block(ctx)
    assert len(block) <= 18_000
    assert "macro" in SYSTEM_INSTRUCTION.lower()
    assert "never an execution signal" in SYSTEM_INSTRUCTION.lower()


def test_ai_context_still_has_no_execution_path():
    import importlib
    import sys
    for m in ("execution_pipeline", "broker_adapter"):
        sys.modules.pop(m, None)
    before = set(sys.modules)
    importlib.reload(importlib.import_module("api.ai_context"))
    newly = set(sys.modules) - before
    assert not any(m.split(".")[0] in {"execution_pipeline", "broker_adapter"} for m in newly), newly
