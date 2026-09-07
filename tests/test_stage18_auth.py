# -*- coding: utf-8 -*-
"""
W3 — single-user session auth for the API.

Auth is OFF unless a passphrase is configured (TL_AUTH_PASSWORD[_HASH]); with it
configured, every /api/* route needs a valid session cookie or bearer token,
except health / the auth routes / the OpenAPI docs.
"""
import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app

PASSPHRASE = "a-strong-test-passphrase-123"


# --- auth disabled (the default — must not change anything) ------------

def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TL_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("TL_AUTH_PASSWORD_HASH", raising=False)
    assert auth.auth_enabled() is False
    c = TestClient(app)
    assert c.get("/api/watchlist").status_code == 200
    s = c.get("/api/auth/status").json()
    assert s == {"auth_required": False, "authenticated": True, "timestamp": s["timestamp"]}


# --- auth enabled -----------------------------------------------------

@pytest.fixture()
def authed_env(monkeypatch):
    monkeypatch.setenv("TL_AUTH_PASSWORD", PASSPHRASE)
    monkeypatch.setenv("TL_AUTH_COOKIE_SECURE", "0")
    monkeypatch.delenv("TL_AUTH_DISABLED", raising=False)
    auth.revoke_all_sessions()
    # reset the in-process rate limiter
    auth._attempts.clear()
    yield
    auth.revoke_all_sessions()
    auth._attempts.clear()


PROTECTED = ["/api/watchlist", "/api/positions", "/api/analytics/performance",
             "/api/operations/system", "/api/ai/status", "/api/macro/scorecard/EURUSD"]
EXEMPT = ["/api/health", "/api/auth/status"]


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_routes_401_without_session(authed_env, path):
    assert TestClient(app).get(path).status_code == 401


@pytest.mark.parametrize("path", EXEMPT)
def test_exempt_routes_open_without_session(authed_env, path):
    assert TestClient(app).get(path).status_code == 200


def test_login_then_access(authed_env):
    c = TestClient(app)
    assert c.get("/api/watchlist").status_code == 401

    bad = c.post("/api/auth/login", json={"password": "nope"})
    assert bad.status_code == 401 and bad.json()["ok"] is False

    ok = c.post("/api/auth/login", json={"password": PASSPHRASE})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    assert c.cookies.get(auth.cookie_name())

    assert c.get("/api/watchlist").status_code == 200
    assert c.get("/api/auth/status").json()["authenticated"] is True


def test_bearer_token_is_accepted(authed_env):
    c = TestClient(app)
    token, _ = auth.create_session("test")
    fresh = TestClient(app)
    assert fresh.get("/api/positions", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert fresh.get("/api/positions", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_logout_revokes_the_session(authed_env):
    c = TestClient(app)
    c.post("/api/auth/login", json={"password": PASSPHRASE})
    assert c.get("/api/watchlist").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/watchlist").status_code == 401


def test_login_rate_limit_locks_out(authed_env, monkeypatch):
    monkeypatch.setenv("TL_AUTH_MAX_ATTEMPTS", "3")
    c = TestClient(app)
    for _ in range(3):
        assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    blocked = c.post("/api/auth/login", json={"password": "wrong"})
    assert blocked.status_code == 429
    # even the correct passphrase is refused while locked out
    assert c.post("/api/auth/login", json={"password": PASSPHRASE}).status_code == 429


def test_revoke_all_sessions(authed_env):
    t1, _ = auth.create_session()
    t2, _ = auth.create_session()
    assert auth.validate_token(t1) and auth.validate_token(t2)
    auth.revoke_all_sessions()
    assert not auth.validate_token(t1) and not auth.validate_token(t2)


def test_password_hash_roundtrip():
    h = auth.hash_password("hunter2-hunter2")
    assert h.startswith("scrypt$")
    assert auth._verify_against_hash("hunter2-hunter2", h)
    assert not auth._verify_against_hash("wrong", h)


def test_expired_session_is_rejected(authed_env, monkeypatch):
    monkeypatch.setenv("TL_AUTH_SESSION_DAYS", "-1")  # already expired
    token, _ = auth.create_session()
    assert auth.validate_token(token) is False


def test_no_execution_capability_added(authed_env):
    """Auth must not have introduced an order path."""
    c = TestClient(app)
    c.post("/api/auth/login", json={"password": PASSPHRASE})
    h = c.get("/api/health").json()
    assert h["automation_enabled"] is False
    assert h["live_broker_transmission"] == "BLOCKED"
