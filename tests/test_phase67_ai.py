# -*- coding: utf-8 -*-
"""
Phase 67 — AI context integration.

The AI must be able to receive the canonical evidence snapshot, must never
receive future information through it, and the evidence-fusion module must not
be able to reach any execution path.
"""
import types

import pytest

from api import ai_context
import api.evidence_fusion as fusion


_FORBIDDEN = {
    "execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
    "order_execution", "execution_config",
}


def test_ai_snapshot_is_bounded_and_safe():
    snap = fusion.ai_snapshot("XAUUSD")
    assert snap["asset"] == "XAUUSD"
    assert "categories" in snap and isinstance(snap["categories"], dict)
    assert "cross_category_state" in snap
    # no raw execution-ish fields, no giant evidence dump
    assert "overall_score" not in snap
    blob = str(snap)
    assert len(blob) < 4000


def test_ai_snapshot_never_carries_future_evidence():
    from datetime import datetime, timezone
    snap = fusion.ai_snapshot("XAUUSD", as_of=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert snap["as_of"].startswith("2026-08-01")
    assert snap["mode"] == "HISTORICAL"


def test_build_context_includes_asset_evidence_section():
    ctx = ai_context.build_context()
    snap = ctx["snapshot"]
    assert "asset_evidence" in snap
    ae = snap["asset_evidence"]
    if ae:  # populated only when the watchlist has supported highlights
        for entry in ae:
            assert "categories" in entry and "cross_category_state" in entry


def test_context_block_stays_bounded():
    ctx = ai_context.build_context()
    block = ai_context.context_as_prompt_block(ctx)
    assert len(block) <= 18_000


def test_system_instruction_marks_evidence_as_non_execution():
    text = ai_context.SYSTEM_INSTRUCTION.lower()
    assert "asset_evidence" in text
    assert "execution signal" in text
    assert "insufficient_evidence" in text or "provider_unavailable" in text


def test_evidence_fusion_imports_no_execution_module():
    mod = fusion
    bound = {v.__name__ for v in vars(mod).values() if isinstance(v, types.ModuleType)}
    assert not (bound & _FORBIDDEN), bound & _FORBIDDEN


def test_evidence_fusion_source_has_no_execution_import():
    import api.evidence_fusion as f
    import api.evidence_model as m
    for src in (f, m):
        with open(src.__file__, encoding="utf-8") as fh:
            text = fh.read()
        for bad in _FORBIDDEN:
            assert f"import {bad}" not in text
            assert f"from {bad}" not in text
