# -*- coding: utf-8 -*-
"""
Tests for Stage 3.5D — Forward Evidence Read-Path Performance Optimization
========================================================================
GET /api/forward-evidence/state now serves the authoritative Phase 49 state
through Phase49MonitoringFacade.get_cached_forward_state_snapshot() — a bounded,
thread-safe, process-local, TTL(60s) single-slot cache — instead of running the
full Phase 49 + Phase 50 cockpit computation (incl. a per-call audit-record
INSERT) on every poll.

Verifies:
1. cold request computes the authoritative evidence
2. warm request returns the cached evidence (no recompute)
3. cached response is semantically identical to an uncached authoritative compute
4. TTL expiration causes recomputation
5. explicit invalidation causes recomputation
6. repeated GET polling creates no duplicate Phase 50 audit rows
7. Strategy Contract SHA-256 unchanged
8. historical holdout baseline (isolation) unchanged
9. evidence statistics identical cached vs authoritative
10. response schema unchanged
11. no execution / broker capability introduced
12. cache is safe under concurrent reads (computed exactly once)
"""
import threading
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app
import xauusd_forward_statistical_monitoring as fsm
from xauusd_forward_statistical_monitoring import (
    Phase49MonitoringFacade,
    FROZEN_CONTRACT_HASH,
    HISTORICAL_BASELINE,
)
import database

client = TestClient(app)
EP = "/api/forward-evidence/state"

RESPONSE_KEYS = {
    "symbol", "mode", "sample_n", "win_rate_pct", "profit_factor", "expected_r",
    "next_milestone", "decision_state", "wilson_ci_lower_pct", "wilson_ci_upper_pct",
    "historical_baseline", "strategy_contract_hash", "live_broker_transmission", "timestamp",
}


@pytest.fixture(autouse=True)
def _reset_snapshot():
    Phase49MonitoringFacade.invalidate_forward_state_snapshot()
    yield
    Phase49MonitoringFacade.invalidate_forward_state_snapshot()


def _fake_p49(tag="A"):
    return {
        "symbol": "XAUUSD", "mode": "PAPER",
        "evaluated_at": f"2026-09-02T00:00:00+00:00#{tag}",
        "contract_hash": FROZEN_CONTRACT_HASH, "contract_valid": True,
        "metrics": {"trades_n": 7, "win_rate_pct": 57.0, "profit_factor": 1.9, "expectancy_r": 0.42},
        "uncertainty": {"wilson_win_rate_ci": (0.31, 0.79)},
        "milestones": {"next_milestone": 10},
        "decision": {"decision_state": "ACCUMULATING_EVIDENCE"},
        "comparison": {}, "alpha_decay": {}, "dataset": {},
        "live_automation_barrier": {"live_automation_enabled": False,
                                    "broker_transmission": "BLOCKED (FAIL-CLOSED)"},
    }


class _SpyCompute:
    """Counting wrapper around evaluate_full_forward_state."""
    def __init__(self, result_factory=lambda: _fake_p49(), delay=0.0):
        self.calls = 0
        self._factory = result_factory
        self._delay = delay
        self._lock = threading.Lock()

    def __call__(self, *a, **k):
        if self._delay:
            import time as _t
            _t.sleep(self._delay)
        with self._lock:
            self.calls += 1
        return self._factory()


# --- 1. cold computes authoritative -----------------------------------------
def test_cold_request_computes_authoritative():
    spy = _SpyCompute()
    with patch.object(Phase49MonitoringFacade, "evaluate_full_forward_state", spy):
        r = client.get(EP)
    assert r.status_code == 200
    assert spy.calls == 1
    assert r.json()["sample_n"] == 7
    assert r.json()["next_milestone"] == 10


# --- 2. warm returns cached (no recompute) ---------------------------------
def test_warm_request_uses_cache():
    spy = _SpyCompute()
    with patch.object(Phase49MonitoringFacade, "evaluate_full_forward_state", spy):
        first = client.get(EP).json()
        second = client.get(EP).json()
        third = client.get(EP).json()
    assert spy.calls == 1
    assert first == second == third


# --- 3. cached response semantically identical to uncached authoritative ---
def test_cached_response_semantically_identical_to_authoritative():
    Phase49MonitoringFacade.invalidate_forward_state_snapshot()
    cached_api = client.get(EP).json()          # populates + serves cache

    authoritative = Phase49MonitoringFacade.evaluate_full_forward_state(mode="PAPER", symbol="XAUUSD")
    m = authoritative.get("metrics", {})
    u = authoritative.get("uncertainty", {})
    ms = authoritative.get("milestones", {})
    d = authoritative.get("decision", {})
    wci = u.get("wilson_win_rate_ci", (0.0, 1.0))

    assert cached_api["sample_n"] == int(m.get("trades_n", 0))
    assert cached_api["win_rate_pct"] == pytest.approx(float(m.get("win_rate_pct", 0.0)))
    assert cached_api["profit_factor"] == pytest.approx(float(m.get("profit_factor", 0.0)))
    assert cached_api["expected_r"] == pytest.approx(float(m.get("expectancy_r", 0.0)))
    assert cached_api["next_milestone"] == int(ms.get("next_milestone", 1))
    assert cached_api["decision_state"] == str(d.get("decision_state", "WAITING FOR SAMPLE"))
    assert cached_api["wilson_ci_lower_pct"] == pytest.approx(round(float(wci[0]) * 100.0, 2))
    assert cached_api["wilson_ci_upper_pct"] == pytest.approx(round(float(wci[1]) * 100.0, 2))
    assert cached_api["strategy_contract_hash"] == FROZEN_CONTRACT_HASH


# --- 4. TTL expiration -> recompute ---------------------------------------
def test_ttl_expiration_recomputes(monkeypatch):
    spy = _SpyCompute()
    monkeypatch.setattr(Phase49MonitoringFacade, "evaluate_full_forward_state", spy)

    base = 100_000.0
    fake_now = {"t": base}
    monkeypatch.setattr(fsm.time, "time", lambda: fake_now["t"])

    Phase49MonitoringFacade.get_cached_forward_state_snapshot()
    assert spy.calls == 1
    fake_now["t"] = base + 59.0
    Phase49MonitoringFacade.get_cached_forward_state_snapshot()
    assert spy.calls == 1                        # still inside 60s TTL
    fake_now["t"] = base + 61.0
    Phase49MonitoringFacade.get_cached_forward_state_snapshot()
    assert spy.calls == 2                        # TTL elapsed -> recompute


# --- 5. explicit invalidation -> recompute -------------------------------
def test_explicit_invalidation_recomputes():
    spy = _SpyCompute()
    with patch.object(Phase49MonitoringFacade, "evaluate_full_forward_state", spy):
        client.get(EP)
        assert spy.calls == 1
        client.get(EP)
        assert spy.calls == 1
        Phase49MonitoringFacade.invalidate_forward_state_snapshot()
        client.get(EP)
        assert spy.calls == 2


# --- 6. no duplicate Phase 50 audit rows from repeated GET --------------
def test_repeated_get_polling_creates_no_audit_rows():
    conn = database.get_connection()
    cur = conn.cursor()

    def _count():
        try:
            cur.execute("SELECT COUNT(*) FROM xauusd_phase50_operational_audits")
            return int(cur.fetchone()[0])
        except Exception:
            return 0

    Phase49MonitoringFacade.invalidate_forward_state_snapshot()
    before = _count()
    for _ in range(8):
        assert client.get(EP).status_code == 200
    after = _count()
    conn.close()
    assert after == before, f"repeated GET added {after - before} Phase 50 audit rows"


def test_read_path_does_not_invoke_phase50():
    import xauusd_forward_end_to_end_proof as e2e
    Phase49MonitoringFacade.invalidate_forward_state_snapshot()
    with patch.object(e2e.Phase50E2EOperationalProofEngine, "audit_end_to_end_pipeline",
                      side_effect=AssertionError("Phase 50 audit invoked on read path")):
        assert client.get(EP).status_code == 200
        assert client.get(EP).status_code == 200


# --- 7. Strategy Contract SHA unchanged --------------------------------
def test_strategy_contract_hash_unchanged():
    data = client.get(EP).json()
    assert data["strategy_contract_hash"] == FROZEN_CONTRACT_HASH
    assert data["strategy_contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


# --- 8. historical holdout baseline / isolation unchanged --------------
def test_historical_baseline_isolation_unchanged():
    b = client.get(EP).json()["historical_baseline"]
    assert b["sample_size"] == HISTORICAL_BASELINE["trades_n"] == 82
    assert b["expected_r"] == pytest.approx(HISTORICAL_BASELINE["expectancy_r"])
    assert b["win_rate_pct"] == pytest.approx(HISTORICAL_BASELINE["win_rate_pct"])
    assert b["profit_factor"] == pytest.approx(HISTORICAL_BASELINE["profit_factor"])
    assert b["status"] == "LOCKED & UNPOOLED"


# --- 9. evidence statistics identical cached vs authoritative ----------
def test_statistics_identical_cached_vs_fresh():
    Phase49MonitoringFacade.invalidate_forward_state_snapshot()
    a = client.get(EP).json()                       # cached
    Phase49MonitoringFacade.invalidate_forward_state_snapshot()
    b = client.get(EP).json()                       # freshly recomputed
    for k in ("sample_n", "win_rate_pct", "profit_factor", "expected_r",
              "next_milestone", "decision_state", "wilson_ci_lower_pct",
              "wilson_ci_upper_pct", "strategy_contract_hash"):
        assert a[k] == b[k], k


# --- 10. response schema unchanged -----------------------------------
def test_response_schema_unchanged():
    data = client.get(EP).json()
    assert set(data.keys()) == RESPONSE_KEYS
    assert data["live_broker_transmission"] == "BLOCKED"
    assert data["symbol"] == "XAUUSD"
    assert data["mode"] == "PAPER"


# --- 11. no execution / broker capability -----------------------------
def test_no_execution_capability_introduced():
    assert client.post(EP, json={}).status_code == 405
    assert client.get("/api/forward-evidence/execute").status_code == 404
    assert client.post("/api/forward-evidence/submit", json={}).status_code == 404
    assert client.get(EP).json()["live_broker_transmission"] == "BLOCKED"


# --- 12. concurrent reads: computed exactly once ---------------------
def test_concurrent_reads_compute_once():
    spy = _SpyCompute(delay=0.05)
    with patch.object(Phase49MonitoringFacade, "evaluate_full_forward_state", spy):
        Phase49MonitoringFacade.invalidate_forward_state_snapshot()
        results = []
        errors = []

        def worker():
            try:
                r = client.get(EP)
                results.append((r.status_code, r.json()))
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not errors
    assert len(results) == 12
    assert all(sc == 200 for sc, _ in results)
    payloads = [p for _, p in results]
    assert all(p == payloads[0] for p in payloads)
    assert spy.calls == 1
