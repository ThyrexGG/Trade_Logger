# -*- coding: utf-8 -*-
"""
GET /api/research/historical/coverage — stale-while-revalidate cache.

The payload is expensive to build (one store round-trip per instrument x
timeframe). The endpoint must:
  * still return a well-formed, safety-barriered payload,
  * serve a persisted snapshot instantly on a cold process,
  * rebuild synchronously when `?refresh=true`,
  * never expose a mutation verb.
"""
import time

import pytest
from fastapi.testclient import TestClient

from api.main import app
import api.routers.strategy_research as sr

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    sr._coverage_mem["payload"] = None
    sr._coverage_mem["at"] = 0.0
    yield


def _assert_shape(body: dict):
    assert body["safety_barrier"] == {"live_automation_enabled": False,
                                      "live_broker_transmission": "BLOCKED"}
    assert isinstance(body["available"], list)
    assert isinstance(body["sufficiency"], list)
    assert body["universe"]


def test_cold_call_builds_and_persists_snapshot():
    r = client.get("/api/research/historical/coverage")
    assert r.status_code == 200
    _assert_shape(r.json())
    # persisted for the next cold process
    art = sr.store.load_artifact(sr._COVERAGE_ARTIFACT_KEY)
    assert art and art["payload"]["universe"]


def test_second_call_is_served_from_memory_cache():
    client.get("/api/research/historical/coverage")  # populate
    built_at = sr._coverage_mem["at"]
    assert built_at > 0
    r = client.get("/api/research/historical/coverage")
    assert r.status_code == 200
    # no rebuild — timestamp unchanged
    assert sr._coverage_mem["at"] == built_at


def test_refresh_true_forces_a_rebuild():
    client.get("/api/research/historical/coverage")
    first = sr._coverage_mem["at"]
    time.sleep(0.01)
    r = client.get("/api/research/historical/coverage?refresh=true")
    assert r.status_code == 200
    _assert_shape(r.json())
    assert sr._coverage_mem["at"] > first


def test_cold_process_serves_persisted_snapshot_without_full_rebuild():
    client.get("/api/research/historical/coverage?refresh=true")  # ensure artifact exists
    sr._coverage_mem["payload"] = None
    sr._coverage_mem["at"] = 0.0
    r = client.get("/api/research/historical/coverage")
    assert r.status_code == 200
    _assert_shape(r.json())


def test_endpoint_is_get_only():
    assert client.post("/api/research/historical/coverage").status_code in (404, 405)
    assert client.delete("/api/research/historical/coverage").status_code in (404, 405)
    assert client.put("/api/research/historical/coverage").status_code in (404, 405)
