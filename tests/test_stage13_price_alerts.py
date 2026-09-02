# -*- coding: utf-8 -*-
"""
Tests for Stage 13 — Price Alerts migration.

`GET/POST/DELETE /api/alerts` is a thin CRUD adapter over the authoritative
`price_alerts` table and the canonical `database.*_price_alert` helpers. It is
monitoring only: no order / execution / broker path, no automation toggle.
Alert *evaluation* stays in the `auto_sync` daemon and is not touched here.
"""
import pytest
from fastapi.testclient import TestClient

import database
from api.main import app

client = TestClient(app)

VALID = {"symbol": "XAUUSD", "target_price": 2500.0, "condition": "ABOVE", "notes": "stage13"}


@pytest.fixture()
def cleanup_alerts():
    """Delete any alert ids created during a test."""
    created: list[int] = []
    yield created
    for aid in created:
        try:
            database.delete_price_alert(aid)
        except Exception:
            pass


def _create(payload) -> int:
    r = client.post("/api/alerts", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["alert"]["id"]


# 1. GET returns persisted alerts + canonical shape ------------------------
def test_get_alerts_shape():
    r = client.get("/api/alerts")
    assert r.status_code == 200
    d = r.json()
    assert set(("alerts", "total", "active", "triggered", "supported_symbols")) <= set(d)
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["source"] == "price_alerts"
    assert "XAUUSD" in d["supported_symbols"]
    assert d["total"] == len(d["alerts"])


def test_get_matches_canonical_model(cleanup_alerts):
    aid = _create(VALID)
    cleanup_alerts.append(aid)
    df = database.get_all_price_alerts(limit=50)
    row = df[df["id"] == aid].iloc[0]
    api_alert = next(a for a in client.get("/api/alerts").json()["alerts"] if a["id"] == aid)
    assert api_alert["symbol"] == str(row["symbol"]).upper()
    assert float(api_alert["target_price"]) == float(row["target_price"])
    assert api_alert["condition"] == str(row["condition"]).upper()
    assert api_alert["status"] == str(row["status"]).upper()


# 2. POST creates a valid alert ------------------------------------------
def test_post_creates_alert(cleanup_alerts):
    r = client.post("/api/alerts", json=VALID)
    assert r.status_code == 201
    a = r.json()["alert"]
    cleanup_alerts.append(a["id"])
    assert a["symbol"] == "XAUUSD"
    assert a["condition"] == "ABOVE"
    assert a["status"] == "ACTIVE"
    assert a["target_price"] == 2500.0
    assert a["created_at"] is not None
    assert a["triggered_at"] is None
    assert r.json()["live_broker_transmission"] == "BLOCKED"


def test_post_normalizes_symbol_alias(cleanup_alerts):
    r = client.post("/api/alerts", json={**VALID, "symbol": "gold"})
    assert r.status_code == 201
    cleanup_alerts.append(r.json()["alert"]["id"])
    assert r.json()["alert"]["symbol"] == "XAUUSD"


# 3. POST rejects invalid payloads -------------------------------------
@pytest.mark.parametrize("payload", [
    {"symbol": "XAUUSD", "target_price": 2500.0},                       # missing condition
    {"symbol": "XAUUSD", "condition": "ABOVE"},                          # missing price
    {"target_price": 2500.0, "condition": "ABOVE"},                      # missing symbol
    {"symbol": "XAUUSD", "target_price": -1.0, "condition": "ABOVE"},    # negative price
    {"symbol": "XAUUSD", "target_price": 0, "condition": "ABOVE"},       # zero price
    {"symbol": "XAUUSD", "target_price": "abc", "condition": "ABOVE"},   # non-numeric
    {"symbol": "", "target_price": 2500.0, "condition": "ABOVE"},        # empty symbol
])
def test_post_rejects_invalid_payload(payload):
    assert client.post("/api/alerts", json=payload).status_code == 422


# 4. POST rejects unsupported symbol / condition ----------------------
def test_post_rejects_unsupported_symbol():
    r = client.post("/api/alerts", json={**VALID, "symbol": "SOLUSDT"})
    assert r.status_code == 422
    assert "unsupported symbol" in r.text.lower()


def test_post_rejects_unsupported_condition():
    assert client.post("/api/alerts", json={**VALID, "condition": "EQUALS"}).status_code == 422
    assert client.post("/api/alerts", json={**VALID, "condition": "above"}).status_code == 422


# 5. unknown fields rejected -----------------------------------------
@pytest.mark.parametrize("extra", ["id", "status", "created_at", "triggered_at", "account_id", "foo"])
def test_post_rejects_unknown_field(extra):
    r = client.post("/api/alerts", json={**VALID, extra: "x" if extra != "id" else 999})
    assert r.status_code == 422


# 6 & 7. DELETE ------------------------------------------------------
def test_delete_removes_existing_alert(cleanup_alerts):
    aid = _create(VALID)
    r = client.delete(f"/api/alerts/{aid}")
    assert r.status_code == 200
    assert r.json() == {**r.json(), "deleted": True, "alert_id": aid}
    assert all(a["id"] != aid for a in client.get("/api/alerts").json()["alerts"])


def test_delete_unknown_alert_404():
    assert client.delete("/api/alerts/999999999").status_code == 404


def test_delete_non_integer_id_422():
    assert client.delete("/api/alerts/not-a-number").status_code == 422


# 8. persistence survives GET after creation -----------------------
def test_persistence_survives_get(cleanup_alerts):
    aid = _create({**VALID, "notes": "persist-marker"})
    cleanup_alerts.append(aid)
    got = next(a for a in client.get("/api/alerts").json()["alerts"] if a["id"] == aid)
    assert got["notes"] == "persist-marker"
    # and a direct DB read agrees
    df = database.get_all_price_alerts(limit=50)
    assert str(df[df["id"] == aid].iloc[0]["notes"]) == "persist-marker"


# 9. collection route has no PUT/PATCH ---------------------------
def test_no_update_endpoints(cleanup_alerts):
    aid = _create(VALID)
    cleanup_alerts.append(aid)
    assert client.put("/api/alerts", json=VALID).status_code == 405
    assert client.patch(f"/api/alerts/{aid}", json={"target_price": 1.0}).status_code == 405


# 10-13. no execution / broker / automation side effects ---------
def test_alert_crud_does_not_touch_execution_state(cleanup_alerts):
    sys_before = client.get("/api/operations/system").json()
    audit_before = client.get("/api/operations/audit?limit=1").json()

    aid = _create(VALID)
    client.delete(f"/api/alerts/{aid}")

    sys_after = client.get("/api/operations/system").json()
    audit_after = client.get("/api/operations/audit?limit=1").json()

    assert sys_after["live_automation_enabled"] is False
    assert sys_after["live_broker_transmission"] == "BLOCKED"
    assert sys_before["open_positions"] == sys_after["open_positions"]
    assert audit_before["total_records"] == audit_after["total_records"]
    assert audit_before["mode_counts"] == audit_after["mode_counts"]


def test_health_flags_unchanged_by_alert_create(cleanup_alerts):
    h_before = client.get("/api/health").json()
    aid = _create(VALID)
    cleanup_alerts.append(aid)
    h_after = client.get("/api/health").json()
    assert h_after["automation_enabled"] is False
    assert h_after["live_broker_transmission"] == "BLOCKED"
    assert h_before["automation_enabled"] == h_after["automation_enabled"]


def test_alerts_router_imports_no_execution_modules():
    """The router's namespace must not bind any execution / broker symbol."""
    import types
    import api.routers.alerts as mod

    forbidden = {"execution_pipeline", "broker_adapter", "risk_gateway",
                 "submit_order", "get_broker_adapter", "CanonicalExecutionRequest"}
    for name, value in vars(mod).items():
        assert name not in forbidden, f"router binds forbidden symbol {name}"
        if isinstance(value, types.ModuleType):
            assert value.__name__.split(".")[0] not in forbidden, (
                f"router imported forbidden module {value.__name__}"
            )
