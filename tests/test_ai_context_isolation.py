# -*- coding: utf-8 -*-
"""The AI assistant's snapshot cache must be per user: one user's balance/positions/P&L must never be
handed to another user's question (it used to be a single global cache with a 2-minute TTL)."""
import pytest

import tenant
from api import ai_context


@pytest.fixture(autouse=True)
def _clean():
    ai_context._ctx_cache.clear()
    yield
    ai_context._ctx_cache.clear()


def test_each_user_gets_their_own_snapshot(monkeypatch):
    calls = []

    def fake_uncached():
        uid = tenant.current_user_id()
        calls.append(uid)
        return {"snapshot": {"owner": uid}, "available_sections": [], "unavailable_sections": []}

    monkeypatch.setattr(ai_context, "_build_context_uncached", fake_uncached)
    with tenant.use("alice"):
        a1 = ai_context.build_context()
    with tenant.use("bob"):
        b1 = ai_context.build_context()
    with tenant.use("alice"):
        a2 = ai_context.build_context()
    assert a1["snapshot"]["owner"] == "alice"
    assert b1["snapshot"]["owner"] == "bob"      # was alice's before the fix
    assert a2 is a1                               # still cached within one user
    assert calls == ["alice", "bob"]              # built once per user, not once per call


def test_force_rebuilds_only_the_callers_entry(monkeypatch):
    n = {"i": 0}

    def fake_uncached():
        n["i"] += 1
        return {"snapshot": {"n": n["i"], "owner": tenant.current_user_id()}, "available_sections": [], "unavailable_sections": []}

    monkeypatch.setattr(ai_context, "_build_context_uncached", fake_uncached)
    with tenant.use("alice"):
        first = ai_context.build_context()
    with tenant.use("bob"):
        bob = ai_context.build_context()
    with tenant.use("alice"):
        again = ai_context.build_context(force=True)
    assert again["snapshot"]["n"] != first["snapshot"]["n"]
    with tenant.use("bob"):
        assert ai_context.build_context() is bob


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(ai_context, "_build_context_uncached", lambda: {"snapshot": {}, "available_sections": [], "unavailable_sections": []})
    for i in range(260):
        with tenant.use(f"user{i}"):
            ai_context.build_context()
    assert len(ai_context._ctx_cache) <= 200
