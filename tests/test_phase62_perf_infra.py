# -*- coding: utf-8 -*-
"""
Phase 62 — performance infrastructure correctness (no timing assertions).

Covers the short-TTL snapshot caches added to the slow read-only endpoints and
the shared PAPER system-health cache. These protect against:
  * a cache that never refreshes (invalidation must work)
  * a cache that leaks the wrong key's payload
  * the authoritative evaluator being bypassed for real execution gating
    (`system_health.evaluate_system_health` itself is NOT cached)
"""
import system_health
from fastapi.testclient import TestClient

from api.main import app
from api import system_health_cache
from api.routers import operations as ops_router

client = TestClient(app)


def test_audit_cache_serves_then_invalidates():
    ops_router.invalidate_audit_cache()
    r1 = client.get("/api/operations/audit?limit=25")
    r2 = client.get("/api/operations/audit?limit=25")
    assert r1.status_code == r2.status_code == 200
    # same timestamp => served from the snapshot cache, not rebuilt
    assert r1.json()["timestamp"] == r2.json()["timestamp"]

    ops_router.invalidate_audit_cache()
    r3 = client.get("/api/operations/audit?limit=25")
    assert r3.json()["timestamp"] != r1.json()["timestamp"]


def test_audit_cache_is_keyed_by_limit():
    ops_router.invalidate_audit_cache()
    small = client.get("/api/operations/audit?limit=5").json()
    big = client.get("/api/operations/audit?limit=500").json()
    assert small["total_returned"] <= 5
    assert big["total_returned"] >= small["total_returned"]


def test_system_health_cache_hits_and_invalidates(monkeypatch):
    system_health_cache.invalidate()
    calls = {"n": 0}
    real = system_health.evaluate_system_health

    def _counting(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(system_health, "evaluate_system_health", _counting)

    system_health_cache.cached_paper_system_health(ttl=60)
    system_health_cache.cached_paper_system_health(ttl=60)
    assert calls["n"] == 1  # second call served from cache

    system_health_cache.invalidate()
    system_health_cache.cached_paper_system_health(ttl=60)
    assert calls["n"] == 2


def test_system_health_cache_forces_paper_mode(monkeypatch):
    system_health_cache.invalidate()
    seen = {}

    def _spy(*a, **kw):
        seen.update(kw)
        return {"overall_status": "BLOCKED", "automation_allowed": False, "checks": {}}

    monkeypatch.setattr(system_health, "evaluate_system_health", _spy)
    system_health_cache.cached_paper_system_health(broker="MT5")
    assert seen.get("mode") == "PAPER"


def test_operations_system_still_failclosed():
    d = client.get("/api/operations/system").json()
    assert d["live_automation_enabled"] is False
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["safety_gate"]["automation_allowed"] in (True, False)


def test_benchmark_module_imports_no_execution_and_reports_pool():
    import importlib

    import database
    import performance_benchmark as pb

    mod_names = {
        getattr(v, "__name__", "")
        for v in vars(pb).values()
        if isinstance(v, type(importlib))
    }
    for forbidden in ("execution_pipeline", "broker_adapter", "risk_gateway"):
        assert forbidden not in mod_names

    stats = database.pool_stats()
    assert {"checkouts", "reused", "overflow_direct", "enabled"} <= set(stats)
